"""Watchtower, Business Impact, Explainable AI and the end-to-end pipeline."""
from sqlalchemy import select

from app.models import AINarrative, BusinessImpact, Evidence, Investigation


def _by_category(db, category):
    return db.scalar(select(Investigation).where(Investigation.category == category))


def test_pipeline_creates_all_scenarios(db):
    cats = {i.category for i in db.scalars(select(Investigation)).all()}
    for expected in ("account_takeover", "credential_stuffing", "insider_misuse",
                     "api_abuse", "retrospective_exposure", "quantum_exposure"):
        assert expected in cats, f"missing investigation category: {expected}"


def test_watchtower_ato_has_evidence_and_confidence(db):
    inv = _by_category(db, "account_takeover")
    assert inv is not None
    assert inv.originating_engine == "watchtower"
    assert inv.confidence >= 80
    ev = db.scalars(select(Evidence).where(Evidence.investigation_id == inv.id)).all()
    assert len(ev) >= 3
    # confidence must be decomposed for explainability
    assert len(inv.meta.get("confidence_breakdown", [])) >= 3


def test_business_impact_scales_with_severity(db):
    ato = _by_category(db, "account_takeover")
    api = _by_category(db, "api_abuse")
    bi_ato = db.scalar(select(BusinessImpact).where(
        BusinessImpact.investigation_id == ato.id, BusinessImpact.is_active == True))  # noqa: E712
    bi_api = db.scalar(select(BusinessImpact).where(
        BusinessImpact.investigation_id == api.id, BusinessImpact.is_active == True))  # noqa: E712
    # A high-value account takeover outranks operational API abuse.
    assert float(bi_ato.financial_exposure) > float(bi_api.financial_exposure)
    assert bi_ato.executive_priority == "P1"


def test_weak_cipher_flags_pci(db):
    inv = _by_category(db, "retrospective_exposure")
    bi = db.scalar(select(BusinessImpact).where(
        BusinessImpact.investigation_id == inv.id, BusinessImpact.is_active == True))  # noqa: E712
    assert "PCI-DSS" in bi.regulatory_flags
    assert float(bi.financial_exposure) > 0


def test_ai_narrative_is_grounded(db):
    inv = _by_category(db, "retrospective_exposure")
    nar = db.scalar(select(AINarrative).where(
        AINarrative.investigation_id == inv.id, AINarrative.is_active == True))  # noqa: E712
    assert nar is not None
    assert nar.grounded is True
    # offline narrator by default (no API key in tests)
    assert nar.provider == "offline"
    assert len(nar.executive_summary) > 100
    assert "reconstruct" in nar.technical_summary.lower()
