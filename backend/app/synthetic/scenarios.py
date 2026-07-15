"""Deterministic investigation scenarios injected on top of the baseline history.

Each scenario demonstrates one ARGUS capability and is designed so that the intelligence
engines (Watchtower forward, Blast Radius retrospective) reconstruct it from evidence —
nothing here writes an Investigation row directly.
"""
from __future__ import annotations

from datetime import timedelta

from app.core.logging import get_logger
from app.models import Customer, Device, IPAddress, Transaction, Vulnerability
from app.models.base import gen_uuid
from app.models.enums import (
    AccountType,
    CustomerType,
    DisclosureType,
    EventType,
    FraudStatus,
)

logger = get_logger(__name__)


def inject_all(ctx) -> dict:
    return {
        "account_takeover": account_takeover(ctx),
        "credential_stuffing": credential_stuffing(ctx),
        "insider_misuse": insider_misuse(ctx),
        "api_abuse": api_abuse(ctx),
        "weak_cipher_disclosure": weak_cipher_disclosure(ctx),
        "quantum_hndl": quantum_hndl(ctx),
    }


# ---------------------------------------------------------------- helpers
def _attacker_ip(ctx, isp_pool) -> IPAddress:
    loc = ctx.rng.choice(ctx.foreign_locations)
    ip = IPAddress(
        id=gen_uuid(),
        address=f"{ctx.rng.randint(45,213)}.{ctx.rng.randint(1,254)}.{ctx.rng.randint(1,254)}.{ctx.rng.randint(1,254)}",
        country=loc.country, city=loc.city, isp=ctx.rng.choice(isp_pool),
        reputation_score=0.08, first_seen=ctx.now, last_seen=ctx.now, location_id=loc.id,
    )
    ctx.session.add(ip)
    return ip, loc


def _pick_high_value_customer(ctx):
    ranked = sorted(ctx.customers, key=lambda c: c.amt_mean, reverse=True)
    for c in ranked:
        if c.profile["type"] in (CustomerType.PREMIUM, CustomerType.HNWI, CustomerType.CORPORATE):
            return c
    return ranked[0]


# ---------------------------------------------------------------- S1
def account_takeover(ctx) -> dict:
    """Trusted customer, new device, foreign country, then a transfer ~15x their norm."""
    from app.synthetic import catalog

    c = _pick_high_value_customer(ctx)
    ip, loc = _attacker_ip(ctx, catalog.HOSTING_ISPS)
    dev = Device(id=gen_uuid(), fingerprint=f"dev-atk-{gen_uuid()[:10]}",
                 os="Windows 10", browser="Chrome 121", manufacturer="Unknown",
                 category="desktop", first_seen=ctx.now, last_seen=ctx.now, trust_score=0.02)
    ctx.session.add(dev)

    t0 = ctx.now - timedelta(hours=6)
    auth_ep = ctx.endpoints["EP-AUTH-01"]
    sref = f"sess-atk-{gen_uuid()[:12]}"

    # 2 failed then success from the foreign device
    for i in range(2):
        ctx.add_ledger(event_type=EventType.LOGIN_FAILURE, event_category="authentication",
                       event_source="auth-service", event_time=t0 + timedelta(minutes=i),
                       customer_id=c.model.id, account_id=c.accounts[0].id, device_id=dev.id,
                       ip_id=ip.id, session_ref=sref, endpoint_id=auth_ep.id, severity="medium",
                       payload={"result": "failure", "country": loc.country, "city": loc.city,
                                "new_device": True})
    ctx.add_ledger(event_type=EventType.LOGIN_SUCCESS, event_category="authentication",
                   event_source="auth-service", event_time=t0 + timedelta(minutes=3),
                   customer_id=c.model.id, account_id=c.accounts[0].id, device_id=dev.id,
                   ip_id=ip.id, session_ref=sref, endpoint_id=auth_ep.id, severity="high",
                   payload={"result": "success", "country": loc.country, "city": loc.city,
                            "new_device": True})

    # high-value transfer to an external account
    amount = round(c.amt_mean * ctx.rng.uniform(12, 18), 2)
    pay_ep = ctx.endpoints["EP-PAY-01"]
    when = t0 + timedelta(minutes=9)
    txn_ref = f"TXN-ATO-{gen_uuid()[:10]}"
    ctx.transactions.append(Transaction(
        txn_ref=txn_ref, event_time=when, source_account_id=c.accounts[0].id,
        dest_external="Beneficiary IBAN ****-9921 (new payee)", customer_id=c.model.id,
        session_ref=sref, device_id=dev.id, ip_id=ip.id, endpoint_id=pay_ep.id,
        location_id=loc.id, amount=amount, category="wire", channel="web",
        status="pending", fraud_status=FraudStatus.SUSPECTED,
        meta={"new_payee": True, "foreign_origin": True}))
    ctx.add_ledger(event_type=EventType.WIRE, event_category="transaction",
                   event_source="txn-processing", event_time=when, customer_id=c.model.id,
                   account_id=c.accounts[0].id, device_id=dev.id, ip_id=ip.id,
                   session_ref=sref, endpoint_id=pay_ep.id, amount=amount, severity="critical",
                   ref_table="transactions", ref_id=txn_ref,
                   payload={"category": "wire", "new_payee": True, "country": loc.country})

    return {"customer_ref": c.model.customer_ref, "customer": c.model.full_name,
            "amount": amount, "amt_mean": round(c.amt_mean, 2), "country": loc.country,
            "device": dev.fingerprint, "session_ref": sref}


