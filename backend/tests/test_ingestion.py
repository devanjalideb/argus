"""Ingestion validation, normalization and Risk Memory behaviour."""
import pytest
from sqlalchemy import func, select

from app.core.exceptions import NotFoundError
from app.models import Customer, EventLedger
from app.modules.ingestion import IngestionService
from app.modules.risk_memory import RiskMemoryService
from app.schemas.ingestion import AuthEventIn


def test_ingest_auth_grows_ledger(db):
    before = db.scalar(select(func.count()).select_from(EventLedger))
    cust = db.scalar(select(Customer)).customer_ref
    IngestionService(db).ingest_auth(AuthEventIn(
        customer_ref=cust, device_fingerprint="dev-test", ip_address="203.0.113.7",
        result="success", country="UAE"))
    after = db.scalar(select(func.count()).select_from(EventLedger))
    assert after == before + 1


def test_unknown_customer_rejected(db):
    with pytest.raises(NotFoundError):
        IngestionService(db).ingest_auth(AuthEventIn(
            customer_ref="CUST-99999", device_fingerprint="x", ip_address="1.2.3.4",
            result="success"))


def test_risk_memory_profiles_are_bounded(db):
    profiles = RiskMemoryService(db)
    cust = db.scalar(select(Customer))
    p = profiles.get_customer_profile(cust.id)
    assert p is not None
    assert 0.0 <= p["trust_score"] <= 1.0
    assert 0.0 <= p["behavioural_confidence"] <= 1.0
    assert p["observation_count"] >= 0
