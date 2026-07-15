"""Risk Memory APIs — inspect behavioural profiles and apply analyst feedback."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.response import success
from app.models import Customer, Device, Endpoint, IPAddress
from app.models.enums import EntityType
from app.modules.risk_memory import RiskMemoryService

router = APIRouter(prefix="/risk-memory", tags=["risk-memory"])


@router.post("/recompute", summary="Recompute all behavioural profiles from history")
def recompute(db: Session = Depends(get_db)):
    return success(RiskMemoryService(db).recompute_all())


@router.get("/search", summary="Search entities with behavioural profiles")
def search(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    like = f"%{q}%"
    customers = db.scalars(select(Customer).where(
        or_(Customer.customer_ref.like(like), Customer.full_name.like(like))).limit(10)).all()
    svc = RiskMemoryService(db)
    return success({
        "customers": [{
            "entity_type": "customer", "id": c.id, "ref": c.customer_ref,
            "name": c.full_name, "type": c.customer_type,
            "profile": svc.get_customer_profile(c.id),
        } for c in customers],
    })


@router.get("/customer/{customer_ref}", summary="Behavioural profile by customer ref")
def customer_profile(customer_ref: str, db: Session = Depends(get_db)):
    c = db.scalar(select(Customer).where(Customer.customer_ref == customer_ref))
    if not c:
        raise NotFoundError(f"Unknown customer '{customer_ref}'")
    profile = RiskMemoryService(db).get_customer_profile(c.id)
    return success({"customer": {"id": c.id, "ref": c.customer_ref, "name": c.full_name,
                                 "type": c.customer_type, "region": c.region}, "profile": profile})


@router.get("/{entity_type}/{entity_id}", summary="Behavioural profile by entity")
def profile(entity_type: str, entity_id: str, db: Session = Depends(get_db)):
    p = RiskMemoryService(db).get_profile(entity_type, entity_id)
    if not p:
        raise NotFoundError(f"No Risk Memory profile for {entity_type}:{entity_id}")
    return success(p)


@router.post("/{entity_type}/{entity_id}/feedback", summary="Fold analyst feedback into baseline")
def feedback(entity_type: str, entity_id: str, material: bool = True, db: Session = Depends(get_db)):
    return success(RiskMemoryService(db).apply_feedback(entity_type, entity_id, material))
