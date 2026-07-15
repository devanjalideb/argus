"""Ingestion & event-ledger APIs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import paginated, success
from app.models import Endpoint, EventLedger, IngestionAudit
from app.modules.ingestion import IngestionService
from app.schemas.ingestion import (
    AnalystActionIn,
    AuthEventIn,
    DisclosureIn,
    EndpointIn,
    TransactionIn,
)

router = APIRouter(prefix="/ingest", tags=["ingestion"])
events_router = APIRouter(prefix="/events", tags=["events"])


@router.post("/auth", summary="Ingest an authentication event")
def ingest_auth(payload: AuthEventIn, db: Session = Depends(get_db)):
    return success(IngestionService(db).ingest_auth(payload))


@router.post("/transaction", summary="Ingest a banking transaction")
def ingest_transaction(payload: TransactionIn, db: Session = Depends(get_db)):
    return success(IngestionService(db).ingest_transaction(payload))


@router.post("/disclosure", summary="Ingest a vulnerability disclosure event")
def ingest_disclosure(payload: DisclosureIn, db: Session = Depends(get_db)):
    return success(IngestionService(db).ingest_disclosure(payload))


@router.post("/endpoint", summary="Register / update an infrastructure endpoint")
def ingest_endpoint(payload: EndpointIn, db: Session = Depends(get_db)):
    return success(IngestionService(db).upsert_endpoint(payload))


@router.post("/analyst-action", summary="Record an analyst action")
def ingest_analyst_action(payload: AnalystActionIn, db: Session = Depends(get_db)):
    return success(IngestionService(db).ingest_analyst_action(payload))


@router.get("/audit", summary="Recent ingestion audit trail")
def audit(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    rows = db.scalars(select(IngestionAudit).order_by(desc(IngestionAudit.received_at)).limit(limit)).all()
    return success([{
        "id": r.id, "received_at": r.received_at.isoformat(), "event_type": r.event_type,
        "source": r.source, "validation_ok": r.validation_ok, "normalized": r.normalized,
        "enriched": r.enriched, "persisted": r.persisted, "correlation_id": r.correlation_id,
        "preview": r.payload_preview,
    } for r in rows])


@events_router.get("", summary="Query the normalized event ledger")
def list_events(
    db: Session = Depends(get_db),
    event_type: str | None = None,
    customer_id: str | None = None,
    endpoint_ref: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    stmt = select(EventLedger)
    count_stmt = select(func.count()).select_from(EventLedger)
    if event_type:
        stmt = stmt.where(EventLedger.event_type == event_type)
        count_stmt = count_stmt.where(EventLedger.event_type == event_type)
    if customer_id:
        stmt = stmt.where(EventLedger.customer_id == customer_id)
        count_stmt = count_stmt.where(EventLedger.customer_id == customer_id)
    if endpoint_ref:
        ep = db.scalar(select(Endpoint).where(Endpoint.endpoint_ref == endpoint_ref))
        eid = ep.id if ep else "__none__"
        stmt = stmt.where(EventLedger.endpoint_id == eid)
        count_stmt = count_stmt.where(EventLedger.endpoint_id == eid)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(desc(EventLedger.event_time)).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [{
        "id": r.id, "event_uid": r.event_uid, "event_type": r.event_type,
        "event_category": r.event_category, "event_time": r.event_time.isoformat(),
        "customer_id": r.customer_id, "endpoint_id": r.endpoint_id,
        "amount": float(r.amount) if r.amount is not None else None,
        "severity": r.severity, "payload": r.payload,
    } for r in rows]
    return paginated(items, total, page, page_size)
