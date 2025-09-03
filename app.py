import streamlit as st
from login_app import login_ui
from dashboard_core import dashboard_main

st.set_page_config(page_title="AGC Dashboard", layout="wide")

def main():
    if "page" not in st.session_state:
        st.session_state.page = "login"
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.page == "dashboard" and st.session_state.logged_in:
        dashboard_main()
    else:
        login_ui()

if __name__ == "__main__":
    main()

