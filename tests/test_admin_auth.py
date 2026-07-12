import bcrypt

from admin_auth import verify_password


def test_verify_password_roundtrip():
    hashed = bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode("utf-8")
    assert verify_password("secret123", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode("utf-8")
    assert verify_password("wrong", hashed) is False