# ---------------------------------------------------------------- S2
def credential_stuffing(ctx) -> dict:
    from app.synthetic import catalog

    ip, loc = _attacker_ip(ctx, catalog.HOSTING_ISPS)
    auth_ep = ctx.endpoints["EP-AUTH-01"]
    t0 = ctx.now - timedelta(days=1, hours=2)
    victims = ctx.rng.sample(ctx.customers, min(40, len(ctx.customers)))
    fails = 0
    for i, c in enumerate(victims):
        for _ in range(ctx.rng.randint(3, 8)):
            ctx.add_ledger(event_type=EventType.LOGIN_FAILURE, event_category="authentication",
                           event_source="auth-service",
                           event_time=t0 + timedelta(seconds=fails * 7),
                           customer_id=c.model.id, account_id=c.accounts[0].id,
                           ip_id=ip.id, endpoint_id=auth_ep.id, severity="medium",
                           payload={"result": "failure", "credential_stuffing": True,
                                    "country": loc.country})
            fails += 1

    # one account falls; small probe then a larger transfer
    victim = victims[0]
    sref = f"sess-cs-{gen_uuid()[:12]}"
    t1 = t0 + timedelta(minutes=30)
    ctx.add_ledger(event_type=EventType.LOGIN_SUCCESS, event_category="authentication",
                   event_source="auth-service", event_time=t1, customer_id=victim.model.id,
                   account_id=victim.accounts[0].id, ip_id=ip.id, session_ref=sref,
                   endpoint_id=auth_ep.id, severity="high",
                   payload={"result": "success", "after_bruteforce": True})
    pay_ep = ctx.endpoints["EP-PAY-01"]
    for k, mult in enumerate([0.02, 0.05, 6.0]):
        amt = round(max(victim.amt_mean * mult, 50), 2)
        ref = f"TXN-CS-{gen_uuid()[:8]}"
        when = t1 + timedelta(minutes=2 + k * 2)
        ctx.transactions.append(Transaction(
            txn_ref=ref, event_time=when, source_account_id=victim.accounts[0].id,
            dest_external="Mule account ****-4471", customer_id=victim.model.id,
            session_ref=sref, ip_id=ip.id, endpoint_id=pay_ep.id, location_id=loc.id,
            amount=amt, category="transfer", channel="api",
            status="completed" if k < 2 else "pending",
            fraud_status=FraudStatus.SUSPECTED, meta={"probe": k < 2}))
        ctx.add_ledger(event_type=EventType.TRANSFER, event_category="transaction",
                       event_source="txn-processing", event_time=when,
                       customer_id=victim.model.id, account_id=victim.accounts[0].id,
                       ip_id=ip.id, session_ref=sref, endpoint_id=pay_ep.id, amount=amt,
                       severity="high" if k == 2 else "low", ref_table="transactions", ref_id=ref,
                       payload={"probe": k < 2})

    return {"attacker_ip": ip.address, "country": loc.country, "failed_attempts": fails,
            "victims_targeted": len(victims), "compromised_customer": victim.model.customer_ref}


