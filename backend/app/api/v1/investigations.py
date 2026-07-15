"""Investigation APIs — the central interface of ARGUS (queue + workspace + lifecycle)."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginated, success
from app.models import BusinessImpact, Customer, Investigation, Recommendation
from app.models.base import utcnow
from app.modules.investigations import InvestigationService

_ACTIVE = ["open", "in_progress", "contained"]
_SEV_WEIGHT = {"critical": 18, "high": 10, "medium": 4, "low": 2}
_INSIGHTS = {
    "account_takeover": "Multiple anomalies observed post credential compromise. Immediate containment recommended.",
    "credential_stuffing": "Automated credential stuffing across many accounts from one source. Block and force resets.",
    "insider_misuse": "A privileged account is accessing customer records off-hours. Suspend and review immediately.",
    "api_abuse": "Abnormal API request velocity from an unregistered client. Apply rate limiting and investigate.",
    "retrospective_exposure": "Historical cardholder data traversed a weak-cipher endpoint. Regulatory review required.",
    "quantum_exposure": "Harvest-now-decrypt-later exposure of sensitive material. Prioritize post-quantum migration.",
}

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


@router.get("/command-center", summary="Command Center aggregate metrics")
def command_center(db: Session = Depends(get_db)):
    invs = db.scalars(select(Investigation).where(Investigation.status.in_(_ACTIVE))).all()
    ids = [i.id for i in invs] or ["__none__"]
    bi_map = {b.investigation_id: b for b in db.scalars(select(BusinessImpact).where(
        BusinessImpact.investigation_id.in_(ids), BusinessImpact.is_active == True)).all()}  # noqa: E712

    sev = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    business_risk = 0.0
    affected = 0
    for i in invs:
        sev[i.severity] = sev.get(i.severity, 0) + 1
        b = bi_map.get(i.id)
        if b:
            business_risk += float(b.financial_exposure)
            affected += b.affected_customers

    score = min(100, sum(_SEV_WEIGHT.get(i.severity, 0) for i in invs))
    label = ("Critical" if score >= 85 else "High" if score >= 60
             else "Medium" if score >= 35 else "Low")

    ranked = sorted(invs, key=lambda i: float(bi_map[i.id].financial_exposure)
                    if i.id in bi_map else 0.0, reverse=True)
    top = ranked[0] if ranked else None
    top_priority = key_insight = None
    suggested: list = []
    if top:
        tb = bi_map.get(top.id)
        cust = db.get(Customer, top.primary_customer_id) if top.primary_customer_id else None
        top_priority = {
            "code": top.code, "title": top.title, "severity": top.severity,
            "customer_ref": cust.customer_ref if cust else None,
            "exposure": float(tb.financial_exposure) if tb else 0.0,
            "affected": tb.affected_customers if tb else 0,
        }
        key_insight = _INSIGHTS.get(top.category,
                                    "Review the highest-priority case and contain if confirmed.")
        recs = db.scalars(select(Recommendation).where(
            Recommendation.investigation_id == top.id).order_by(Recommendation.priority)).all()
        suggested = [{"label": r.title, "rec_type": r.rec_type, "priority": r.priority}
                     for r in recs[:4]]

    return success({
        "threat_level": {"score": score, "label": label},
        "active_total": len(invs), "severity_counts": sev,
        "business_risk": round(business_risk, 2), "affected_customers": affected,
        "top_priority": top_priority, "key_insight": key_insight,
        "suggested_actions": suggested, "trends_available": False,
    })


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
