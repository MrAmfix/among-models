from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.services.auth import (
    authenticate_user,
    create_user,
    get_user_by_login,
)
from app.routes.deps import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return templates.TemplateResponse(
        "index.html", {"request": request, "user": user}
    )


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(
        "auth/register.html", {"request": request, "error": None}
    )


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
    db: Session = Depends(get_db),
):
    login = login.strip()
    error = None

    if len(login) < 3:
        error = "Логин должен содержать минимум 3 символа"
    elif len(password) < 6:
        error = "Пароль должен содержать минимум 6 символов"
    elif password != password2:
        error = "Пароли не совпадают"
    elif get_user_by_login(db, login):
        error = "Пользователь с таким логином уже существует"

    if error:
        return templates.TemplateResponse(
            "auth/register.html", {"request": request, "error": error}
        )

    create_user(db, login=login, password=password)
    return RedirectResponse("/login?registered=1", status_code=302)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, registered: str = None, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "error": None, "registered": registered == "1"},
    )


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, login.strip(), password)
    if user is None:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Неверный логин или пароль", "registered": False},
        )
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)
