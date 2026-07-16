"""Detection pipeline orchestrator.

Runs the complete investigation-construction flow end to end: reset prior investigations,
run both intelligence engines, then enrich every resulting investigation with Business
Impact, an explainable AI narrative, and a knowledge-graph roster.
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import (
    AINarrative,
    AnalystAction,
    BusinessImpact,
    Evidence,
    Investigation,
    Recommendation,
    Report,
)

logger = get_logger(__name__)

# Rotating roster used to give demo investigations realistic assignees instead of
# "Unassigned". Applied only to seeded/demo data; the live assign() API is unaffected.
_DEMO_ANALYSTS = [
    "SOC Tier 2", "A. Sharma", "Incident Response", "SOC Tier 1",
    "R. Iyer", "Threat Intel", "K. Menon", "SOC Tier 3",
]


def reset_investigations(session: Session) -> None:
    for model in (Evidence, BusinessImpact, AINarrative, Recommendation, Report,
                  AnalystAction, Investigation):
        session.execute(delete(model))
    session.commit()
    logger.info("Cleared prior investigations and enrichment.")


def run_detection(session: Session, reset: bool = True, enrich: bool = True) -> dict:
    from app.modules.blast_radius import BlastRadiusService
    from app.modules.risk_memory import RiskMemoryService
    from app.modules.watchtower import WatchtowerService

    if reset:
        reset_investigations(session)

    RiskMemoryService(session).recompute_all()
    watch = WatchtowerService(session).analyze()
    blast = BlastRadiusService(session).analyze_all()

    result = {"watchtower": watch, "blast_radius": blast}
    if enrich:
        result["enrichment"] = _enrich_all(session)
    _assign_demo_analysts(session)
    return result


def _assign_demo_analysts(session: Session) -> None:
    """Give every demo investigation a realistic owner (rotating), replacing 'Unassigned'.

    Deterministic (ordered by code) so the demo is stable across rebuilds. Only sets the
    ``owner`` display field on seeded data; the manual assign() workflow is untouched, and any
    investigation already owned by a human is left as-is.
    """
    invs = session.scalars(select(Investigation).order_by(Investigation.code)).all()
    assigned = 0
    for idx, inv in enumerate(invs):
        if not inv.owner:
            inv.owner = _DEMO_ANALYSTS[idx % len(_DEMO_ANALYSTS)]
            assigned += 1
    session.commit()
    logger.info("Assigned %d demo investigation(s) to analysts.", assigned)


def _enrich_all(session: Session) -> dict:
    """Business Impact + AI narrative + Knowledge Graph roster for every investigation."""
    from app.models import Investigation as Inv
    from app.modules.business_impact import BusinessImpactService
    from app.modules.explain import ExplainService

    bi = BusinessImpactService(session)
    ai = ExplainService(session)
    codes = [i.code for i in session.scalars(select(Inv)).all()]
    for code in codes:
        bi.assess(code)
        # Bulk rebuild uses the instant offline narrator; the live model is invoked
        # on demand via the "Regenerate AI" action (POST /ai/{code}/generate).
        ai.generate(code, prefer_offline=True)
    session.commit()
    return {"enriched_investigations": len(codes)}
