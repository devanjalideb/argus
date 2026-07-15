"""The Blast Radius exact-reconstruction spine: reconstruction must equal the ground
truth from the ledger, no more and no less.
"""
from sqlalchemy import select

from app.models import Endpoint, EventLedger, Investigation, Vulnerability


def _ground_truth(db, vuln_ref, categories=("transaction",)):
    v = db.scalar(select(Vulnerability).where(Vulnerability.vuln_ref == vuln_ref))
    ep = db.get(Endpoint, v.affected_endpoint_id)
    win_end = v.exposure_window_end or v.disclosed_at
    rows = db.scalars(select(EventLedger).where(
        EventLedger.endpoint_id == ep.id,
        EventLedger.event_category.in_(categories),
        EventLedger.event_time >= v.exposure_window_start,
        EventLedger.event_time <= win_end,
    )).all()
    return v, rows


def test_weak_cipher_reconstruction_is_exact(db):
    v, rows = _ground_truth(db, "CVE-2016-2183")
    expected_count = len(rows)
    expected_total = sum(float(r.amount) for r in rows if r.amount is not None)
    assert expected_count > 0, "seed should route transactions through the weak-cipher endpoint"

    inv = db.scalar(select(Investigation).where(Investigation.vulnerability_id == v.id))
    recon = inv.meta["reconstruction"]
    assert recon["exposed_records"] == expected_count
    assert abs(recon["total_amount"] - expected_total) < 1.0


def test_unaffected_customers_excluded(db):
    """Customers with no activity through the affected endpoint must not appear."""
    v, rows = _ground_truth(db, "CVE-2016-2183")
    exposed_customers = {r.customer_id for r in rows if r.customer_id}
    inv = db.scalar(select(Investigation).where(Investigation.vulnerability_id == v.id))
    assert inv.meta["reconstruction"]["exposed_customers"] == len(exposed_customers)


def test_quantum_is_potential_not_confirmed(db):
    v = db.scalar(select(Vulnerability).where(Vulnerability.vuln_ref == "PQC-ADVISORY-2026-01"))
    inv = db.scalar(select(Investigation).where(Investigation.vulnerability_id == v.id))
    assert inv.category == "quantum_exposure"
    assert inv.meta["reconstruction"]["classification"] == "potential_future_exposure"


def test_reconstruction_is_deterministic(db):
    """Re-running reconstruction yields identical counts."""
    from app.modules.blast_radius import BlastRadiusService
    a = BlastRadiusService(db).reconstruct("CVE-2016-2183")
    b = BlastRadiusService(db).reconstruct("CVE-2016-2183")
    assert a["exposed_records"] == b["exposed_records"]
    assert a["total_amount"] == b["total_amount"]
