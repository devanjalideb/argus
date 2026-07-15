"""Investigation APIs — the central interface of ARGUS (queue + workspace + lifecycle)."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginated, success
from app.models import Investigation
from app.models.base import utcnow
from app.modules.investigations import InvestigationService

router = APIRouter(prefix="/investigations", tags=["investigations"])


@router.get("", summary="List investigations (Investigation Queue)")
def list_investigations(
    db: Session = Depends(get_db),
    status: str | None = None,
    severity: str | None = None,
    engine: str | None = None,
    category: str | None = None,
    search: str | None = None,
    sort: str = "detected_at",
    order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    items, total = InvestigationService(db).list(
        status=status, severity=severity, engine=engine, category=category, search=search,
        sort=sort, order=order, page=page, page_size=page_size)
    return paginated(items, total, page, page_size)


@router.get("/summary", summary="Queue metrics")
def summary(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Investigation)) or 0
    active = db.scalar(select(func.count()).select_from(Investigation).where(
        Investigation.status.in_(["open", "in_progress", "contained"]))) or 0
    critical = db.scalar(select(func.count()).select_from(Investigation).where(
        Investigation.severity == "critical",
        Investigation.status.in_(["open", "in_progress", "contained"]))) or 0
    today = db.scalar(select(func.count()).select_from(Investigation).where(
        Investigation.detected_at >= utcnow() - timedelta(days=1))) or 0
    return success({"total": total, "active": active, "critical": critical,
                    "created_today": today})


@router.get("/{code}", summary="Full investigation (Investigation Workspace)")
def get_investigation(code: str, db: Session = Depends(get_db)):
    return success(InvestigationService(db).detail(code))


@router.post("/{code}/assign", summary="Assign an analyst")
def assign(code: str, analyst: str = Body(..., embed=True), db: Session = Depends(get_db)):
    return success(InvestigationService(db).assign(code, analyst))


@router.post("/{code}/status", summary="Update status")
def set_status(code: str, status: str = Body(..., embed=True),
               note: str | None = Body(None, embed=True), db: Session = Depends(get_db)):
    return success(InvestigationService(db).update_status(code, status, note))


@router.post("/{code}/escalate", summary="Escalate to executive priority")
def escalate(code: str, note: str | None = Body(None, embed=True), db: Session = Depends(get_db)):
    return success(InvestigationService(db).escalate(code, note))


@router.post("/{code}/close", summary="Close investigation")
def close(code: str, resolution: str = Body(..., embed=True), db: Session = Depends(get_db)):
    return success(InvestigationService(db).update_status(code, "closed", resolution))
