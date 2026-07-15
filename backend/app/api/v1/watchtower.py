"""Watchtower APIs — behavioural intelligence surface."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.models.enums import Engine
from app.modules.investigations import InvestigationService
from app.modules.watchtower import WatchtowerService
from app.modules.watchtower.service import MODEL_STATE

router = APIRouter(prefix="/watchtower", tags=["watchtower"])


@router.post("/analyze", summary="Run behavioural analysis over recent activity")
def analyze(db: Session = Depends(get_db)):
    return success(WatchtowerService(db).analyze())


@router.get("/status", summary="Model + engine status")
def status(db: Session = Depends(get_db)):
    return success({
        "model": MODEL_STATE,
        "algorithm": "Isolation Forest (scikit-learn)",
        "approach": "per-entity behavioural deviation vs Risk Memory baseline + deterministic rules",
    })


@router.get("/detections", summary="Recent Watchtower investigations")
def detections(db: Session = Depends(get_db)):
    items, total = InvestigationService(db).list(engine=Engine.WATCHTOWER, page_size=50)
    return success({"detections": items, "total": total})
