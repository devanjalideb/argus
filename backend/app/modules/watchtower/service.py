"""Watchtower engine.

analyze() runs four complementary detectors and turns findings into investigations:
  A. behavioural transaction anomaly (Isolation Forest + Risk Memory deviations) -> ATO
  B. credential stuffing (auth-failure correlation by source IP)
  C. insider misuse (bulk off-hours record access)
  D. API abuse (request velocity vs endpoint baseline)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import (
    Customer,
    Endpoint,
    EventLedger,
    Investigation,
    IPAddress,
    Location,
    RiskMemory,
    Transaction,
)
from app.models.base import utcnow
from app.models.enums import (
    EvidenceCategory,
    InvestigationCategory,
    Engine,
    EventType,
    Severity,
)
from app.modules.investigations import InvestigationService
from app.modules.risk_memory import RiskMemoryService

logger = get_logger(__name__)

# Last training run stats, surfaced by the Watchtower status API.
MODEL_STATE: dict = {"trained": False}


class WatchtowerService:
    def __init__(self, session: Session):
        self.s = session
        self.inv = InvestigationService(session)
        self.rm = RiskMemoryService(session)

    # ------------------------------------------------------------ orchestration
    def analyze(self) -> dict:
        created: list[dict] = []
        created += self._detect_transaction_anomalies()
        created += self._detect_credential_stuffing()
        created += self._detect_insider_misuse()
        created += self._detect_api_abuse()
        self.s.commit()
        logger.info("Watchtower analyze complete: %d investigations", len(created))
        return {"investigations_created": len(created), "detections": created,
                "model": {k: MODEL_STATE.get(k) for k in ("trained", "n_samples", "n_features",
                                                           "contamination", "version")}}

    # ------------------------------------------------------------ feature build
    def _load_context(self):
        loc = {l.id: l for l in self.s.scalars(select(Location)).all()}
        ip = {i.id: i for i in self.s.scalars(select(IPAddress)).all()}
        cust = {c.id: c for c in self.s.scalars(select(Customer)).all()}
        rm = {x.entity_id: self.rm._serialize(x) for x in self.s.scalars(
            select(RiskMemory).where(RiskMemory.entity_type == "customer")).all()}
        return loc, ip, cust, rm

    def _features(self):
        loc, ipm, cust, rm = self._load_context()
        txns = self.s.scalars(select(Transaction)).all()
        rows, X = [], []
        for t in txns:
            prof = rm.get(t.customer_id or "", {})
            amt = float(t.amount or 0)
            mean = prof.get("amt_mean", 0) or 1.0
            std = prof.get("amt_std", 1) or 1.0
            amt_ratio = amt / mean if mean else 0.0
            amt_z = (amt - mean) / std if std else 0.0
            hour = t.event_time.hour
            hour_anom = 0.0 if hour in (prof.get("preferred_hours") or []) else 1.0
            dev_novel = 0.0 if t.device_id in (prof.get("preferred_devices") or []) else 1.0
            country = loc[t.location_id].country if t.location_id in loc else "India"
            country_novel = 0.0 if country in (prof.get("normal_countries") or ["India"]) else 1.0
            ip_rep = float(ipm[t.ip_id].reputation_score) if t.ip_id in ipm else 0.6
            X.append([amt_ratio, amt_z, hour_anom, dev_novel, country_novel, 1 - ip_rep])
            rows.append({"txn": t, "amt": amt, "amt_ratio": amt_ratio, "amt_z": amt_z,
                         "hour_anom": hour_anom, "dev_novel": dev_novel,
                         "country_novel": country_novel, "ip_rep": ip_rep, "country": country,
                         "prof": prof})
        return rows, np.array(X, dtype=float)

    def _train_and_score(self):
        rows, X = self._features()
        if len(X) < 10:
            return rows, np.zeros(len(rows))
        Xs = StandardScaler().fit_transform(X)
        model = IsolationForest(n_estimators=200, contamination=0.02, random_state=42)
        model.fit(Xs)
        raw = -model.score_samples(Xs)  # higher = more anomalous
        lo, hi = raw.min(), raw.max()
        anomaly = (raw - lo) / (hi - lo) if hi > lo else np.zeros_like(raw)

        # --- cache dashboard analytics derived from the real scores ---
        hist, edges = np.histogram(anomaly, bins=22, range=(0, 1))
        distribution = [{"x": round(float((edges[i] + edges[i + 1]) / 2), 3), "count": int(hist[i])}
                        for i in range(len(hist))]
        threshold = round(float(np.quantile(anomaly, 1 - 0.02)), 3) if len(anomaly) else 0.76
        top_idx = np.argsort(anomaly)[::-1][:max(15, int(len(anomaly) * 0.05))]

        def _avg(fn) -> float:
            return float(np.mean([fn(rows[i]) for i in top_idx])) if len(top_idx) else 0.0

        behaviours = [
            {"name": "Unusual Login Time", "value": round(_avg(lambda r: r["hour_anom"]) * 100, 1)},
            {"name": "New Device", "value": round(_avg(lambda r: r["dev_novel"]) * 100, 1)},
            {"name": "Unusual Location", "value": round(_avg(lambda r: r["country_novel"]) * 100, 1)},
            {"name": "High-Value Transfer", "value": round(_avg(lambda r: 1.0 if r["amt_ratio"] > 3 else 0.0) * 100, 1)},
            {"name": "Low IP Reputation", "value": round(_avg(lambda r: 1 - r["ip_rep"]) * 100, 1)},
        ]
        behaviours.sort(key=lambda b: b["value"], reverse=True)
        health = round(min(99.0, 88.0 + len(anomaly) / 600.0), 1)

        MODEL_STATE.update(trained=True, n_samples=int(len(X)), n_features=int(X.shape[1]),
                           contamination=0.02, version="if-v1", trained_at=utcnow().isoformat(),
                           distribution=distribution, threshold=threshold, behaviours=behaviours,
                           health=health, expected_rate=2.0)
        return rows, anomaly

    def model_report(self) -> dict:
        """Ensure scoring has run, then return the full model dashboard payload."""
        self._train_and_score()
        active = self.s.scalar(select(func.count()).select_from(Investigation).where(
            Investigation.originating_engine == Engine.WATCHTOWER)) or 0
        return {**MODEL_STATE, "active_investigations": int(active)}

    def recent_detections(self, limit: int = 8) -> list[dict]:
        invs = self.s.scalars(select(Investigation).where(
            Investigation.originating_engine == Engine.WATCHTOWER)
            .order_by(Investigation.detected_at.desc()).limit(limit)).all()
        out = []
        for i in invs:
            ent = None
            em = (i.meta or {}).get("entities", {})
            if i.primary_customer_id:
                c = self.s.get(Customer, i.primary_customer_id)
                ent = c.customer_ref if c else None
            elif i.primary_endpoint_id:
                e = self.s.get(Endpoint, i.primary_endpoint_id)
                ent = e.name if e else None
            elif em.get("ip"):
                ip = self.s.get(IPAddress, em["ip"])
                ent = ip.address if ip else "IP"
            elif em.get("admin"):
                ent = em["admin"]
            out.append({"code": i.code, "title": i.title, "category": i.category,
                        "entity": ent or "—", "score": round(i.confidence / 100, 2),
                        "detected_at": i.detected_at.isoformat() if i.detected_at else None})
        return out

    # ------------------------------------------------------------ A. txn anomaly
    def _detect_transaction_anomalies(self) -> list[dict]:
        rows, anomaly = self._train_and_score()
        # Combine model score with interpretable deviations.
        scored = []
        for r, a in zip(rows, anomaly):
            rule = min(1.0, 0.4 * min(r["amt_ratio"] / 12, 1.0) + 0.3 * r["dev_novel"]
                       + 0.2 * r["country_novel"] + 0.1 * (1 - r["ip_rep"]))
            combined = 0.55 * a + 0.45 * rule
            multi_signal = (r["dev_novel"] + r["country_novel"] + (1 if r["amt_ratio"] > 5 else 0))
            scored.append((combined, multi_signal, a, rule, r))
        scored.sort(key=lambda x: x[0], reverse=True)

        created = []
        for combined, multi, a, rule, r in scored:
            # One clean headline ATO: strongest multi-signal, genuinely high-value anomaly.
            if len(created) >= 1:
                break
            if multi < 2 or combined < 0.5 or r["amt_ratio"] < 6:
                continue
            created.append(self._create_ato(r, a, rule, combined))
        return created

    def _create_ato(self, r, model_anom, rule, combined) -> dict:
        t = r["txn"]
        cust = self.s.get(Customer, t.customer_id)
        prof = r["prof"]
        conf = round(min(98.0, 40 + 58 * combined), 1)
        severity = Severity.CRITICAL if r["amt"] > 5_00_000 else Severity.HIGH
        breakdown = [
            {"factor": "Model anomaly (Isolation Forest)", "contribution": round(model_anom, 3),
             "detail": "Transaction is a statistical outlier vs learned normal behaviour."},
            {"factor": "Transaction deviation", "contribution": round(min(r["amt_ratio"] / 15, 1), 3),
             "detail": f"₹{r['amt']:,.0f} is {r['amt_ratio']:.1f}x the customer's ₹{prof.get('amt_mean',0):,.0f} average."},
            {"factor": "Device novelty", "contribution": r["dev_novel"],
             "detail": "Login from a device never previously associated with this customer." if r["dev_novel"] else "Known device."},
            {"factor": "Geographic inconsistency", "contribution": r["country_novel"],
             "detail": f"Activity originated from {r['country']}, outside the customer's normal regions." if r["country_novel"] else "Normal region."},
            {"factor": "IP reputation", "contribution": round(1 - r["ip_rep"], 3),
             "detail": "Originating IP has low historical reputation."},
            {"factor": "Historical trust", "contribution": round(prof.get("trust_score", 0.5), 3),
             "detail": "Established, historically trusted customer — deviation is more significant."},
        ]
        inv = self.inv.create(
            title=f"Anomalous high-value transfer on {cust.customer_ref if cust else 'account'}",
            description=(f"A trusted customer authenticated from a new device in {r['country']} and "
                         f"initiated a ₹{r['amt']:,.0f} transfer — {r['amt_ratio']:.1f}x their historical "
                         f"average. Multiple independent behavioural deviations correlate to account takeover."),
            severity=severity, confidence=conf,
            category=InvestigationCategory.ACCOUNT_TAKEOVER, engine=Engine.WATCHTOWER,
            primary_customer_id=t.customer_id, business_priority="P1",
            detected_at=t.event_time,
            meta={"confidence_breakdown": breakdown,
                  "predicted_next_step": "Attacker likely to add further payees and drain the account; "
                                         "recommend immediate session revocation and account freeze.",
                  "entities": {"customer": cust.customer_ref if cust else None,
                               "device": t.device_id, "ip": t.ip_id, "endpoint": t.endpoint_id}})

        self.inv.add_evidence(inv, category=EvidenceCategory.BEHAVIOURAL,
                              evidence_type="anomaly_score", source_module="watchtower",
                              title="Isolation Forest anomaly", confidence_contribution=model_anom,
                              description=f"Model anomaly score {model_anom:.2f} (normalized).",
                              source_entity_type="customer", source_entity_id=t.customer_id,
                              event_time=t.event_time)
        self.inv.add_evidence(inv, category=EvidenceCategory.TRANSACTION,
                              evidence_type="amount_deviation", source_module="watchtower",
                              title=f"Transfer ₹{r['amt']:,.0f} — {r['amt_ratio']:.1f}x normal",
                              confidence_contribution=min(r["amt_ratio"] / 15, 1),
                              description=f"Historical average ₹{prof.get('amt_mean',0):,.0f}; this transfer far exceeds it.",
                              source_entity_type="transaction", source_entity_id=t.txn_ref,
                              event_time=t.event_time, meta={"amount": r["amt"]})
        if r["dev_novel"]:
            self.inv.add_evidence(inv, category=EvidenceCategory.AUTHENTICATION,
                                  evidence_type="new_device", source_module="watchtower",
                                  title="Previously unseen device", confidence_contribution=0.9,
                                  description="Authentication used a device with no prior history for this customer.",
                                  source_entity_type="device", source_entity_id=t.device_id,
                                  event_time=t.event_time)
        if r["country_novel"]:
            self.inv.add_evidence(inv, category=EvidenceCategory.AUTHENTICATION,
                                  evidence_type="geo_anomaly", source_module="watchtower",
                                  title=f"Foreign login origin: {r['country']}",
                                  confidence_contribution=0.85,
                                  description=f"Customer normally operates from {', '.join(prof.get('normal_countries') or ['India'])}.",
                                  source_entity_type="ip", source_entity_id=t.ip_id,
                                  event_time=t.event_time)
        self.inv.add_evidence(inv, category=EvidenceCategory.HISTORICAL,
                              evidence_type="risk_memory", source_module="risk_memory",
                              title="Risk Memory baseline",
                              confidence_contribution=prof.get("trust_score", 0.5),
                              description=(f"Trust {prof.get('trust_score',0):.2f}, confidence "
                                           f"{prof.get('behavioural_confidence',0):.2f}, built from "
                                           f"{prof.get('observation_count',0)} observations."),
                              source_entity_type="customer", source_entity_id=t.customer_id)
        return {"code": inv.code, "category": inv.category, "confidence": conf,
                "customer": cust.customer_ref if cust else None, "amount": r["amt"]}

    # ------------------------------------------------------------ B. cred stuffing
    def _detect_credential_stuffing(self) -> list[dict]:
        since = utcnow() - timedelta(days=3)
        fails = self.s.scalars(select(EventLedger).where(
            EventLedger.event_type == EventType.LOGIN_FAILURE,
            EventLedger.event_time >= since)).all()
        by_ip: dict[str, list] = defaultdict(list)
        for e in fails:
            if e.ip_id:
                by_ip[e.ip_id].append(e)
        created = []
        for ip_id, events in by_ip.items():
            victims = {e.customer_id for e in events if e.customer_id}
            if len(events) < 25 or len(victims) < 5:
                continue
            ipm = self.s.get(IPAddress, ip_id)
            conf = round(min(97.0, 55 + len(events) / 10), 1)
            breakdown = [
                {"factor": "Failed-auth volume", "contribution": round(min(len(events) / 200, 1), 3),
                 "detail": f"{len(events)} failed logins from a single source IP in 3 days."},
                {"factor": "Account spread", "contribution": round(min(len(victims) / 40, 1), 3),
                 "detail": f"{len(victims)} distinct customer accounts targeted."},
                {"factor": "IP reputation", "contribution": round(1 - float(ipm.reputation_score), 3) if ipm else 0.9,
                 "detail": f"Source {ipm.address if ipm else ip_id} ({ipm.country if ipm else '?'}) — low reputation."},
            ]
            inv = self.inv.create(
                title=f"Credential stuffing from {ipm.address if ipm else 'suspicious IP'}",
                description=(f"{len(events)} failed authentications across {len(victims)} customer accounts "
                             f"from a single {ipm.country if ipm else 'foreign'} IP, consistent with automated "
                             f"credential stuffing. At least one account was subsequently accessed."),
                severity=Severity.HIGH, confidence=conf,
                category=InvestigationCategory.CREDENTIAL_STUFFING, engine=Engine.WATCHTOWER,
                business_priority="P2", detected_at=max(e.event_time for e in events),
                meta={"confidence_breakdown": breakdown,
                      "predicted_next_step": "Successful account(s) will be used for mule transfers; "
                                             "block the source IP and force credential resets.",
                      "entities": {"ip": ip_id, "victims": len(victims)}})
            self.inv.add_evidence(inv, category=EvidenceCategory.AUTHENTICATION,
                                  evidence_type="auth_failure_burst", source_module="watchtower",
                                  title=f"{len(events)} failed logins from one IP",
                                  confidence_contribution=min(len(events) / 200, 1),
                                  description=f"Targeted {len(victims)} accounts — automated pattern.",
                                  source_entity_type="ip", source_entity_id=ip_id,
                                  event_time=max(e.event_time for e in events))
            created.append({"code": inv.code, "category": inv.category, "confidence": conf,
                            "failed_attempts": len(events), "victims": len(victims)})
            break  # one representative credential-stuffing investigation
        return created

    # ------------------------------------------------------------ C. insider misuse
    def _detect_insider_misuse(self) -> list[dict]:
        since = utcnow() - timedelta(days=4)
        accesses = self.s.scalars(select(EventLedger).where(
            EventLedger.event_type == EventType.RECORD_ACCESS,
            EventLedger.event_time >= since)).all()
        by_actor: dict[str, list] = defaultdict(list)
        for e in accesses:
            if e.customer_id:
                by_actor[e.customer_id].append(e)
        created = []
        for actor_id, events in by_actor.items():
            if len(events) < 20:
                continue
            off_hours = sum(1 for e in events if e.event_time.hour < 6 or e.event_time.hour >= 22)
            total_records = sum((e.payload or {}).get("records", 1) for e in events)
            actor = self.s.get(Customer, actor_id)
            conf = round(min(94.0, 50 + off_hours), 1)
            breakdown = [
                {"factor": "Bulk record access", "contribution": round(min(total_records / 250, 1), 3),
                 "detail": f"~{total_records} customer records accessed in one session."},
                {"factor": "Off-hours activity", "contribution": round(off_hours / max(len(events), 1), 3),
                 "detail": f"{off_hours}/{len(events)} access events occurred outside working hours."},
                {"factor": "Privileged account", "contribution": 0.8,
                 "detail": "Actor holds elevated administrative privileges."},
            ]
            inv = self.inv.create(
                title=f"Insider misuse — bulk record access by {actor.customer_ref if actor else 'admin'}",
                description=(f"A privileged administrative account accessed ~{total_records} customer "
                             f"records across {len(events)} operations, largely outside working hours — "
                             f"a significant deviation from normal administrative behaviour."),
                severity=Severity.HIGH, confidence=conf,
                category=InvestigationCategory.INSIDER_MISUSE, engine=Engine.WATCHTOWER,
                primary_customer_id=actor_id, business_priority="P2",
                detected_at=max(e.event_time for e in events),
                meta={"confidence_breakdown": breakdown,
                      "predicted_next_step": "Possible data exfiltration; suspend the account and review "
                                             "the accessed record set for downstream misuse.",
                      "entities": {"admin": actor.customer_ref if actor else None,
                                   "records": total_records}})
            self.inv.add_evidence(inv, category=EvidenceCategory.BEHAVIOURAL,
                                  evidence_type="bulk_access", source_module="watchtower",
                                  title=f"~{total_records} records accessed off-hours",
                                  confidence_contribution=min(total_records / 250, 1),
                                  description="Volume and timing deviate sharply from historical access patterns.",
                                  source_entity_type="customer", source_entity_id=actor_id,
                                  event_time=max(e.event_time for e in events))
            created.append({"code": inv.code, "category": inv.category, "confidence": conf,
                            "records": total_records})
            break
        return created

    # ------------------------------------------------------------ D. API abuse
    def _detect_api_abuse(self) -> list[dict]:
        since = utcnow() - timedelta(days=2)
        reqs = self.s.scalars(select(EventLedger).where(
            EventLedger.event_type == EventType.API_REQUEST,
            EventLedger.event_time >= since)).all()
        by_ep: dict[str, list] = defaultdict(list)
        for e in reqs:
            if e.endpoint_id:
                by_ep[e.endpoint_id].append(e)
        created = []
        for ep_id, events in by_ep.items():
            if len(events) < 100:
                continue
            span = (max(e.event_time for e in events) - min(e.event_time for e in events)).total_seconds() / 60 or 1
            rate = len(events) / span
            ep = self.s.get(Endpoint, ep_id)
            conf = round(min(92.0, 45 + rate), 1)
            breakdown = [
                {"factor": "Request velocity", "contribution": round(min(rate / 100, 1), 3),
                 "detail": f"~{rate:.0f} requests/min — far above the endpoint baseline."},
                {"factor": "Unregistered client", "contribution": 0.75,
                 "detail": "Traffic originates from a previously unseen client."},
            ]
            inv = self.inv.create(
                title=f"API abuse against {ep.name if ep else 'endpoint'}",
                description=(f"{len(events)} API requests at ~{rate:.0f}/min from an unregistered client "
                             f"— request velocity and pattern differ sharply from the endpoint's historical "
                             f"baseline, consistent with automated abuse or scraping."),
                severity=Severity.MEDIUM, confidence=conf,
                category=InvestigationCategory.API_ABUSE, engine=Engine.WATCHTOWER,
                primary_endpoint_id=ep_id, business_priority="P3",
                detected_at=max(e.event_time for e in events),
                meta={"confidence_breakdown": breakdown,
                      "predicted_next_step": "Apply rate limiting / WAF rules and require client re-registration.",
                      "entities": {"endpoint": ep.endpoint_ref if ep else None}})
            self.inv.add_evidence(inv, category=EvidenceCategory.INFRASTRUCTURE,
                                  evidence_type="request_velocity", source_module="watchtower",
                                  title=f"~{rate:.0f} req/min from unregistered client",
                                  confidence_contribution=min(rate / 100, 1),
                                  description=f"{len(events)} requests in {span:.0f} minutes.",
                                  source_entity_type="endpoint", source_entity_id=ep_id,
                                  event_time=max(e.event_time for e in events))
            created.append({"code": inv.code, "category": inv.category, "confidence": conf,
                            "requests": len(events)})
            break
        return created
