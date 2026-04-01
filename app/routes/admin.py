from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.model_catalog import ModelCatalog
from app.models.user import User
from app.routes.deps import require_admin

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def admin_index(
    request: Request,
    search: str = Query(default=""),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if search:
        query = query.filter(User.login.ilike(f"%{search}%"))
    users = query.order_by(User.id).all()
    return templates.TemplateResponse(
        "admin/index.html",
        {
            "request": request,
            "user": admin,
            "users": users,
            "search": search,
            "success": request.query_params.get("success"),
        },
    )


@router.post("/grant-games", response_class=HTMLResponse)
def grant_games(
    request: Request,
    target_user_id: int = Form(...),
    amount: int = Form(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if amount <= 0:
        return RedirectResponse("/admin?error=invalid_amount", status_code=302)

    target = db.query(User).filter(User.id == target_user_id).first()
    if target is None:
        return RedirectResponse("/admin?error=user_not_found", status_code=302)

    target.allowed_games += amount
    db.commit()
    return RedirectResponse(f"/admin?success=1&login={target.login}", status_code=302)


@router.get("/models", response_class=HTMLResponse)
def admin_models(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    models = db.query(ModelCatalog).order_by(ModelCatalog.id).all()
    return templates.TemplateResponse(
        "admin/models.html",
        {
            "request": request,
            "user": admin,
            "models": models,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/models/toggle", response_class=HTMLResponse)
def toggle_model(
    model_id: int = Form(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ = admin
    model = db.query(ModelCatalog).filter(ModelCatalog.id == model_id).first()
    if model is None:
        return RedirectResponse("/admin/models?error=model_not_found", status_code=302)

    model.is_active = not model.is_active
    db.commit()
    return RedirectResponse("/admin/models?success=toggled", status_code=302)


@router.post("/models/add", response_class=HTMLResponse)
def add_model(
    name: str = Form(...),
    model_id: str = Form(...),
    description: str = Form(default=""),
    is_active: bool = Form(default=False),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ = admin
    clean_name = name.strip()
    clean_model_id = model_id.strip()
    clean_description = description.strip()

    if not clean_name or not clean_model_id:
        return RedirectResponse("/admin/models?error=invalid_data", status_code=302)

    model = ModelCatalog(
        name=clean_name,
        model_id=clean_model_id,
        description=clean_description or None,
        is_active=is_active,
    )
    db.add(model)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return RedirectResponse("/admin/models?error=duplicate_model_id", status_code=302)

    return RedirectResponse("/admin/models?success=added", status_code=302)
