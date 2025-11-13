"""FastAPI router providing a simple administrative dashboard UI."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .admin_service import AdminUserService
from .db import get_db
from .models import HealthMetric

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/admin", tags=["admin"])


def _current_admin(
    request: Request, session: Session
) -> Optional[str]:  # pragma: no cover - small helper
    admin_id = request.session.get("admin_user_id")
    if not admin_id:
        return None
    admin = AdminUserService(session).get_by_id(admin_id)
    if not admin:
        request.session.clear()
        return None
    return admin.id


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    admin_id = _current_admin(request, db)
    if admin_id:
        return RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("admin/login.html", {"request": request, "error": None})


@router.post("/login")
async def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    service = AdminUserService(db)
    user = service.authenticate(username, password)
    if not user:
        context = {"request": request, "error": "用户名或密码错误"}
        return templates.TemplateResponse("admin/login.html", context, status_code=status.HTTP_401_UNAUTHORIZED)
    request.session["admin_user_id"] = user.id
    return RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    if not _current_admin(request, db):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    service = AdminUserService(db)
    stats = service.dashboard_stats()
    recent_metrics = db.execute(
        select(HealthMetric)
        .where(HealthMetric.deleted.is_(False))
        .order_by(desc(HealthMetric.created_at))
        .limit(10)
    ).scalars().all()
    context = {
        "request": request,
        "stats": stats,
        "recent_metrics": recent_metrics,
    }
    return templates.TemplateResponse("admin/dashboard.html", context)


@router.get("/metrics", response_class=HTMLResponse)
async def metrics_list(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int = 20,
    user_id: Optional[str] = None,
    type_code: Optional[str] = None,
):
    if not _current_admin(request, db):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))
    stmt = select(HealthMetric).where(HealthMetric.deleted.is_(False))
    if user_id:
        stmt = stmt.where(HealthMetric.user_id == user_id)
    if type_code:
        stmt = stmt.where(HealthMetric.type_code == type_code)
    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()
    stmt = stmt.order_by(desc(HealthMetric.recorded_at)).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(stmt).scalars().all()
    context = {
        "request": request,
        "metrics": rows,
        "page": page,
        "page_size": page_size,
        "total": total or 0,
        "user_id": user_id or "",
        "type_code": type_code or "",
    }
    return templates.TemplateResponse("admin/metrics.html", context)


@router.post("/metrics/{record_id}/delete")
async def delete_metric(record_id: str, request: Request, db: Session = Depends(get_db)):
    if not _current_admin(request, db):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    metric = db.get(HealthMetric, record_id)
    if not metric or metric.deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记录不存在或已删除")
    metric.deleted = True
    db.add(metric)
    return RedirectResponse(url=request.headers.get("referer", "/admin/metrics"), status_code=status.HTTP_303_SEE_OTHER)
