"""Synthetic-data & pipeline APIs — for development, demos and the Integrations page.

Isolated from operational investigation workflows.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.models import (
    Account,
    AuthEvent,
    Customer,
    Endpoint,
    EventLedger,
    Investigation,
    Transaction,
    Vulnerability,
)
from app.modules.pipeline import run_detection
from app.synthetic.seed import run_seed

router = APIRouter(prefix="/synthetic", tags=["synthetic"])


@router.get("/status", summary="Ecosystem & investigation counts")
def status(db: Session = Depends(get_db)):
    def c(model):
        return db.scalar(select(func.count()).select_from(model)) or 0
    return success({
        "customers": c(Customer), "accounts": c(Account), "endpoints": c(Endpoint),
        "auth_events": c(AuthEvent), "transactions": c(Transaction),
        "ledger_events": c(EventLedger), "vulnerabilities": c(Vulnerability),
        "investigations": c(Investigation),
    })


@router.post("/seed", summary="Reset and regenerate the synthetic banking ecosystem")
def seed(num_customers: int = Body(45, embed=True),
         baseline_days: int = Body(75, embed=True)):
    summary = run_seed(reset=True, num_customers=num_customers, baseline_days=baseline_days)
    return success(summary)


@router.post("/pipeline", summary="Run detection + enrichment over current data")
def pipeline(enrich: bool = Body(True, embed=True), db: Session = Depends(get_db)):
    return success(run_detection(db, reset=True, enrich=enrich))


@router.post("/rebuild", summary="Full demo rebuild: seed + detect + enrich")
def rebuild(db: Session = Depends(get_db)):
    seed_summary = run_seed(reset=True)
    detection = run_detection(db, reset=True, enrich=True)
    return success({"seed": seed_summary, "detection": {
        "watchtower": detection["watchtower"]["investigations_created"],
        "blast_radius": detection["blast_radius"]["investigations_created"],
        "enriched": detection.get("enrichment", {}).get("enriched_investigations", 0),
    }})
