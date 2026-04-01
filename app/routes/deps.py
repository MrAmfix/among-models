from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.user import User
from app.services.auth import get_user_by_id


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(db, user_id)


def require_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user


def require_admin(
    request: Request, db: Session = Depends(get_db)
) -> User:
    user = require_user(request, db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return user
