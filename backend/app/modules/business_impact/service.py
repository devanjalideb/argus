"""Business Impact engine — executive risk translation + recommendations.

Consumes investigations already created by Watchtower / Blast Radius and enriches them
with financial exposure, customer segmentation, regulatory obligations, executive
priority (distinct from technical severity) and deterministic next-best-actions.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models import (
    BusinessImpact,
    Customer,
    Endpoint,
    Investigation,
    Recommendation,
    Transaction,
)
from app.models.base import utcnow
from app.models.enums import (
    BusinessPriority,
    DataSensitivity,
    InvestigationCategory,
    RecommendationType,
    Severity,
)

logger = get_logger(__name__)

# Data sensitivity -> applicable regulatory considerations (India-centric bank).
_REG = {
    DataSensitivity.CARDHOLDER: ["PCI-DSS", "RBI Cyber Security Framework"],
    DataSensitivity.PII: ["DPDP Act 2023", "RBI Cyber Security Framework"],
    DataSensitivity.KYC: ["RBI KYC Directions", "DPDP Act 2023"],
    DataSensitivity.FINANCIAL: ["RBI Cyber Security Framework"],
    DataSensitivity.CREDENTIALS: ["RBI Cyber Security Framework", "CERT-In Directions"],
    DataSensitivity.CRYPTO_MATERIAL: ["CERT-In Directions", "RBI Cyber Security Framework"],
    DataSensitivity.BALANCES: ["RBI Cyber Security Framework"],
    DataSensitivity.ADMIN: ["RBI Cyber Security Framework"],
}

# Category -> canonical data sensitivity when not derived from an endpoint.
_CAT_SENSITIVITY = {
    InvestigationCategory.ACCOUNT_TAKEOVER: DataSensitivity.BALANCES,
    InvestigationCategory.CREDENTIAL_STUFFING: DataSensitivity.CREDENTIALS,
    InvestigationCategory.INSIDER_MISUSE: DataSensitivity.PII,
    InvestigationCategory.API_ABUSE: DataSensitivity.BALANCES,
}


class BusinessImpactService:
    def __init__(self, session: Session):
        self.s = session

    def assess(self, ident: str) -> dict:
        inv = self._inv(ident)
        exposure, customers, accounts, sensitivity, segmentation = self._exposure(inv)
        endpoint = self.s.get(Endpoint, inv.primary_endpoint_id) if inv.primary_endpoint_id else None
        criticality = endpoint.criticality if endpoint else "high"
        regulatory = self._regulatory(sensitivity, inv.severity)
        priority = self._priority(inv.severity, exposure, customers)
        disruption = self._disruption(inv.category)
        remediation = self._remediation_cost(inv.category, customers, exposure)

        # Deactivate any prior active assessment (preserve history).
        for prev in self.s.scalars(select(BusinessImpact).where(
                BusinessImpact.investigation_id == inv.id, BusinessImpact.is_active == True)).all():  # noqa: E712
            prev.is_active = False

        bi = BusinessImpact(
            investigation_id=inv.id, financial_exposure=round(exposure, 2),
            affected_customers=customers, affected_accounts=accounts,
            customer_segmentation=segmentation, data_sensitivity=sensitivity,
            infrastructure_criticality=criticality, operational_disruption=disruption,
            regulatory_flags=regulatory, executive_priority=priority,
            executive_severity=self._exec_severity(priority),
            estimated_remediation_cost=round(remediation, 2),
            business_confidence=0.85, recommended_urgency=self._urgency(priority),
            is_active=True, calculated_at=utcnow(),
        )
        self.s.add(bi)
        # Business priority feeds back onto the investigation (still separate from severity).
        inv.business_priority = priority
        inv.lifecycle_stage = "enriched"

        self._recommendations(inv, exposure, customers, sensitivity, regulatory)
        self.s.commit()
        logger.info("Business Impact for %s: INR %.0f, %d customers, priority %s",
                    inv.code, exposure, customers, priority)
        return {"investigation": inv.code, "financial_exposure": round(exposure, 2),
                "affected_customers": customers, "executive_priority": priority,
                "regulatory_flags": regulatory}

    # ------------------------------------------------------------ helpers
    def _inv(self, ident: str) -> Investigation:
        inv = self.s.scalar(select(Investigation).where(Investigation.code == ident))
        if not inv:
            inv = self.s.get(Investigation, ident)
        if not inv:
            raise NotFoundError(f"Unknown investigation '{ident}'")
        return inv

    def _exposure(self, inv: Investigation):
        """Return (financial_exposure, customers, accounts, sensitivity, segmentation)."""
        meta = inv.meta or {}
        recon = meta.get("reconstruction")
        if recon:  # Blast Radius
            ep = self.s.get(Endpoint, inv.primary_endpoint_id) if inv.primary_endpoint_id else None
            sensitivity = ep.data_sensitivity if ep else DataSensitivity.PII
            seg = self._segment_from_top(recon.get("top_customers", []))
            return (recon["total_amount"], recon["exposed_customers"],
                    recon["exposed_accounts"], sensitivity, seg)

        cat = inv.category
        sensitivity = _CAT_SENSITIVITY.get(cat, DataSensitivity.BALANCES)
        if cat == InvestigationCategory.ACCOUNT_TAKEOVER and inv.primary_customer_id:
            amt = self._suspicious_sum(customer_id=inv.primary_customer_id)
            seg = self._segment_customers([inv.primary_customer_id])
            return amt, 1, 1, sensitivity, seg
        if cat == InvestigationCategory.CREDENTIAL_STUFFING:
            amt = self._suspicious_sum()
            victims = int((meta.get("entities") or {}).get("victims", 0))
            return amt, victims, victims, sensitivity, {"retail": victims}
        if cat == InvestigationCategory.INSIDER_MISUSE:
            records = int((meta.get("entities") or {}).get("records", 0))
            return records * 5000.0, records, records, sensitivity, {"pii_records": records}
        # api_abuse and others: operational, negligible direct financial exposure
        return 0.0, 0, 0, sensitivity, {}

    def _suspicious_sum(self, customer_id: str | None = None) -> float:
        stmt = select(Transaction).where(
            Transaction.fraud_status.in_(["suspected", "confirmed"]),
            Transaction.event_time >= utcnow() - timedelta(days=7))
        if customer_id:
            stmt = stmt.where(Transaction.customer_id == customer_id)
        return float(sum(float(t.amount or 0) for t in self.s.scalars(stmt).all()))

    def _segment_customers(self, ids: list[str]) -> dict:
        seg: dict[str, int] = {}
        for c in self.s.scalars(select(Customer).where(Customer.id.in_(ids or ["__none__"]))).all():
            seg[c.customer_type] = seg.get(c.customer_type, 0) + 1
        return seg

    @staticmethod
    def _segment_from_top(top: list[dict]) -> dict:
        seg: dict[str, int] = {}
        for t in top:
            seg[t.get("type", "retail")] = seg.get(t.get("type", "retail"), 0) + 1
        return seg

    @staticmethod
    def _regulatory(sensitivity: str, severity: str) -> list[str]:
        flags = list(_REG.get(sensitivity, ["RBI Cyber Security Framework"]))
        if severity in (Severity.CRITICAL, Severity.HIGH):
            flags.append("CERT-In 6-hour incident reporting")
        return flags

    @staticmethod
    def _priority(severity: str, exposure: float, customers: int) -> str:
        if severity == Severity.CRITICAL or exposure >= 1_00_00_000 or customers >= 100:
            return BusinessPriority.P1
        if severity == Severity.HIGH or exposure >= 10_00_000 or customers >= 20:
            return BusinessPriority.P2
        if exposure > 0 or customers > 0:
            return BusinessPriority.P3
        return BusinessPriority.P4

    @staticmethod
    def _exec_severity(priority: str) -> str:
        return {"P1": "critical", "P2": "high", "P3": "medium", "P4": "low"}[priority]

    @staticmethod
    def _urgency(priority: str) -> str:
        return {"P1": "immediate", "P2": "same_day", "P3": "standard", "P4": "monitor"}[priority]

    @staticmethod
    def _disruption(category: str) -> str:
        return {
            InvestigationCategory.ACCOUNT_TAKEOVER: "customer_facing",
            InvestigationCategory.CREDENTIAL_STUFFING: "customer_facing",
            InvestigationCategory.INSIDER_MISUSE: "internal",
            InvestigationCategory.API_ABUSE: "service_degradation",
            InvestigationCategory.RETROSPECTIVE_EXPOSURE: "payment_processing",
            InvestigationCategory.QUANTUM_EXPOSURE: "cryptographic_infrastructure",
        }.get(category, "moderate")

    @staticmethod
    def _remediation_cost(category: str, customers: int, exposure: float) -> float:
        base = {
            InvestigationCategory.ACCOUNT_TAKEOVER: 150_000,
            InvestigationCategory.CREDENTIAL_STUFFING: 400_000,
            InvestigationCategory.INSIDER_MISUSE: 800_000,
            InvestigationCategory.API_ABUSE: 200_000,
            InvestigationCategory.RETROSPECTIVE_EXPOSURE: 2_500_000,
            InvestigationCategory.QUANTUM_EXPOSURE: 5_000_000,
        }.get(category, 300_000)
        return base + customers * 800 + exposure * 0.01

    # ------------------------------------------------------------ recommendations
    def _recommendations(self, inv: Investigation, exposure: float, customers: int,
                         sensitivity: str, regulatory: list[str]) -> None:
        # Clear any previous recommendations for a clean regeneration.
        for r in self.s.scalars(select(Recommendation).where(
                Recommendation.investigation_id == inv.id)).all():
            self.s.delete(r)

        recs = self._plan(inv.category, exposure, customers, regulatory)
        for rec_type, title, priority, rationale in recs:
            self.s.add(Recommendation(
                investigation_id=inv.id, rec_type=rec_type, title=title,
                description=title, rationale=rationale, priority=priority, status="pending",
                generated_at=utcnow()))

    @staticmethod
    def _plan(category: str, exposure: float, customers: int, regulatory: list[str]):
        reg = ", ".join(regulatory)
        C = InvestigationCategory
        R = RecommendationType
        if category == C.ACCOUNT_TAKEOVER:
            return [
                (R.FREEZE_ACCOUNT, "Freeze the affected account", "P1",
                 f"A ₹{exposure:,.0f} transfer is in flight from a compromised session; freezing halts loss."),
                (R.REVOKE_SESSION, "Revoke active sessions & force re-authentication", "P1",
                 "The attacker holds a live authenticated session from an untrusted device."),
                (R.NOTIFY_CUSTOMER, "Notify the customer through a verified channel", "P2",
                 "Confirm the transaction was not customer-initiated and restore trust."),
                (R.ESCALATE, "Escalate to fraud operations", "P1",
                 "High-value, high-confidence account takeover warrants immediate human review."),
            ]
        if category == C.CREDENTIAL_STUFFING:
            return [
                (R.BLOCK_DEVICE, "Block the source IP at the edge", "P1",
                 "A single IP is driving automated credential stuffing across many accounts."),
                (R.ROTATE_CREDENTIALS, "Force credential reset for targeted accounts", "P2",
                 "Reused/guessed credentials must be invalidated to stop account access."),
                (R.NOTIFY_FRAUD, "Alert fraud monitoring for the compromised account", "P2",
                 "Downstream mule transfers should be watched and intercepted."),
            ]
        if category == C.INSIDER_MISUSE:
            return [
                (R.REVOKE_SESSION, "Suspend the administrative account", "P1",
                 "Bulk off-hours record access is inconsistent with legitimate administration."),
                (R.REGULATORY_REVIEW, f"Initiate regulatory review ({reg})", "P2",
                 f"Potential exposure of personal data engages {reg}."),
                (R.NOTIFY_FRAUD, "Engage insider-threat / fraud team", "P2",
                 "Human review of the accessed record set is required."),
            ]
        if category == C.API_ABUSE:
            return [
                (R.PATCH_ENDPOINT, "Apply rate limiting / WAF rules", "P3",
                 "Request velocity far exceeds baseline; throttle and require client re-registration."),
                (R.NOTIFY_FRAUD, "Monitor for data scraping downstream", "P3",
                 "Confirm whether abusive traffic extracted sensitive data."),
            ]
        if category == C.RETROSPECTIVE_EXPOSURE:
            return [
                (R.PATCH_ENDPOINT, "Decommission the weak cipher / patch the endpoint", "P1",
                 "The affected endpoint must stop negotiating the vulnerable cipher immediately."),
                (R.ROTATE_CREDENTIALS, "Rotate keys/credentials handled by the endpoint", "P2",
                 "Any secrets processed under the weak cipher should be considered compromised."),
                (R.NOTIFY_CUSTOMER, f"Notify affected customers ({customers})", "P2",
                 "Cardholder/PII exposure typically requires customer notification."),
                (R.REGULATORY_REVIEW, f"Initiate regulatory review ({reg})", "P1",
                 f"Exposure of {customers} customers engages {reg}."),
            ]
        if category == C.QUANTUM_EXPOSURE:
            return [
                (R.PATCH_ENDPOINT, "Prioritize post-quantum (PQC) migration for the gateway", "P2",
                 "RSA-2048 key exchange is vulnerable to harvest-now-decrypt-later; migrate to PQC."),
                (R.REGULATORY_REVIEW, f"Assess long-term exposure & report ({reg})", "P2",
                 "Document the harvested-data risk for regulators and executives."),
                (R.ESCALATE, "Brief the CISO on quantum exposure", "P2",
                 "Strategic cryptographic risk requires executive awareness and roadmap funding."),
            ]
        return [(R.ESCALATE, "Escalate for analyst review", "P3",
                 "Investigation requires human triage.")]
