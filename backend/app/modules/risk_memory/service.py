"""Risk Memory engine — builds and serves evolving behavioural profiles.

`recompute_all` summarizes historical behaviour into compact per-entity features so
analytical engines retrieve a profile in one query instead of scanning months of events.
`observe` applies incremental updates; `apply_feedback` folds analyst decisions back in.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import (
    AuthEvent,
    Customer,
    Device,
    Endpoint,
    EventLedger,
    IPAddress,
    Location,
    RiskMemory,
    Transaction,
)
from app.models.base import utcnow
from app.models.enums import AuthResult, EntityType

logger = get_logger(__name__)


def _confidence_from_count(n: int) -> float:
    """More observations -> higher confidence the baseline is well understood."""
    return round(min(0.99, 1 - math.exp(-n / 40.0)), 4)


class RiskMemoryService:
    def __init__(self, session: Session):
        self.s = session

    # ------------------------------------------------------------ retrieval
    def get_profile(self, entity_type: str, entity_id: str) -> dict | None:
        rm = self.s.scalar(
            select(RiskMemory).where(RiskMemory.entity_type == entity_type,
                                     RiskMemory.entity_id == entity_id))
        return self._serialize(rm) if rm else None

    def get_customer_profile(self, customer_id: str) -> dict | None:
        return self.get_profile(EntityType.CUSTOMER, customer_id)

    def get_device_profile(self, device_id: str) -> dict | None:
        return self.get_profile(EntityType.DEVICE, device_id)

    def get_ip_profile(self, ip_id: str) -> dict | None:
        return self.get_profile(EntityType.IP, ip_id)

    def get_endpoint_profile(self, endpoint_id: str) -> dict | None:
        return self.get_profile(EntityType.ENDPOINT, endpoint_id)

    def _row(self, entity_type: str, entity_id: str) -> RiskMemory:
        rm = self.s.scalar(
            select(RiskMemory).where(RiskMemory.entity_type == entity_type,
                                     RiskMemory.entity_id == entity_id))
        if not rm:
            # Explicit initial values: column defaults only apply at flush, but we
            # read these fields before flushing.
            rm = RiskMemory(
                entity_type=entity_type, entity_id=entity_id, trust_score=0.5,
                behavioural_confidence=0.1, baseline_confidence=0.1, amt_mean=0.0,
                amt_median=0.0, amt_std=1.0, amt_max=0.0, txn_frequency_daily=0.0,
                auth_success_rate=1.0, behavioural_variance=0.0, decay_factor=0.98,
                observation_count=0, historical_anomalies=0, false_positives=0,
                true_positives=0, preferred_hours=[], normal_countries=[],
                preferred_devices=[], history=[],
            )
            self.s.add(rm)
        return rm

    @staticmethod
    def _serialize(rm: RiskMemory) -> dict:
        return {
            "entity_type": rm.entity_type, "entity_id": rm.entity_id,
            "trust_score": round(rm.trust_score, 4),
            "behavioural_confidence": round(rm.behavioural_confidence, 4),
            "baseline_confidence": round(rm.baseline_confidence, 4),
            "amt_mean": round(rm.amt_mean, 2), "amt_median": round(rm.amt_median, 2),
            "amt_std": round(rm.amt_std, 2), "amt_max": round(rm.amt_max, 2),
            "txn_frequency_daily": round(rm.txn_frequency_daily, 3),
            "auth_success_rate": round(rm.auth_success_rate, 4),
            "preferred_hours": rm.preferred_hours, "normal_countries": rm.normal_countries,
            "preferred_devices": rm.preferred_devices,
            "home_lat": rm.home_lat, "home_lon": rm.home_lon,
            "observation_count": rm.observation_count,
            "historical_anomalies": rm.historical_anomalies,
            "false_positives": rm.false_positives, "true_positives": rm.true_positives,
            "behavioural_variance": round(rm.behavioural_variance, 4),
            "decay_factor": rm.decay_factor,
            "last_recalculated": rm.last_recalculated.isoformat() if rm.last_recalculated else None,
            "history": rm.history,
        }

    # ------------------------------------------------------------ recompute
    def recompute_all(self) -> dict:
        counts = {
            "customers": self._recompute_customers(),
            "devices": self._recompute_devices(),
            "ips": self._recompute_ips(),
            "endpoints": self._recompute_endpoints(),
        }
        self.s.commit()
        logger.info("Risk Memory recomputed: %s", counts)
        return counts

    def _recompute_customers(self) -> int:
        customers = self.s.scalars(select(Customer)).all()
        loc_map = {l.id: l for l in self.s.scalars(select(Location)).all()}

        # Pre-group transactions and auth events by customer in Python (2 scans total).
        txns = defaultdict(list)
        for cid, amount, when in self.s.execute(
                select(Transaction.customer_id, Transaction.amount, Transaction.event_time)):
            if cid:
                txns[cid].append((float(amount), when))

        auth = defaultdict(list)
        for cid, when, result, dev, loc in self.s.execute(
                select(AuthEvent.customer_id, AuthEvent.event_time, AuthEvent.result,
                       AuthEvent.device_id, AuthEvent.location_id)):
            if cid:
                auth[cid].append((when, result, dev, loc))

        n = 0
        for c in customers:
            amts = [a for a, _ in txns.get(c.id, [])]
            times = [w for _, w in txns.get(c.id, [])]
            a_events = auth.get(c.id, [])

            rm = self._row(EntityType.CUSTOMER, c.id)
            if amts:
                arr = np.array(amts)
                rm.amt_mean = float(arr.mean())
                rm.amt_median = float(np.median(arr))
                rm.amt_std = float(arr.std()) if len(arr) > 1 else float(arr.mean() * 0.3)
                rm.amt_max = float(arr.max())
                cv = rm.amt_std / rm.amt_mean if rm.amt_mean else 0.0
                rm.behavioural_variance = round(min(cv, 3.0), 4)
            if times:
                span_days = max(1, (max(times) - min(times)).days)
                rm.txn_frequency_daily = len(times) / span_days

            hours = [w.hour for (w, _, _, _) in a_events]
            rm.preferred_hours = [h for h, _ in Counter(hours).most_common(6)]
            successes = sum(1 for (_, r, _, _) in a_events if r == AuthResult.SUCCESS)
            rm.auth_success_rate = successes / len(a_events) if a_events else 1.0
            rm.preferred_devices = list({d for (_, _, d, _) in a_events if d})[:5]
            countries = [loc_map[l].country for (_, _, _, l) in a_events if l in loc_map]
            rm.normal_countries = [ct for ct, _ in Counter(countries).most_common(4)]
            lats = [loc_map[l].latitude for (_, _, _, l) in a_events if l in loc_map]
            lons = [loc_map[l].longitude for (_, _, _, l) in a_events if l in loc_map]
            if lats:
                rm.home_lat, rm.home_lon = float(np.mean(lats)), float(np.mean(lons))

            rm.observation_count = len(amts) + len(a_events)
            rm.behavioural_confidence = _confidence_from_count(rm.observation_count)
            rm.baseline_confidence = rm.behavioural_confidence
            # Trust: consistent spend + high auth success -> trusted (before any anomalies).
            consistency = max(0.0, 1 - min(rm.behavioural_variance / 2.0, 1.0))
            rm.trust_score = round(0.55 + 0.35 * consistency + 0.10 * rm.auth_success_rate - 0.05, 4)
            rm.trust_score = min(0.98, max(0.15, rm.trust_score))
            rm.last_recalculated = utcnow()
            rm.history = [{"t": utcnow().isoformat(), "trust": rm.trust_score,
                           "confidence": rm.behavioural_confidence}]
            n += 1
        return n

    def _recompute_devices(self) -> int:
        usage = Counter()
        for (dev,) in self.s.execute(select(AuthEvent.device_id)):
            if dev:
                usage[dev] += 1
        n = 0
        for d in self.s.scalars(select(Device)).all():
            rm = self._row(EntityType.DEVICE, d.id)
            rm.observation_count = usage.get(d.id, 0)
            rm.behavioural_confidence = _confidence_from_count(rm.observation_count)
            rm.trust_score = float(d.trust_score)
            rm.last_recalculated = utcnow()
            n += 1
        return n

    def _recompute_ips(self) -> int:
        usage = Counter()
        for (ip,) in self.s.execute(select(EventLedger.ip_id)):
            if ip:
                usage[ip] += 1
        n = 0
        for ip in self.s.scalars(select(IPAddress)).all():
            rm = self._row(EntityType.IP, ip.id)
            rm.observation_count = usage.get(ip.id, 0)
            rm.behavioural_confidence = _confidence_from_count(rm.observation_count)
            rm.trust_score = float(ip.reputation_score)
            rm.normal_countries = [ip.country]
            rm.last_recalculated = utcnow()
            n += 1
        return n

    def _recompute_endpoints(self) -> int:
        vol = Counter()
        for (eid,) in self.s.execute(select(EventLedger.endpoint_id)):
            if eid:
                vol[eid] += 1
        n = 0
        for ep in self.s.scalars(select(Endpoint)).all():
            rm = self._row(EntityType.ENDPOINT, ep.id)
            rm.observation_count = vol.get(ep.id, 0)
            rm.behavioural_confidence = _confidence_from_count(rm.observation_count)
            rm.trust_score = 0.9 if ep.security_posture == "hardened" else 0.4
            rm.last_recalculated = utcnow()
            n += 1
        return n

    # ------------------------------------------------------------ feedback
    def apply_feedback(self, entity_type: str, entity_id: str, material: bool) -> dict:
        """Analyst decision folds back into the baseline (continuous improvement)."""
        rm = self._row(entity_type, entity_id)
        if material:
            rm.true_positives += 1
            rm.historical_anomalies += 1
            rm.trust_score = max(0.05, rm.trust_score * 0.75)
        else:
            rm.false_positives += 1
            # Legitimate behaviour: relax the baseline so similar activity is less alarming.
            rm.trust_score = min(0.98, rm.trust_score * 1.0 + 0.05)
        rm.last_recalculated = utcnow()
        rm.history = (rm.history or []) + [{
            "t": utcnow().isoformat(), "trust": round(rm.trust_score, 4),
            "feedback": "material" if material else "non_material"}]
        self.s.commit()
        return self._serialize(rm)
