from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.game import Game
from app.routes.deps import get_current_user, require_user
from app.models.user import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=302)

    games = (
        db.query(Game)
        .filter(Game.creator_id == user.id)
        .order_by(Game.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user, "games": games},
    )
