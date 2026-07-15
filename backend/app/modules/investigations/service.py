"""InvestigationService — lifecycle + serialization for the central business object."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models import (
    AINarrative,
    AnalystAction,
    BusinessImpact,
    Customer,
    Endpoint,
    Evidence,
    Investigation,
    Recommendation,
    Vulnerability,
)
from app.models.base import utcnow

logger = get_logger(__name__)


class InvestigationService:
    def __init__(self, session: Session):
        self.s = session

    # ------------------------------------------------------------ creation
    def next_code(self) -> str:
        year = utcnow().year
        n = self.s.scalar(
            select(func.count()).select_from(Investigation)
            .where(Investigation.code.like(f"ARG-{year}-%"))) or 0
        return f"ARG-{year}-{n + 1:04d}"

    def create(self, *, title: str, description: str, severity: str, confidence: float,
               category: str, engine: str, primary_customer_id: str | None = None,
               primary_endpoint_id: str | None = None, vulnerability_id: str | None = None,
               business_priority: str = "P3", detected_at: datetime | None = None,
               meta: dict | None = None) -> Investigation:
        inv = Investigation(
            code=self.next_code(), title=title, description=description, severity=severity,
            confidence=round(confidence, 2), category=category, originating_engine=engine,
            status="open", lifecycle_stage="detected", business_priority=business_priority,
            primary_customer_id=primary_customer_id, primary_endpoint_id=primary_endpoint_id,
            vulnerability_id=vulnerability_id, detected_at=detected_at or utcnow(),
            meta=meta or {},
        )
        self.s.add(inv)
        self.s.flush()
        logger.info("Investigation %s created by %s (%s)", inv.code, engine, category)
        return inv

    def add_evidence(self, inv: Investigation, *, category: str, evidence_type: str,
                     source_module: str, title: str, description: str = "",
                     confidence_contribution: float = 0.0, source_entity_type: str | None = None,
                     source_entity_id: str | None = None, event_time: datetime | None = None,
                     ledger_ref: int | None = None, meta: dict | None = None) -> Evidence:
        ev = Evidence(
            investigation_id=inv.id, category=category, evidence_type=evidence_type,
            source_module=source_module, title=title, description=description,
            confidence_contribution=round(confidence_contribution, 4),
            source_entity_type=source_entity_type, source_entity_id=source_entity_id,
            event_time=event_time, ledger_ref=ledger_ref, meta=meta or {},
        )
        self.s.add(ev)
        return ev

    def add_action(self, inv: Investigation, action: str, actor: str = "analyst",
                   detail: str | None = None) -> AnalystAction:
        act = AnalystAction(investigation_id=inv.id, action=action, actor=actor,
                            detail=detail, event_time=utcnow())
        self.s.add(act)
        return act

    # ------------------------------------------------------------ retrieval
    def _get(self, ident: str) -> Investigation:
        inv = self.s.scalar(select(Investigation).where(Investigation.code == ident))
        if not inv:
            inv = self.s.get(Investigation, ident)
        if not inv:
            raise NotFoundError(f"Unknown investigation '{ident}'")
        return inv

    def list(self, *, status: str | None = None, severity: str | None = None,
             engine: str | None = None, category: str | None = None, search: str | None = None,
             sort: str = "detected_at", order: str = "desc", page: int = 1,
             page_size: int = 25) -> tuple[list[dict], int]:
        stmt = select(Investigation)
        cnt = select(func.count()).select_from(Investigation)
        conds = []
        if status:
            conds.append(Investigation.status == status)
        if severity:
            conds.append(Investigation.severity == severity)
        if engine:
            conds.append(Investigation.originating_engine == engine)
        if category:
            conds.append(Investigation.category == category)
        if search:
            like = f"%{search}%"
            conds.append(Investigation.title.like(like) | Investigation.code.like(like))
        for cnd in conds:
            stmt = stmt.where(cnd)
            cnt = cnt.where(cnd)

        sort_col = {
            "detected_at": Investigation.detected_at, "severity": Investigation.severity,
            "confidence": Investigation.confidence, "updated_at": Investigation.updated_at,
        }.get(sort, Investigation.detected_at)
        stmt = stmt.order_by(desc(sort_col) if order == "desc" else sort_col)

        total = self.s.scalar(cnt) or 0
        rows = self.s.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()

        # Batch-load active business impacts + narratives to avoid N+1.
        ids = [r.id for r in rows]
        bi_map = self._active_map(BusinessImpact, ids)
        nar_map = self._active_map(AINarrative, ids)
        return [self._summary(r, bi_map.get(r.id), nar_map.get(r.id)) for r in rows], total

    def _active_map(self, model, inv_ids: list[str]) -> dict:
        if not inv_ids:
            return {}
        rows = self.s.scalars(
            select(model).where(model.investigation_id.in_(inv_ids), model.is_active == True)  # noqa: E712
        ).all()
        return {r.investigation_id: r for r in rows}

    # ------------------------------------------------------------ serializers
    @staticmethod
    def _summary(inv: Investigation, bi: BusinessImpact | None, nar: AINarrative | None) -> dict:
        return {
            "id": inv.id, "code": inv.code, "title": inv.title, "severity": inv.severity,
            "confidence": inv.confidence, "status": inv.status, "category": inv.category,
            "originating_engine": inv.originating_engine, "business_priority": inv.business_priority,
            "lifecycle_stage": inv.lifecycle_stage,
            "assigned_analyst_id": inv.assigned_analyst_id, "owner": inv.owner,
            "financial_exposure": float(bi.financial_exposure) if bi else 0.0,
            "affected_customers": bi.affected_customers if bi else 0,
            "ai_summary": (nar.executive_summary[:240] if nar and nar.executive_summary
                           else (inv.description[:240] if inv.description else "")),
            "detected_at": inv.detected_at.isoformat() if inv.detected_at else None,
            "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
        }

    def detail(self, ident: str) -> dict:
        inv = self._get(ident)
        evidence = self.s.scalars(
            select(Evidence).where(Evidence.investigation_id == inv.id)
            .order_by(Evidence.event_time.is_(None), Evidence.event_time)).all()
        bi = self.s.scalar(select(BusinessImpact).where(
            BusinessImpact.investigation_id == inv.id, BusinessImpact.is_active == True))  # noqa: E712
        nar = self.s.scalar(select(AINarrative).where(
            AINarrative.investigation_id == inv.id, AINarrative.is_active == True))  # noqa: E712
        recs = self.s.scalars(select(Recommendation).where(
            Recommendation.investigation_id == inv.id).order_by(Recommendation.priority)).all()
        actions = self.s.scalars(select(AnalystAction).where(
            AnalystAction.investigation_id == inv.id).order_by(AnalystAction.event_time)).all()

        vuln = self.s.get(Vulnerability, inv.vulnerability_id) if inv.vulnerability_id else None
        cust = self.s.get(Customer, inv.primary_customer_id) if inv.primary_customer_id else None
        ep = self.s.get(Endpoint, inv.primary_endpoint_id) if inv.primary_endpoint_id else None

        ev_dicts = [self._evidence(e) for e in evidence]
        grouped: dict[str, list] = {}
        for e in ev_dicts:
            grouped.setdefault(e["category"], []).append(e)

        return {
            "id": inv.id, "code": inv.code, "title": inv.title, "description": inv.description,
            "severity": inv.severity, "confidence": inv.confidence, "status": inv.status,
            "category": inv.category, "originating_engine": inv.originating_engine,
            "lifecycle_stage": inv.lifecycle_stage, "business_priority": inv.business_priority,
            "assigned_analyst_id": inv.assigned_analyst_id, "owner": inv.owner,
            "resolution": inv.resolution,
            "detected_at": inv.detected_at.isoformat() if inv.detected_at else None,
            "created_at": inv.created_at.isoformat(), "updated_at": inv.updated_at.isoformat(),
            "resolved_at": inv.resolved_at.isoformat() if inv.resolved_at else None,
            "meta": inv.meta or {},
            "confidence_breakdown": (inv.meta or {}).get("confidence_breakdown", []),
            "predicted_next_step": (inv.meta or {}).get("predicted_next_step"),
            "primary_customer": {"id": cust.id, "ref": cust.customer_ref, "name": cust.full_name,
                                 "type": cust.customer_type} if cust else None,
            "primary_endpoint": {"id": ep.id, "ref": ep.endpoint_ref, "name": ep.name,
                                 "criticality": ep.criticality} if ep else None,
            "vulnerability": {"ref": vuln.vuln_ref, "title": vuln.title, "type": vuln.disclosure_type,
                              "severity": vuln.severity} if vuln else None,
            "evidence": ev_dicts,
            "evidence_by_category": grouped,
            "evidence_count": len(ev_dicts),
            "business_impact": self._bi(bi) if bi else None,
            "ai_narrative": self._nar(nar) if nar else None,
            "recommendations": [self._rec(r) for r in recs],
            "analyst_actions": [self._act(a) for a in actions],
            "timeline": self._timeline(ev_dicts, actions),
        }

    @staticmethod
    def _evidence(e: Evidence) -> dict:
        return {
            "id": e.id, "category": e.category, "evidence_type": e.evidence_type,
            "source_module": e.source_module, "title": e.title, "description": e.description,
            "confidence_contribution": e.confidence_contribution,
            "source_entity_type": e.source_entity_type, "source_entity_id": e.source_entity_id,
            "event_time": e.event_time.isoformat() if e.event_time else None, "meta": e.meta,
        }

    @staticmethod
    def _bi(bi: BusinessImpact) -> dict:
        return {
            "financial_exposure": float(bi.financial_exposure),
            "affected_customers": bi.affected_customers, "affected_accounts": bi.affected_accounts,
            "customer_segmentation": bi.customer_segmentation, "data_sensitivity": bi.data_sensitivity,
            "infrastructure_criticality": bi.infrastructure_criticality,
            "operational_disruption": bi.operational_disruption,
            "regulatory_flags": bi.regulatory_flags, "executive_priority": bi.executive_priority,
            "executive_severity": bi.executive_severity,
            "estimated_remediation_cost": float(bi.estimated_remediation_cost),
            "business_confidence": bi.business_confidence, "recommended_urgency": bi.recommended_urgency,
        }

    @staticmethod
    def _nar(n: AINarrative) -> dict:
        return {
            "provider": n.provider, "model_id": n.model_id, "grounded": n.grounded,
            "executive_summary": n.executive_summary, "technical_summary": n.technical_summary,
            "confidence_explanation": n.confidence_explanation, "evidence_summary": n.evidence_summary,
            "recommended_action_summary": n.recommended_action_summary,
            "generation_ms": n.generation_ms, "generated_at": n.created_at.isoformat(),
        }

    @staticmethod
    def _rec(r: Recommendation) -> dict:
        return {
            "id": r.id, "rec_type": r.rec_type, "title": r.title, "description": r.description,
            "rationale": r.rationale, "priority": r.priority, "status": r.status, "owner": r.owner,
            "executed_at": r.executed_at.isoformat() if r.executed_at else None,
        }

    @staticmethod
    def _act(a: AnalystAction) -> dict:
        return {"id": a.id, "action": a.action, "actor": a.actor, "detail": a.detail,
                "event_time": a.event_time.isoformat()}

    @staticmethod
    def _timeline(ev_dicts: list[dict], actions: list[AnalystAction]) -> list[dict]:
        items = []
        for e in ev_dicts:
            if e["event_time"]:
                items.append({"time": e["event_time"], "kind": "evidence",
                              "category": e["category"], "title": e["title"],
                              "description": e["description"]})
        for a in actions:
            items.append({"time": a.event_time.isoformat(), "kind": "action",
                          "category": "analyst_note", "title": f"Analyst: {a.action}",
                          "description": a.detail or ""})
        return sorted(items, key=lambda x: x["time"])

    # ------------------------------------------------------------ lifecycle
    def update_status(self, ident: str, status: str, note: str | None = None) -> dict:
        inv = self._get(ident)
        inv.status = status
        if status in ("resolved", "closed"):
            inv.resolved_at = utcnow()
            inv.lifecycle_stage = "resolved"
            if note:
                inv.resolution = note
        self.add_action(inv, f"status_changed:{status}", detail=note)
        self.s.commit()
        return self.detail(inv.code)

    def assign(self, ident: str, analyst: str) -> dict:
        inv = self._get(ident)
        inv.owner = analyst
        self.add_action(inv, "assigned", detail=analyst)
        self.s.commit()
        return self.detail(inv.code)

    def escalate(self, ident: str, note: str | None = None) -> dict:
        inv = self._get(ident)
        inv.business_priority = "P1"
        inv.severity = "critical"
        self.add_action(inv, "escalated", detail=note)
        self.s.commit()
        return self.detail(inv.code)