# ---------------------------------------------------------------- S3
def insider_misuse(ctx) -> dict:
    """Internal admin accesses an unusual number of customer records off-hours."""
    admin = Customer(id=gen_uuid(), customer_ref="EMP-ADMIN-07",
                     full_name="Internal Ops — R. Menon", customer_type=CustomerType.ADMIN,
                     tier="privileged", risk_classification="elevated",
                     onboarding_date=ctx.now - timedelta(days=900), status="active",
                     preferred_channel="web", region="New Delhi")
    ctx.session.add(admin)
    admin_ip = IPAddress(id=gen_uuid(), address="10.12.7.44", country="India", city="New Delhi",
                         isp="Internal Corp LAN", reputation_score=0.6,
                         first_seen=ctx.now - timedelta(days=900), last_seen=ctx.now)
    ctx.session.add(admin_ip)
    admin_ep = ctx.endpoints["EP-ADMIN-01"]
    custdb_ep = ctx.endpoints["EP-CUSTDB-01"]

    t0 = (ctx.now - timedelta(days=2)).replace(hour=2, minute=13)  # 02:13 — off hours
    sref = f"sess-ins-{gen_uuid()[:12]}"
    ctx.add_ledger(event_type=EventType.LOGIN_SUCCESS, event_category="authentication",
                   event_source="admin-console", event_time=t0, customer_id=admin.id,
                   ip_id=admin_ip.id, session_ref=sref, endpoint_id=admin_ep.id, severity="low",
                   payload={"result": "success", "off_hours": True})
    n_records = ctx.rng.randint(180, 260)
    for i in range(60):  # 60 bulk-access events covering ~n_records records
        ctx.add_ledger(event_type=EventType.RECORD_ACCESS, event_category="operational",
                       event_source="customer-db", event_time=t0 + timedelta(seconds=i * 25),
                       customer_id=admin.id, session_ref=sref, endpoint_id=custdb_ep.id,
                       severity="medium",
                       payload={"records": ctx.rng.randint(2, 6), "bulk_export": i > 40,
                                "off_hours": True})
    return {"admin_ref": admin.customer_ref, "records_accessed": n_records,
            "endpoint": custdb_ep.endpoint_ref, "time": t0.isoformat()}


# ---------------------------------------------------------------- S4
def api_abuse(ctx) -> dict:
    """Legitimate credentials, but request velocity far exceeds the endpoint baseline."""
    ip, loc = _attacker_ip(ctx, ["Cloud Scraper Net", "Anonymous Proxy"])
    api_ep = ctx.endpoints["EP-PAY-01"]
    t0 = ctx.now - timedelta(hours=12)
    sref = f"sess-api-{gen_uuid()[:12]}"
    n = 300
    for i in range(n):
        ctx.add_ledger(event_type=EventType.API_REQUEST, event_category="operational",
                       event_source="api-gateway",
                       event_time=t0 + timedelta(milliseconds=i * 400),
                       ip_id=ip.id, session_ref=sref, endpoint_id=api_ep.id,
                       severity="medium",
                       payload={"client": "unregistered", "rate_per_min": 150,
                                "country": loc.country})
    return {"endpoint": api_ep.endpoint_ref, "requests": n, "attacker_ip": ip.address,
            "country": loc.country}


