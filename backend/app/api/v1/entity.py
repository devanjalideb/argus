"""Entity Explorer APIs — 360° view of a single entity (customer)."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.response import success
from app.models import AuthEvent, Customer, Device, Endpoint, Transaction
from app.models.base import utcnow
from app.modules.risk_memory import RiskMemoryService

router = APIRouter(prefix="/entity", tags=["entity"])


@router.get("/customer/{ref}", summary="Full 360 view of a customer entity")
def customer_entity(ref: str, db: Session = Depends(get_db)):
    c = db.scalar(select(Customer).where(Customer.customer_ref == ref))
    if not c:
        raise NotFoundError(f"Unknown customer '{ref}'")

    txns = db.scalars(select(Transaction).where(Transaction.customer_id == c.id)
                      .order_by(desc(Transaction.event_time))).all()
    total = sum(float(t.amount or 0) for t in txns)
    count = len(txns)

    # 30-day daily transaction history
    since = utcnow() - timedelta(days=30)
    daily: dict[str, float] = {}
    for t in txns:
        if t.event_time and t.event_time >= since:
            k = t.event_time.date().isoformat()
            daily[k] = daily.get(k, 0.0) + float(t.amount or 0)
    history = [{"date": k, "amount": round(v, 2)} for k, v in sorted(daily.items())]

    # top endpoints traversed (real proxy for "counterparties")
    ep_vol: dict[str, float] = {}
    for t in txns:
        if t.endpoint_id:
            ep_vol[t.endpoint_id] = ep_vol.get(t.endpoint_id, 0.0) + float(t.amount or 0)
    top = sorted(ep_vol.items(), key=lambda kv: kv[1], reverse=True)[:6]
    ep_map = {e.id: e for e in db.scalars(select(Endpoint).where(
        Endpoint.id.in_([e for e, _ in top] or ["__none__"]))).all()}
    top_endpoints = [{"ref": ep_map[eid].endpoint_ref, "name": ep_map[eid].name,
                      "amount": round(v, 2)} for eid, v in top if eid in ep_map]

    recent = [{"ref": t.txn_ref, "amount": float(t.amount or 0), "category": t.category,
               "channel": t.channel, "status": t.status,
               "time": t.event_time.isoformat() if t.event_time else None} for t in txns[:12]]

    auths = db.scalars(select(AuthEvent).where(AuthEvent.customer_id == c.id)
                       .order_by(desc(AuthEvent.event_time)).limit(12)).all()
    logins = [{"result": a.result, "method": a.method, "browser": a.browser,
               "time": a.event_time.isoformat() if a.event_time else None} for a in auths]

    prof = RiskMemoryService(db).get_customer_profile(c.id) or {}
    dev_ids = prof.get("preferred_devices", []) or []
    devices = [{"name": d.os, "detail": d.browser, "category": d.category,
                "trust": round(d.trust_score, 2),
                "last_seen": d.last_seen.isoformat() if d.last_seen else None}
               for d in db.scalars(select(Device).where(Device.id.in_(dev_ids or ["__none__"]))).all()]

    return success({
        "customer": {"ref": c.customer_ref, "name": c.full_name, "type": c.customer_type,
                     "region": c.region},
        "stats": {"total": round(total, 2), "count": count,
                  "avg": round(total / count, 2) if count else 0.0},
        "history": history, "top_endpoints": top_endpoints, "recent": recent,
        "logins": logins, "devices": devices, "profile": prof,
    })
