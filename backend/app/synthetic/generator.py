"""Deterministic synthetic banking ecosystem generator.

Builds a believable miniature digital bank: customers with distinct behavioural
identities, accounts, trusted devices, home IPs, infrastructure endpoints, and several
months of *normal* history — the baseline Risk Memory and Watchtower learn from. Attack
scenarios are injected afterwards (see scenarios.py) so investigations emerge naturally.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import (
    Account,
    AuthEvent,
    Customer,
    Device,
    Endpoint,
    EventLedger,
    IPAddress,
    Location,
)
from app.models import Session as BankSession
from app.models.base import gen_uuid, utcnow
from app.models.enums import AuthResult, EventType

from . import catalog

logger = get_logger(__name__)


@dataclass
class CustomerCtx:
    model: Customer
    profile: dict
    accounts: list[Account] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)
    home_ip: IPAddress | None = None
    location: Location | None = None
    amt_mean: float = 0.0


@dataclass
class GenContext:
    """Shared state passed to scenario injectors."""

    session: Session
    rng: random.Random
    now: datetime
    endpoints: dict[str, Endpoint]
    customers: list[CustomerCtx]
    locations: list[Location]
    foreign_locations: list[Location]
    ledger: list[EventLedger] = field(default_factory=list)
    auth_events: list[AuthEvent] = field(default_factory=list)
    bank_sessions: list[BankSession] = field(default_factory=list)
    transactions: list = field(default_factory=list)

    def add_ledger(self, **kw) -> str:
        uid = gen_uuid()
        self.ledger.append(EventLedger(event_uid=uid, **kw))
        return uid


class SyntheticGenerator:
    def __init__(self, session: Session, seed: int = 42,
                 reference_time: datetime | None = None,
                 num_customers: int = 45, baseline_days: int = 75):
        self.session = session
        self.rng = random.Random(seed)
        self.now = reference_time or utcnow()
        self.num_customers = num_customers
        self.baseline_days = baseline_days
        self.ctx: GenContext | None = None

    # ---------------------------------------------------------------- public
    def generate(self) -> dict:
        from . import scenarios  # local import avoids cycle

        # Entities are committed phase-by-phase in dependency order so that later
        # bulk-inserted children always have their parent rows present.
        locations, foreign = self._gen_locations()
        self.session.commit()
        endpoints = self._gen_endpoints()
        self.session.commit()
        customers = self._gen_customers(locations)
        self.session.commit()

        self.ctx = GenContext(
            session=self.session, rng=self.rng, now=self.now,
            endpoints=endpoints, customers=customers,
            locations=locations, foreign_locations=foreign,
        )

        self._gen_baseline_history()
        self._flush_all()

        scenario_summary = scenarios.inject_all(self.ctx)
        self._flush_all()

        summary = {
            "customers": len(customers),
            "accounts": sum(len(c.accounts) for c in customers),
            "devices": sum(len(c.devices) for c in customers),
            "endpoints": len(endpoints),
            "locations": len(locations) + len(foreign),
            "baseline_days": self.baseline_days,
            "scenarios": scenario_summary,
        }
        logger.info("Synthetic ecosystem generated: %s", summary)
        return summary

    # ---------------------------------------------------------------- pieces
    def _gen_locations(self) -> tuple[list[Location], list[Location]]:
        dom, frn = [], []
        for name, country, lat, lon in catalog.DOMESTIC_CITIES:
            dom.append(Location(id=gen_uuid(), city=name, country=country,
                                latitude=lat, longitude=lon,
                                timezone="Asia/Kolkata", region="APAC"))
        for name, country, lat, lon in catalog.FOREIGN_CITIES:
            frn.append(Location(id=gen_uuid(), city=name, country=country,
                                latitude=lat, longitude=lon,
                                timezone="UTC", region="INTL"))
        self.session.add_all(dom + frn)
        return dom, frn

    def _gen_endpoints(self) -> dict[str, Endpoint]:
        eps: dict[str, Endpoint] = {}
        active_from = self.now - timedelta(days=self.baseline_days + 400)
        for ref, name, cat, crit, sens, cipher, weak in catalog.ENDPOINTS:
            ep = Endpoint(
                id=gen_uuid(), endpoint_ref=ref, name=name, category=cat,
                criticality=crit, data_sensitivity=sens, encryption_profile=cipher,
                security_posture="legacy" if weak else "hardened",
                active_from=active_from,
            )
            eps[ref] = ep
        self.session.add_all(list(eps.values()))
        return eps

    def _weighted_archetype(self) -> dict:
        pool = []
        for a in catalog.ARCHETYPES:
            pool.extend([a] * a["weight"])
        return self.rng.choice(pool)

    def _gen_customers(self, locations: list[Location]) -> list[CustomerCtx]:
        customers: list[CustomerCtx] = []
        for i in range(1, self.num_customers + 1):
            arch = self._weighted_archetype()
            loc = self.rng.choice(locations)
            first = self.rng.choice(catalog.FIRST_NAMES)
            last = self.rng.choice(catalog.LAST_NAMES)
            onboard = self.now - timedelta(days=self.rng.randint(180, 1400))
            cust = Customer(
                id=gen_uuid(), customer_ref=f"CUST-{i:05d}",
                full_name=f"{first} {last}", customer_type=arch["type"],
                tier=arch["type"], risk_classification="low",
                onboarding_date=onboard, status="active",
                preferred_channel="mobile" if arch["device"] == "mobile" else "web",
                region=loc.city,
                email=f"{first.lower()}.{last.lower()}{i}@example.com",
            )
            ctx = CustomerCtx(model=cust, profile=arch, location=loc)

            # accounts
            for j, atype in enumerate(arch["acct_types"][: arch["accounts"]]):
                bal = round(self.rng.uniform(*arch["balance"]), 2)
                acct = Account(
                    id=gen_uuid(), account_number=f"{i:05d}{j:02d}{self.rng.randint(1000,9999)}",
                    customer_id=cust.id, account_type=atype, current_balance=bal,
                    tier=arch["type"], opened_at=onboard,
                )
                ctx.accounts.append(acct)

            # trusted devices
            n_dev = 1 if arch["device"] == "mobile" else self.rng.randint(1, 2)
            for _ in range(n_dev):
                os_, br, mfr = self.rng.choice(catalog.DEVICE_POOL[arch["device"]])
                dev = Device(
                    id=gen_uuid(), fingerprint=f"dev-{gen_uuid()[:12]}",
                    os=os_, browser=br, manufacturer=mfr, category=arch["device"],
                    first_seen=onboard, last_seen=self.now, trust_score=0.9,
                )
                ctx.devices.append(dev)

            # home IP
            isp = self.rng.choice(catalog.DOMESTIC_ISPS)
            octet = self.rng.randint(2, 254)
            ip = IPAddress(
                id=gen_uuid(), address=f"49.{self.rng.randint(32,47)}.{self.rng.randint(1,254)}.{octet}",
                country=loc.country, city=loc.city, isp=isp,
                reputation_score=0.85, first_seen=onboard, last_seen=self.now,
                location_id=loc.id,
            )
            ctx.home_ip = ip
            ctx.amt_mean = self.rng.uniform(arch["txn"][0] * 1.5, arch["txn"][1] * 0.5)

            self.session.add(cust)
            self.session.add_all(ctx.accounts + ctx.devices + [ip])
            customers.append(ctx)
        return customers

    def _gen_baseline_history(self) -> None:
        """Months of normal behaviour per customer -> sessions, auth, txns, ledger."""
        ctx = self.ctx
        assert ctx is not None
        for c in ctx.customers:
            arch = c.profile
            for day in range(self.baseline_days, 0, -1):
                # is the customer active this day?
                if ctx.rng.random() > min(0.95, arch["per_day"]):
                    if arch["per_day"] < 1 and ctx.rng.random() > arch["per_day"]:
                        continue
                n_txn = max(1, round(ctx.rng.gauss(arch["per_day"], arch["per_day"] * 0.4)))
                n_txn = min(n_txn, 8)
                hour = ctx.rng.choice(arch["hours"])
                base_dt = self.now - timedelta(days=day)
                start = base_dt.replace(hour=hour, minute=ctx.rng.randint(0, 59),
                                        second=ctx.rng.randint(0, 59), microsecond=0)
                self._emit_normal_session(c, start, n_txn)

    def _emit_normal_session(self, c: CustomerCtx, start: datetime, n_txn: int) -> None:
        ctx = self.ctx
        assert ctx is not None
        dev = ctx.rng.choice(c.devices)
        ip = c.home_ip
        auth_ep = ctx.endpoints[ctx.rng.choice(catalog.AUTH_ENDPOINT_REFS)]
        sref = f"sess-{gen_uuid()[:16]}"

        # occasional benign failure then success
        if ctx.rng.random() < 0.06:
            self._auth(c, dev, ip, auth_ep, start - timedelta(seconds=40),
                       AuthResult.FAILURE, sref)
        self._auth(c, dev, ip, auth_ep, start, AuthResult.SUCCESS, sref)

        bs = BankSession(
            id=gen_uuid(), session_ref=sref, customer_id=c.model.id,
            account_id=c.accounts[0].id, device_id=dev.id, ip_id=ip.id,
            start_time=start, end_time=start + timedelta(minutes=ctx.rng.randint(2, 25)),
            duration_seconds=ctx.rng.randint(120, 1500), status="closed",
            confidence=0.9, auth_strength="mfa" if ctx.rng.random() < 0.5 else "password",
        )
        ctx.bank_sessions.append(bs)

        for k in range(n_txn):
            self._txn(c, dev, ip, sref, start + timedelta(minutes=2 + k * 3))

    def _auth(self, c, dev, ip, ep, when, result, sref) -> None:
        ctx = self.ctx
        etype = EventType.LOGIN_SUCCESS if result == AuthResult.SUCCESS else EventType.LOGIN_FAILURE
        ctx.auth_events.append(AuthEvent(
            event_time=when, result=result, method="mfa" if ctx.rng.random() < 0.4 else "password",
            customer_id=c.model.id, account_id=c.accounts[0].id, device_id=dev.id,
            ip_id=ip.id, location_id=c.location.id, session_ref=sref, endpoint_id=ep.id,
            browser=dev.browser, meta={},
        ))
        ctx.add_ledger(
            event_type=etype, event_category="authentication", event_source="auth-service",
            event_time=when, customer_id=c.model.id, account_id=c.accounts[0].id,
            device_id=dev.id, ip_id=ip.id, session_ref=sref, endpoint_id=ep.id,
            payload={"result": result, "city": c.location.city, "country": c.location.country},
        )

    def _txn(self, c, dev, ip, sref, when) -> None:
        from app.models import Transaction
        ctx = self.ctx
        r = ctx.rng.random()
        cum, cat, etype = 0.0, "transfer", EventType.TRANSFER
        for name, mapped, w in catalog.TXN_CATEGORIES:
            cum += w
            if r <= cum:
                cat = name
                etype = {
                    "transfer": EventType.TRANSFER, "bill_payment": EventType.BILL_PAYMENT,
                    "card_payment": EventType.CARD_PAYMENT, "atm_withdrawal": EventType.ATM_WITHDRAWAL,
                    "subscription": EventType.BILL_PAYMENT, "investment": EventType.TRANSFER,
                }[name]
                break
        amount = round(min(max(c.amt_mean * ctx.rng.uniform(0.25, 2.3),
                               c.profile["txn"][0]), c.profile["txn"][1]), 2)
        acct = ctx.rng.choice(c.accounts)
        ep = ctx.endpoints[ctx.rng.choice(catalog.TXN_ENDPOINT_REFS)]
        txn_ref = f"TXN-{when:%y%m%d}-{gen_uuid()[:10]}"
        ctx.transactions.append(Transaction(
            txn_ref=txn_ref, event_time=when, source_account_id=acct.id,
            customer_id=c.model.id, session_ref=sref, device_id=dev.id, ip_id=ip.id,
            endpoint_id=ep.id, location_id=c.location.id, amount=amount, category=cat,
            channel=c.profile["device"], status="completed", fraud_status="none", meta={},
        ))
        ctx.add_ledger(
            event_type=etype, event_category="transaction", event_source="txn-processing",
            event_time=when, customer_id=c.model.id, account_id=acct.id, device_id=dev.id,
            ip_id=ip.id, session_ref=sref, endpoint_id=ep.id, amount=amount,
            ref_table="transactions", ref_id=txn_ref,
            payload={"category": cat, "channel": c.profile["device"]},
        )

    # ---------------------------------------------------------------- persistence
    def _flush_all(self) -> None:
        ctx = self.ctx
        assert ctx is not None
        # Commit any pending unit-of-work entities (e.g. scenario attacker devices,
        # IPs, admin customer, vulnerabilities) FIRST, in dependency order, so the
        # bulk-inserted event children below always find their parent rows.
        self.session.commit()
        if ctx.bank_sessions:
            self.session.bulk_save_objects(ctx.bank_sessions)
            ctx.bank_sessions.clear()
        if ctx.auth_events:
            self.session.bulk_save_objects(ctx.auth_events)
            ctx.auth_events.clear()
        if ctx.transactions:
            self.session.bulk_save_objects(ctx.transactions)
            ctx.transactions.clear()
        if ctx.ledger:
            self.session.bulk_save_objects(ctx.ledger)
            ctx.ledger.clear()
        self.session.commit()
