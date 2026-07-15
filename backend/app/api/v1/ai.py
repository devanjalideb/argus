"""Explainable AI APIs."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.response import success
from app.modules.explain import ExplainService
from app.modules.investigations import InvestigationService

router = APIRouter(prefix="/ai", tags=["explainable-ai"])


@router.get("/status", summary="AI provider status")
def status():
    live = settings.ai_enabled and bool(settings.openrouter_api_key)
    return success({
        "provider": "openrouter" if live else "offline-grounded-narrator",
        "model": settings.openrouter_model if live else "argus-grounded-narrator-v1",
        "live": live,
        "note": "Narratives are strictly grounded in structured evidence; offline fallback "
                "keeps the platform fully usable without network access.",
    })


@router.post("/{code}/generate", summary="Generate grounded narratives for an investigation")
def generate(code: str, db: Session = Depends(get_db)):
    return success(ExplainService(db).generate(code))


@router.get("/{code}", summary="Active AI narratives for an investigation")
def get_narratives(code: str, db: Session = Depends(get_db)):
    detail = InvestigationService(db).detail(code)
    return success({"investigation": code, "ai_narrative": detail["ai_narrative"]})
