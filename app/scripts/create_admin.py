"""
Run once at startup to ensure the admin user exists.
Reads ADMIN_LOGIN and ADMIN_PASSWORD from .env via app.config.
"""
import sys
import os

# Ensure project root is on the path when run as `python -m app.scripts.create_admin`
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.config import settings
from app.db.base import SessionLocal
from app.services.auth import get_user_by_login, hash_password
from app.models.user import User


def create_admin() -> None:
    db = SessionLocal()
    try:
        existing = get_user_by_login(db, settings.ADMIN_LOGIN)
        if existing:
            print(f"[create_admin] Admin '{settings.ADMIN_LOGIN}' already exists, skipping.")
            return

        admin = User(
            login=settings.ADMIN_LOGIN,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            role="admin",
            allowed_games=999999,
        )
        db.add(admin)
        db.commit()
        print(f"[create_admin] Admin '{settings.ADMIN_LOGIN}' created successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
