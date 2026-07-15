"""Blast Radius engine — retrospective reconstruction of historical exposure.

Given a disclosure, it (1) resolves affected infrastructure, (2) bounds the exposure
window, (3) replays the immutable ledger over that window with deterministic SQL, and
(4) correlates the affected customers, accounts and transactions into a retrospective
investigation. It never predicts — it reconstructs what verifiably happened.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models import Customer, Endpoint, EventLedger, Vulnerability
from app.models.base import utcnow
from app.models.enums import (
    DisclosureType,
    Engine,
    EvidenceCategory,
    InvestigationCategory,
    Severity,
)
from app.modules.investigations import InvestigationService

logger = get_logger(__name__)

# Which ledger categories each disclosure type exposes.
_STRATEGY = {
    DisclosureType.WEAK_CIPHER: ("transaction",),
    DisclosureType.QUANTUM_HNDL: ("transaction",),
    DisclosureType.API_KEY_LEAK: ("authentication", "operational"),
    DisclosureType.CRED_LEAK: ("authentication",),
    DisclosureType.CVE: ("transaction", "authentication"),
    DisclosureType.VENDOR_BREACH: ("transaction", "authentication"),
}


class BlastRadiusService:
    def __init__(self, session: Session):
        self.s = session
        self.inv = InvestigationService(session)

    # ------------------------------------------------------------ public
    def analyze_all(self) -> dict:
        """Reconstruct every disclosure that has not been fully remediated."""
        vulns = self.s.scalars(select(Vulnerability)).all()
        created = []
        for v in vulns:
            if v.patch_status == "patched":
                continue
            created.append(self.reconstruct(v.vuln_ref))
        self.s.commit()
        logger.info("Blast Radius analyze_all: %d retrospective investigations", len(created))
        return {"investigations_created": len(created), "reconstructions": created}

    def reconstruct(self, vuln_ref: str) -> dict:
        vuln = self.s.scalar(select(Vulnerability).where(Vulnerability.vuln_ref == vuln_ref))
        if not vuln:
            raise NotFoundError(f"Unknown vulnerability '{vuln_ref}'")
        ep = self.s.get(Endpoint, vuln.affected_endpoint_id)
        if not ep:
            raise NotFoundError("Affected endpoint not found for disclosure")

        endpoint_ids = [vuln.affected_endpoint_id] + list(vuln.affected_endpoints or [])
        win_start = vuln.exposure_window_start
        win_end = vuln.exposure_window_end or vuln.disclosed_at or utcnow()
        categories = _STRATEGY.get(vuln.disclosure_type, ("transaction",))

        # THE reconstruction query: deterministic replay of the ledger over the window.
        stmt = select(EventLedger).where(
            EventLedger.endpoint_id.in_(endpoint_ids),
            EventLedger.event_category.in_(categories),
            and_(EventLedger.event_time >= win_start, EventLedger.event_time <= win_end),
        ).order_by(EventLedger.event_time)
        records = self.s.scalars(stmt).all()

        customers = {r.customer_id for r in records if r.customer_id}
        accounts = {r.account_id for r in records if r.account_id}
        total_amount = float(sum(float(r.amount) for r in records if r.amount is not None))

        # Aggregate exposure by customer to surface the most-exposed accounts.
        by_customer: dict[str, float] = defaultdict(float)
        for r in records:
            if r.customer_id and r.amount is not None:
                by_customer[r.customer_id] += float(r.amount)
        top = sorted(by_customer.items(), key=lambda kv: kv[1], reverse=True)[:6]
        cust_map = {c.id: c for c in self.s.scalars(
            select(Customer).where(Customer.id.in_([c for c, _ in top] or ["__none__"]))).all()}
        top_customers = [{
            "ref": cust_map[cid].customer_ref if cid in cust_map else cid,
            "name": cust_map[cid].full_name if cid in cust_map else None,
            "type": cust_map[cid].customer_type if cid in cust_map else None,
            "exposed_amount": round(amt, 2),
        } for cid, amt in top]

        classification = self._classification(vuln.disclosure_type)
        confidence = self._confidence(vuln, len(records))
        severity = self._severity(vuln, len(customers), ep)

        recon = {
            "vuln_ref": vuln.vuln_ref, "disclosure_type": vuln.disclosure_type,
            "endpoint": ep.endpoint_ref, "endpoint_name": ep.name,
            "cipher": ep.encryption_profile, "algorithm": vuln.affected_algorithm,
            "window_start": win_start.isoformat(), "window_end": win_end.isoformat(),
            "exposed_records": len(records), "exposed_customers": len(customers),
            "exposed_accounts": len(accounts), "total_amount": round(total_amount, 2),
            "classification": classification, "top_customers": top_customers,
            "sample": [{"event_uid": r.event_uid, "type": r.event_type,
                        "time": r.event_time.isoformat(),
                        "amount": float(r.amount) if r.amount is not None else None}
                       for r in records[:10]],
        }
        inv = self._create_investigation(vuln, ep, recon, confidence, severity)
        return {"code": inv.code, "vuln_ref": vuln.vuln_ref, **{k: recon[k] for k in
                ("exposed_records", "exposed_customers", "total_amount", "classification")},
                "confidence": confidence}

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _classification(disclosure_type: str) -> str:
        if disclosure_type == DisclosureType.QUANTUM_HNDL:
            return "potential_future_exposure"  # harvest-now-decrypt-later
        return "confirmed_exposure"

    @staticmethod
    def _confidence(vuln: Vulnerability, n: int) -> float:
        base = 96.0 if vuln.disclosure_type == DisclosureType.WEAK_CIPHER else 88.0
        if vuln.disclosure_type == DisclosureType.QUANTUM_HNDL:
            base = 82.0
        return round(base if n > 0 else 40.0, 1)

    @staticmethod
    def _severity(vuln: Vulnerability, n_customers: int, ep: Endpoint) -> str:
        if vuln.severity == "critical" or n_customers > 50 or ep.criticality == "critical":
            return Severity.CRITICAL
        if n_customers > 10:
            return Severity.HIGH
        return Severity.MEDIUM

    def _create_investigation(self, vuln, ep, recon, confidence, severity):
        is_quantum = vuln.disclosure_type == DisclosureType.QUANTUM_HNDL
        category = (InvestigationCategory.QUANTUM_EXPOSURE if is_quantum
                    else InvestigationCategory.RETROSPECTIVE_EXPOSURE)
        title = f"Retrospective exposure — {vuln.title.split('—')[0].strip()} ({ep.endpoint_ref})"
        desc = (f"Following disclosure of {vuln.vuln_ref}, deterministic reconstruction over the "
                f"exposure window replayed {recon['exposed_records']:,} events through {ep.name}. "
                f"{recon['exposed_customers']} customers and ₹{recon['total_amount']:,.0f} of activity "
                f"traversed the affected infrastructure while the weakness was live.")

        breakdown = [
            {"factor": "Reconstruction method", "contribution": 1.0,
             "detail": "Deterministic SQL replay of the immutable event ledger (not inference)."},
            {"factor": "Endpoint mapping certainty", "contribution": 1.0,
             "detail": f"Disclosure maps directly to {ep.endpoint_ref} via infrastructure records."},
            {"factor": "Exposure-window precision", "contribution": 0.95,
             "detail": f"Window {recon['window_start'][:10]} → {recon['window_end'][:10]}."},
            {"factor": "Telemetry completeness", "contribution": 0.9 if recon["exposed_records"] else 0.2,
             "detail": f"{recon['exposed_records']:,} matching ledger events available."},
        ]
        timeline = [
            {"time": ep.active_from.isoformat(), "kind": "infra",
             "title": f"{ep.name} deployed", "description": f"Cipher/profile: {ep.encryption_profile}."},
            {"time": recon["window_start"], "kind": "exposure",
             "title": "Exposure window begins", "description": "Weakness live in production."},
            {"time": vuln.disclosed_at.isoformat(), "kind": "disclosure",
             "title": f"{vuln.vuln_ref} disclosed", "description": vuln.title},
        ]
        if vuln.remediation_deadline:
            timeline.append({"time": vuln.remediation_deadline.isoformat(), "kind": "remediation",
                             "title": "Remediation deadline", "description": f"Patch status: {vuln.patch_status}."})

        inv = self.inv.create(
            title=title, description=desc, severity=severity, confidence=confidence,
            category=category, engine=Engine.BLAST_RADIUS, primary_endpoint_id=ep.id,
            vulnerability_id=vuln.id, business_priority="P1" if severity == Severity.CRITICAL else "P2",
            detected_at=vuln.disclosed_at,
            meta={"confidence_breakdown": breakdown, "reconstruction": recon, "timeline": timeline,
                  "predicted_next_step": None,
                  "entities": {"endpoint": ep.endpoint_ref, "vulnerability": vuln.vuln_ref}})

        # Evidence — grounded entirely in the reconstruction.
        self.inv.add_evidence(inv, category=EvidenceCategory.VULNERABILITY,
                              evidence_type="disclosure", source_module="blast_radius",
                              title=f"{vuln.vuln_ref}: {vuln.title}", confidence_contribution=1.0,
                              description=vuln.description, source_entity_type="vulnerability",
                              source_entity_id=vuln.vuln_ref, event_time=vuln.disclosed_at)
        self.inv.add_evidence(inv, category=EvidenceCategory.INFRASTRUCTURE,
                              evidence_type="affected_endpoint", source_module="blast_radius",
                              title=f"Affected: {ep.name} ({ep.encryption_profile})",
                              confidence_contribution=1.0,
                              description=f"Criticality {ep.criticality}, data sensitivity {ep.data_sensitivity}.",
                              source_entity_type="endpoint", source_entity_id=ep.endpoint_ref)
        self.inv.add_evidence(inv, category=EvidenceCategory.TRANSACTION,
                              evidence_type="exposure_reconstruction", source_module="blast_radius",
                              title=f"{recon['exposed_records']:,} events · ₹{recon['total_amount']:,.0f} · {recon['exposed_customers']} customers",
                              confidence_contribution=0.95,
                              description=(f"Deterministic replay over the exposure window. "
                                           f"Classification: {recon['classification'].replace('_',' ')}."),
                              meta={"reconstruction": {k: recon[k] for k in
                                    ("exposed_records", "exposed_customers", "exposed_accounts",
                                     "total_amount", "window_start", "window_end")}})
        for tc in recon["top_customers"][:5]:
            self.inv.add_evidence(inv, category=EvidenceCategory.HISTORICAL,
                                  evidence_type="affected_customer", source_module="blast_radius",
                                  title=f"{tc['ref']} ({tc['type']}) — ₹{tc['exposed_amount']:,.0f} exposed",
                                  confidence_contribution=0.8,
                                  description=f"{tc['name']} had material activity through the affected endpoint.",
                                  source_entity_type="customer", source_entity_id=tc["ref"])
        return inv
