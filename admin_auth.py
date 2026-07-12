import bcrypt
import streamlit as st


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def check_admin_login(username: str, password: str) -> bool:
    expected_username = st.secrets.get("admin_username")
    expected_hash = st.secrets.get("admin_password_hash")
    if expected_username is None or expected_hash is None:
        return False
    if username != expected_username:
        return False
    return verify_password(password, expected_hash)