# ---------------------------------------------------------------- S5
def weak_cipher_disclosure(ctx) -> dict:
    """Sweet32 (3DES/CBC) disclosed on the legacy payments processor -> Blast Radius.

    The baseline already routed real transactions through EP-PAY-LEGACY, so
    reconstruction over the exposure window finds genuine historical exposure.
    """
    ep = ctx.endpoints["EP-PAY-LEGACY"]
    window_start = ctx.now - timedelta(days=ctx.rng.randint(140, 200))
    vuln = Vulnerability(
        id=gen_uuid(), vuln_ref="CVE-2016-2183", disclosure_type=DisclosureType.WEAK_CIPHER,
        title="Sweet32 — 3DES/DES CBC birthday-bound collision on legacy payments TLS",
        description=("The Legacy Payments Processor negotiated TLS 1.0 with 3DES-CBC. "
                     "Sweet32 permits recovery of plaintext from long-lived encrypted "
                     "sessions. All cardholder transactions routed through this endpoint "
                     "during the exposure window are considered potentially exposed."),
        severity="high", cvss=7.5, affected_endpoint_id=ep.id, affected_algorithm="3DES-CBC",
        exposure_window_start=window_start, exposure_window_end=None,
        published_at=ctx.now - timedelta(hours=8), disclosed_at=ctx.now - timedelta(hours=8),
        remediation_deadline=ctx.now + timedelta(days=7), patch_status="unpatched",
    )
    ctx.session.add(vuln)
    ep.deprecated_at = None
    return {"vuln_ref": vuln.vuln_ref, "endpoint": ep.endpoint_ref,
            "window_start": window_start.isoformat(), "algorithm": "3DES-CBC"}


# ---------------------------------------------------------------- S6
def quantum_hndl(ctx) -> dict:
    """Harvest-now-decrypt-later: RSA-2048 key exchange on the encryption gateway.

    Historical high-value transactions are routed through EP-CRYPTO-01 during the window
    so Blast Radius can reconstruct the population whose material could be decrypted later.
    """
    ep = ctx.endpoints["EP-CRYPTO-01"]
    window_start = ctx.now - timedelta(days=ctx.rng.randint(220, 300))
    high_value = [c for c in ctx.customers if c.amt_mean > 200_000]
    if not high_value:
        high_value = sorted(ctx.customers, key=lambda c: c.amt_mean, reverse=True)[:8]

    injected = 0
    for c in high_value:
        for _ in range(ctx.rng.randint(4, 9)):
            days_ago = ctx.rng.randint(1, (ctx.now - window_start).days)
            when = ctx.now - timedelta(days=days_ago, hours=ctx.rng.randint(0, 23))
            amt = round(c.amt_mean * ctx.rng.uniform(0.8, 3.0), 2)
            ref = f"TXN-QC-{gen_uuid()[:8]}"
            ctx.transactions.append(Transaction(
                txn_ref=ref, event_time=when, source_account_id=c.accounts[0].id,
                customer_id=c.model.id, endpoint_id=ep.id, location_id=c.location.id,
                amount=amt, category="transfer", channel=c.profile["device"],
                status="completed", fraud_status="none",
                meta={"key_exchange": "RSA-2048", "sensitive": True}))
            ctx.add_ledger(event_type=EventType.TRANSFER, event_category="transaction",
                           event_source="crypto-gateway", event_time=when, customer_id=c.model.id,
                           account_id=c.accounts[0].id, endpoint_id=ep.id, amount=amt,
                           ref_table="transactions", ref_id=ref,
                           payload={"key_exchange": "RSA-2048", "sensitive": True})
            injected += 1

    vuln = Vulnerability(
        id=gen_uuid(), vuln_ref="PQC-ADVISORY-2026-01",
        disclosure_type=DisclosureType.QUANTUM_HNDL,
        title="Harvest-Now-Decrypt-Later exposure — RSA-2048 key exchange on encryption gateway",
        description=("The Encryption Gateway used RSA-2048 for key establishment protecting "
                     "sensitive customer material. Under a harvest-now-decrypt-later threat "
                     "model, ciphertext captured today may be decryptable once a "
                     "cryptographically-relevant quantum computer exists. All sensitive "
                     "material routed through this gateway during the window is at risk."),
        severity="critical", cvss=8.1, affected_endpoint_id=ep.id, affected_algorithm="RSA-2048",
        exposure_window_start=window_start, exposure_window_end=None,
        published_at=ctx.now - timedelta(hours=3), disclosed_at=ctx.now - timedelta(hours=3),
        remediation_deadline=ctx.now + timedelta(days=30), patch_status="in_progress",
    )
    ctx.session.add(vuln)
    return {"vuln_ref": vuln.vuln_ref, "endpoint": ep.endpoint_ref,
            "window_start": window_start.isoformat(), "sensitive_txns": injected,
            "customers_at_risk": len(high_value), "algorithm": "RSA-2048"}
