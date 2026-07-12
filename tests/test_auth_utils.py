from auth_utils import authenticate, create_user, hash_password, verify_password


def test_hash_and_verify_roundtrip():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True


def test_verify_rejects_wrong_password():
    hashed = hash_password("secret123")
    assert verify_password("wrong", hashed) is False


def test_authenticate_returns_user_for_correct_credentials(session):
    create_user(session, "alice", "secret123", role="admin")
    user = authenticate(session, "alice", "secret123")
    assert user is not None
    assert user.username == "alice"
    assert user.role == "admin"


def test_authenticate_returns_none_for_wrong_password(session):
    create_user(session, "alice", "secret123", role="admin")
    assert authenticate(session, "alice", "wrong") is None


def test_authenticate_returns_none_for_unknown_user(session):
    assert authenticate(session, "nobody", "secret123") is None
