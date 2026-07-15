"""Ingestion service — validate, normalize, enrich, persist, audit.

API routes stay thin; every normalization/enrichment/persistence decision lives here.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models import (
    Account,
    AuthEvent,
    Customer,
    Device,
    Endpoint,
    EventLedger,
    IngestionAudit,
    IPAddress,
    Transaction,
    Vulnerability,
)
from app.models import AnalystAction, Investigation
from app.models.base import gen_uuid, utcnow
from app.models.enums import AuthResult, EventType
from app.schemas.ingestion import (
    AnalystActionIn,
    AuthEventIn,
    DisclosureIn,
    EndpointIn,
    TransactionIn,
)

logger = get_logger(__name__)

# Map a transaction category to its canonical ledger event type.
_TXN_EVENT_TYPE = {
    "transfer": EventType.TRANSFER,
    "wire": EventType.WIRE,
    "bill_payment": EventType.BILL_PAYMENT,
    "card_payment": EventType.CARD_PAYMENT,
    "atm_withdrawal": EventType.ATM_WITHDRAWAL,
}


def normalize_utc(dt: datetime | None) -> datetime:
    """Standardize any incoming timestamp to naive UTC."""
    if dt is None:
        return utcnow()
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class IngestionService:
    def __init__(self, session: Session):
        self.s = session

    # ---------------------------------------------------------- resolvers
    def _customer(self, ref: str) -> Customer:
        c = self.s.scalar(select(Customer).where(Customer.customer_ref == ref))
        if not c:
            raise NotFoundError(f"Unknown customer_ref '{ref}'")
        return c

    def _account(self, number: str | None) -> Account | None:
        if not number:
            return None
        return self.s.scalar(select(Account).where(Account.account_number == number))

    def _endpoint(self, ref: str) -> Endpoint:
        e = self.s.scalar(select(Endpoint).where(Endpoint.endpoint_ref == ref))
        if not e:
            raise NotFoundError(f"Unknown endpoint_ref '{ref}'")
        return e

    def _device(self, fingerprint: str | None) -> Device | None:
        if not fingerprint:
            return None
        dev = self.s.scalar(select(Device).where(Device.fingerprint == fingerprint))
        if dev:
            dev.last_seen = utcnow()
            return dev
        dev = Device(id=gen_uuid(), fingerprint=fingerprint, os="unknown", browser="unknown",
                     category="unknown", first_seen=utcnow(), last_seen=utcnow(), trust_score=0.1)
        self.s.add(dev)
        self.s.flush()
        return dev

    def _ip(self, address: str | None, city: str | None, country: str | None) -> IPAddress | None:
        if not address:
            return None
        ip = self.s.scalar(select(IPAddress).where(IPAddress.address == address))
        if ip:
            ip.last_seen = utcnow()
            return ip
        ip = IPAddress(id=gen_uuid(), address=address, city=city or "Unknown",
                       country=country or "Unknown", isp="Unknown", reputation_score=0.3,
                       first_seen=utcnow(), last_seen=utcnow())
        self.s.add(ip)
        self.s.flush()
        return ip

    # ---------------------------------------------------------- audit + ledger
    def _audit(self, event_type: str, source: str, *, enriched: bool, preview: dict) -> str:
        cid = str(uuid.uuid4())
        self.s.add(IngestionAudit(
            received_at=utcnow(), event_type=event_type, source=source,
            validation_ok=True, normalized=True, enriched=enriched, persisted=True,
            correlation_id=cid, message="ingested", payload_preview=preview,
        ))
        return cid

    def _ledger(self, **kw) -> EventLedger:
        row = EventLedger(event_uid=gen_uuid(), **kw)
        self.s.add(row)
        return row

    # ---------------------------------------------------------- ingest ops
    def ingest_auth(self, p: AuthEventIn) -> dict:
        when = normalize_utc(p.event_time)
        cust = self._customer(p.customer_ref)
        acct = self._account(p.account_number)
        dev = self._device(p.device_fingerprint)
        ip = self._ip(p.ip_address, p.city, p.country)
        ep = self._endpoint(p.endpoint_ref)
        result = AuthResult.SUCCESS if p.result.lower().startswith("s") else AuthResult.FAILURE

        self.s.add(AuthEvent(
            event_time=when, result=result, method=p.method, customer_id=cust.id,
            account_id=acct.id if acct else None, device_id=dev.id if dev else None,
            ip_id=ip.id if ip else None, endpoint_id=ep.id, browser=dev.browser if dev else None,
            meta={"source": p.source},
        ))
        etype = EventType.LOGIN_SUCCESS if result == AuthResult.SUCCESS else EventType.LOGIN_FAILURE
        self._ledger(event_type=etype, event_category="authentication", event_source=p.source,
                     event_time=when, customer_id=cust.id, account_id=acct.id if acct else None,
                     device_id=dev.id if dev else None, ip_id=ip.id if ip else None,
                     endpoint_id=ep.id,
                     payload={"result": result, "country": p.country, "city": p.city})
        cid = self._audit("auth_event", p.source, enriched=True,
                          preview={"customer": p.customer_ref, "result": result})
        self.s.commit()
        return {"accepted": True, "event_type": etype, "customer": cust.customer_ref,
                "normalized_time": when.isoformat(), "correlation_id": cid}

    def ingest_transaction(self, p: TransactionIn) -> dict:
        when = normalize_utc(p.event_time)
        cust = self._customer(p.customer_ref)
        acct = self._account(p.account_number)
        if not acct:
            raise NotFoundError(f"Unknown account_number '{p.account_number}'")
        dev = self._device(p.device_fingerprint)
        ip = self._ip(p.ip_address, None, None)
        ep = self._endpoint(p.endpoint_ref)
        etype = _TXN_EVENT_TYPE.get(p.category, EventType.TRANSFER)
        txn_ref = f"TXN-{when:%y%m%d}-{gen_uuid()[:10]}"

        self.s.add(Transaction(
            txn_ref=txn_ref, event_time=when, source_account_id=acct.id, customer_id=cust.id,
            dest_external=p.dest_external, device_id=dev.id if dev else None,
            ip_id=ip.id if ip else None, endpoint_id=ep.id, amount=p.amount, currency=p.currency,
            category=p.category, channel=p.channel, status="completed", fraud_status="none",
            meta={"source": p.source},
        ))
        self._ledger(event_type=etype, event_category="transaction", event_source=p.source,
                     event_time=when, customer_id=cust.id, account_id=acct.id,
                     device_id=dev.id if dev else None, ip_id=ip.id if ip else None,
                     endpoint_id=ep.id, amount=p.amount, ref_table="transactions", ref_id=txn_ref,
                     payload={"category": p.category, "channel": p.channel})
        cid = self._audit("transaction", p.source, enriched=True,
                          preview={"customer": p.customer_ref, "amount": p.amount})
        self.s.commit()
        return {"accepted": True, "txn_ref": txn_ref, "event_type": etype,
                "normalized_time": when.isoformat(), "correlation_id": cid}

    def ingest_disclosure(self, p: DisclosureIn) -> dict:
        ep = self._endpoint(p.affected_endpoint_ref)
        existing = self.s.scalar(select(Vulnerability).where(Vulnerability.vuln_ref == p.vuln_ref))
        if existing:
            vuln = existing
        else:
            vuln = Vulnerability(id=gen_uuid(), vuln_ref=p.vuln_ref)
            self.s.add(vuln)
        vuln.disclosure_type = p.disclosure_type
        vuln.title = p.title
        vuln.description = p.description
        vuln.severity = p.severity
        vuln.cvss = p.cvss
        vuln.affected_endpoint_id = ep.id
        vuln.affected_algorithm = p.affected_algorithm
        vuln.exposure_window_start = normalize_utc(p.exposure_window_start)
        vuln.exposure_window_end = normalize_utc(p.exposure_window_end) if p.exposure_window_end else None
        vuln.published_at = utcnow()
        vuln.disclosed_at = utcnow()
        vuln.remediation_deadline = normalize_utc(p.remediation_deadline) if p.remediation_deadline else None

        self._ledger(event_type=EventType.DISCLOSURE, event_category="vulnerability",
                     event_source=p.source, event_time=utcnow(), endpoint_id=ep.id,
                     severity=p.severity, ref_table="vulnerabilities", ref_id=vuln.vuln_ref,
                     payload={"disclosure_type": p.disclosure_type, "title": p.title})
        cid = self._audit("disclosure", p.source, enriched=True,
                          preview={"vuln_ref": p.vuln_ref, "endpoint": p.affected_endpoint_ref})
        self.s.commit()
        return {"accepted": True, "vuln_ref": vuln.vuln_ref, "vulnerability_id": vuln.id,
                "affected_endpoint": ep.endpoint_ref, "correlation_id": cid}

    def upsert_endpoint(self, p: EndpointIn) -> dict:
        ep = self.s.scalar(select(Endpoint).where(Endpoint.endpoint_ref == p.endpoint_ref))
        created = ep is None
        if created:
            ep = Endpoint(id=gen_uuid(), endpoint_ref=p.endpoint_ref, active_from=utcnow())
            self.s.add(ep)
        ep.name = p.name
        ep.category = p.category
        ep.criticality = p.criticality
        ep.data_sensitivity = p.data_sensitivity
        ep.encryption_profile = p.encryption_profile
        self._audit("endpoint", "api", enriched=False,
                    preview={"endpoint_ref": p.endpoint_ref, "created": created})
        self.s.commit()
        return {"accepted": True, "endpoint_ref": ep.endpoint_ref, "created": created}

    def ingest_analyst_action(self, p: AnalystActionIn) -> dict:
        inv = None
        if p.investigation_code:
            inv = self.s.scalar(
                select(Investigation).where(Investigation.code == p.investigation_code))
        self.s.add(AnalystAction(
            investigation_id=inv.id if inv else None, action=p.action, actor=p.actor,
            detail=p.detail, event_time=utcnow(),
        ))
        cid = self._audit("analyst_action", "api", enriched=False,
                          preview={"action": p.action, "investigation": p.investigation_code})
        self.s.commit()
        return {"accepted": True, "action": p.action, "correlation_id": cid}
