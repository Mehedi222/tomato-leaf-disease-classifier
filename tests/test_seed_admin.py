import pytest

from models import User
from seed_admin import seed_admin


def test_seed_admin_creates_admin_role(session):
    user = seed_admin(session, "root", "adminpass123")
    assert user.role == "admin"
    stored = session.query(User).filter_by(username="root").first()
    assert stored is not None
    assert stored.password_hash != "adminpass123"


def test_seed_admin_rejects_duplicate_username(session):
    seed_admin(session, "root", "adminpass123")
    with pytest.raises(ValueError):
        seed_admin(session, "root", "otherpass")
