import streamlit as st

# Replace with your secure credentials
VALID_USERNAME = "ihub2119"
VALID_PASSWORD = "hsl@wrdm"

def login_ui():
    st.title("🔐 Login to AGC Dashboard")

    username = st.text_input("👤 Username")
    password = st.text_input("🔑 Password", type="password")

    if st.button("Login"):
        if not username or not password:
            st.warning("⚠ Both fields are required.")
        elif username == VALID_USERNAME and password == VALID_PASSWORD:
            st.success("✅ Login successful.")
            st.session_state.logged_in = True
            st.session_state.page = "dashboard"
        else:
            st.error("❌ Invalid username or password.")




#python -m streamlit run login_app.py
#& "C:\Users\YourName\AppData\Local\Programs\Python\Python311\python.exe" -m streamlit run login_app.py

#streamlit run streamlit_app/login_app.py
#streamlit run _app.py