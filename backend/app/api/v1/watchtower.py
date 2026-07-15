"""Watchtower APIs — behavioural intelligence surface."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.modules.watchtower import WatchtowerService

router = APIRouter(prefix="/watchtower", tags=["watchtower"])


@router.post("/analyze", summary="Run behavioural analysis over recent activity")
def analyze(db: Session = Depends(get_db)):
    return success(WatchtowerService(db).analyze())


@router.get("/status", summary="Model dashboard: health, distribution, behaviours")
def status(db: Session = Depends(get_db)):
    return success({
        "model": WatchtowerService(db).model_report(),
        "algorithm": "Isolation Forest (scikit-learn)",
        "approach": "per-entity behavioural deviation vs Risk Memory baseline + deterministic rules",
    })


@router.get("/detections", summary="Recent Watchtower detections with anomaly scores")
def detections(db: Session = Depends(get_db)):
    return success({"detections": WatchtowerService(db).recent_detections(limit=8)})
