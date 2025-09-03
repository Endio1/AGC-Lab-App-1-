import streamlit as st
import pandas as pd
import time
import io
import plotly.express as px
import plotly.graph_objects as go

def dashboard_main():
    st.title("AGC Anomaly Detection - Flowchart Logic")

    st.markdown("""
        ⚙️ This page runs the full **flowchart-based anomaly logic**.

        🔁 Use simulation or upload full file, then optionally inject error using sidebar.
    """)

    # ----- Sidebar Inputs -----
    start_time = st.sidebar.text_input("Start Timestamp (YYYY-MM-DD HH:MM:SS)", key="start_time")
    end_time = st.sidebar.text_input("End Timestamp (YYYY-MM-DD HH:MM:SS)", key="end_time")

    error_agc = st.sidebar.number_input("AGC Error to Add (MW)", value=0.0, key="error_agc")
    error_df = st.sidebar.number_input("∆f Error to Add (Hz)", value=0.0, key="error_df")

    if 'inject' not in st.session_state:
        st.session_state['inject'] = None

    if st.sidebar.button("Apply Error"):
        st.session_state['inject'] = {
            "start": start_time,
            "end": end_time,
            "agc": error_agc,
            "df": error_df
        }

    if st.sidebar.button("Remove Error"):
        st.session_state['inject'] = None

    simulate_mode = st.sidebar.checkbox("Enable Row-by-Row Simulation")
    sim_speed = st.sidebar.slider("Simulation Speed (seconds per step)", min_value=1, max_value=10, value=4)
    play = st.sidebar.button("▶ Play")
    pause = st.sidebar.button("⏸ Pause")

    uploaded_file = st.file_uploader("Upload Excel File", type=["xls", "xlsx"], key="file")

    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file, engine='openpyxl' if uploaded_file.name.endswith('xlsx') else 'xlrd')
        df = df.dropna()
        df.columns = df.columns.str.strip()
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')

        required = ['Timestamp', 'Frequency', 'AGC U1', 'ULSP U1']
        if not all(col in df.columns for col in required):
            st.error(f"Missing one of the required columns: {required}")
            return

        df['Injected'] = False
        df['AGC After'] = df['AGC U1']

        # Apply injection if any
        if st.session_state['inject']:
            inj = st.session_state['inject']
            t_start = pd.to_datetime(inj['start'], errors='coerce')
            t_end = pd.to_datetime(inj['end'], errors='coerce')
            mask = (df['Timestamp'] >= t_start) & (df['Timestamp'] <= t_end)

            if inj['agc'] != 0.0:
                df.loc[mask, 'AGC After'] += inj['agc']
                df.loc[mask, 'Injected'] = True

            if inj['df'] != 0.0:
                df.loc[mask, 'Frequency'] += inj['df']
                df.loc[mask, 'Injected'] = True

        # Step pre-calculations
        df['E'] = df['AGC U1'] - df['AGC After']   # A1 - A2
        df['∆F'] = df['Frequency'] - 50
        df['∆P'] = df['AGC After'] - df['ULSP U1']
        df['N'] = df['∆F'] * df['∆P']
        df['Error'] = df['E']  # for scatter plot

        alarm_results = []
        m_vals = [0]
        counter = 0

        for i in range(len(df)):
            row = df.iloc[i]
            alarm_flag = ""

            # ---------- Step 1 ----------
            if abs(row['E']) > 0:
                alarm_flag = "1"

            else:
                # ---------- Step 2 ----------
                if -0.10 < row['∆F'] < 0.25:
                    pass  # go to Step 3
                else:
                    if row['N'] > 0:
                        alarm_flag = "2"
                    elif row['N'] < 0:
                        pass  # go to Step 3
                    elif row['N'] == 0 and row['∆P'] == 0:
                        pass  # go to Step 3
                    else:
                        alarm_flag = "2"

            # ---------- Step 3 ----------
            if alarm_flag == "":
                if i > 0:
                    dt = (df['Timestamp'].iloc[i] - df['Timestamp'].iloc[i-1]).total_seconds() / 60.0
                    if dt == 0: 
                        m_val = 0
                    else:
                        m_val = (row['AGC U1'] - row['AGC After']) / dt
                else:
                    m_val = 0

                m_vals.append(m_val)

                if m_val == 0:
                    if i > 0:
                        dF = row['Frequency'] - df['Frequency'].iloc[i-1]
                        dt_sec = (df['Timestamp'].iloc[i] - df['Timestamp'].iloc[i-1]).total_seconds()
                        roc_of = abs(dF) / dt_sec if dt_sec > 0 else 0
                    else:
                        dF = 0
                        roc_of = 0

                    if -0.10 < dF < 0.10 and roc_of < 1:
                        alarm_flag = ""
                        counter = 0
                    else:
                        counter += 1
                        if counter >= 20:
                            alarm_flag = "3"
                elif m_val > 0:
                    if m_val > 20:
                        alarm_flag = "3"
                    elif row['∆F'] > 0:
                        alarm_flag = "3"
                elif m_val < 0:
                    if m_val < -20:
                        alarm_flag = "3"
                    elif row['∆F'] < 0:
                        alarm_flag = "3"
            else:
                m_vals.append(m_vals[-1])

            alarm_results.append(alarm_flag)

        df['M (MW/min)'] = m_vals[:len(df)]
        df['Final Alarm'] = alarm_results

        display_cols = [
            'Timestamp', 'Frequency', 'AGC U1', 'AGC After',
            '∆F', '∆P', 'N', 'M (MW/min)', 'Final Alarm', 'Error'
        ]

        def highlight(row):
            if row['Final Alarm'] == "1":
                return ['background-color: #ffcccc; color: black'] * len(row)
            elif row['Final Alarm'] == "2":
                return ['background-color: #fff2cc; color: black'] * len(row)
            elif row['Final Alarm'] == "3":
                return ['background-color: #ccffcc; color: black'] * len(row)
            return [''] * len(row)

        final_df = df[display_cols]

        # Simulation vs Full Table
        if simulate_mode and play:
            st.subheader("🔁 Simulation Playback (Every {} Seconds)".format(sim_speed))
            placeholder = st.empty()
            for i in range(9, len(final_df) + 1):
                if pause:
                    break
                display_df = final_df.iloc[i - 9:i]
                placeholder.dataframe(display_df.style.apply(highlight, axis=1), use_container_width=True)
                time.sleep(sim_speed)
        else:
            st.subheader("📊 Full AGC Data with All Flowchart Checks")
            st.dataframe(final_df.style.apply(highlight, axis=1), use_container_width=True)

        # ------------------- GRAPH OPTIONS -------------------
        st.sidebar.subheader("📊 Select Graphs to Display")
        graph_options = st.sidebar.multiselect(
            "Choose graphs",
            [
                "Line: Frequency vs Time",
                "Line: AGC Before vs After",
                "Line: ∆F vs Time",
                "Line: ∆P vs Time",
                "Line: M (MW/min) vs Time",
                "Multiline: AGC Before & After",
                "Multiline: AGC Before & Frequency",
                "Heatmap: AGC & Frequency",
                "Scatter: Error vs Time"
            ]
        )

        # ------------------- LINE GRAPHS -------------------
        if "Line: Frequency vs Time" in graph_options:
            fig = px.line(final_df, x="Timestamp", y="Frequency",
                          title="Frequency vs Time")
            st.plotly_chart(fig, use_container_width=True)

        if "Line: AGC Before vs After" in graph_options:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=final_df['Timestamp'], y=final_df['AGC U1'],
                                     mode='lines', name='AGC Before'))
            fig.add_trace(go.Scatter(x=final_df['Timestamp'], y=final_df['AGC After'],
                                     mode='lines', name='AGC After'))
            fig.update_layout(title="AGC Before vs After")
            st.plotly_chart(fig, use_container_width=True)

        if "Line: ∆F vs Time" in graph_options:
            fig = px.line(final_df, x="Timestamp", y="∆F",
                          title="∆F vs Time")
            st.plotly_chart(fig, use_container_width=True)

        if "Line: ∆P vs Time" in graph_options:
            fig = px.line(final_df, x="Timestamp", y="∆P",
                          title="∆P vs Time")
            st.plotly_chart(fig, use_container_width=True)

        if "Line: M (MW/min) vs Time" in graph_options:
            fig = px.line(final_df, x="Timestamp", y="M (MW/min)",
                          title="M (MW/min) vs Time")
            st.plotly_chart(fig, use_container_width=True)

        # ------------------- MULTILINE GRAPHS -------------------
        if "Multiline: AGC Before & After" in graph_options:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=final_df['Timestamp'], y=final_df['AGC U1'],
                                     mode='lines', name='AGC Before'))
            fig.add_trace(go.Scatter(x=final_df['Timestamp'], y=final_df['AGC After'],
                                     mode='lines', name='AGC After'))
            fig.update_layout(title="AGC Before & After Over Time")
            st.plotly_chart(fig, use_container_width=True)

        if "Multiline: AGC Before & Frequency" in graph_options:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=final_df['Timestamp'], y=final_df['AGC U1'],
                                     mode='lines', name='AGC Before'))
            fig.add_trace(go.Scatter(x=final_df['Timestamp'], y=final_df['Frequency'],
                                     mode='lines', name='Frequency'))
            fig.update_layout(title="AGC Before & Frequency Over Time")
            st.plotly_chart(fig, use_container_width=True)

        # ------------------- HEATMAP -------------------
        if "Heatmap: AGC & Frequency" in graph_options:
            heatmap_df = final_df[["AGC U1", "AGC After", "Frequency"]].corr()
            fig = px.imshow(heatmap_df,
                            text_auto=True,
                            color_continuous_scale="RdBu_r",
                            title="Heatmap of AGC & Frequency")
            st.plotly_chart(fig, use_container_width=True)

        # ------------------- SCATTER PLOT -------------------
        if "Scatter: Error vs Time" in graph_options:
            fig = px.scatter(final_df, x="Timestamp", y="Error",
                             title="Error vs Time", opacity=0.7)
            st.plotly_chart(fig, use_container_width=True)

        # ---------- NEW: Download Option ----------
        st.subheader("⬇️ Download Table")
        buffer = io.BytesIO()
        final_df.to_excel(buffer, index=False)
        st.download_button(
            label="Download as Excel",
            data=buffer,
            file_name="AGC_Flowchart_Results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        csv = final_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download as CSV",
            data=csv,
            file_name="AGC_Flowchart_Results.csv",
            mime="text/csv"
        )

    else:
        st.warning("Please upload a valid Excel file to begin.")

