"""Aggregate router for API v1. Feature routers are registered here as they are built."""
from __future__ import annotations

from fastapi import APIRouter

from . import (
    ai,
    auth,
    blast_radius,
    business_impact,
    entity,
    ingestion,
    investigations,
    knowledge_graph,
    reports,
    risk_memory,
    synthetic,
    system,
    watchtower,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(ingestion.router)
api_router.include_router(ingestion.events_router)
api_router.include_router(risk_memory.router)
api_router.include_router(investigations.router)
api_router.include_router(watchtower.router)
api_router.include_router(blast_radius.router)
api_router.include_router(business_impact.router)
api_router.include_router(entity.router)
api_router.include_router(ai.router)
api_router.include_router(knowledge_graph.router)
api_router.include_router(reports.router)
api_router.include_router(synthetic.router)

# Registered in later milestones:
#   auth
