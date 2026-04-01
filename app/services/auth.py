from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.user import User

pwd_context = CryptContext(
    # `bcrypt_sha256` removes bcrypt's 72-byte input limitation.
    # Keep `bcrypt` for compatibility with hashes that may already exist.
    schemes=["bcrypt_sha256", "bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_user_by_login(db: Session, login: str) -> User | None:
    return db.query(User).filter(User.login == login).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, login: str, password: str, role: str = "user") -> User:
    user = User(
        login=login,
        password_hash=hash_password(password),
        role=role,
        allowed_games=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, login: str, password: str) -> User | None:
    user = get_user_by_login(db, login)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
