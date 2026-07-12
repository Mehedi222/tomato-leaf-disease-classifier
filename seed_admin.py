import getpass

from auth_utils import create_user
from db import get_session, init_db
from models import User


def seed_admin(session, username: str, password: str) -> User:
    existing = session.query(User).filter_by(username=username).first()
    if existing is not None:
        raise ValueError(f"User '{username}' already exists")
    return create_user(session, username, password, role="admin")


def main():
    init_db()
    session = get_session()
    username = input("Admin username: ")
    password = getpass.getpass("Admin password: ")
    user = seed_admin(session, username, password)
    print(f"Created admin user '{user.username}' (id={user.id})")
    session.close()


if __name__ == "__main__":
    main()
