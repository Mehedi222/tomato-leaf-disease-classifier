import streamlit as st

from auth_utils import authenticate
from db import get_session, init_db


def render_login():
    _, center, _ = st.columns([1, 2, 1])
    with center:
        with st.container(border=True):
            st.title("Login")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Log in", type="primary"):
                session = get_session()
                user = authenticate(session, username, password)
                session.close()
                if user is None:
                    st.error("Invalid username or password")
                else:
                    st.session_state["user"] = {
                        "id": user.id,
                        "username": user.username,
                        "role": user.role,
                    }
                    st.rerun()


def render_app():
    with st.sidebar:
        st.write(f"Logged in as **{st.session_state['user']['username']}**")
        if st.button("Logout"):
            del st.session_state["user"]
            st.rerun()

    pages = [
        st.Page("pages/predict_page.py", title="Predict", icon="🔬"),
        st.Page("pages/my_history_page.py", title="My History", icon="📜"),
    ]

    if st.session_state["user"]["role"] == "admin":
        pages.append(st.Page("pages/admin_dashboard_page.py", title="Admin Dashboard", icon="📊"))

    navigation = st.navigation(pages, position="top")
    navigation.run()


init_db()

if "user" not in st.session_state:
    login_page = st.Page(render_login, title="Login", visibility="hidden")
    st.navigation([login_page]).run()
else:
    render_app()
