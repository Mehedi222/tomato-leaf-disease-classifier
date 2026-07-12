import bcrypt

from models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_user(session, username: str, password: str, role: str = "user") -> User:
    user = User(username=username, password_hash=hash_password(password), role=role)
    session.add(user)
    session.commit()
    return user


def authenticate(session, username: str, password: str) -> User | None:
    user = session.query(User).filter_by(username=username).first()
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
