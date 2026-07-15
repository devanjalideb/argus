"""Blast Radius APIs — retrospective reconstruction surface."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.models import Endpoint, Vulnerability
from app.models.enums import Engine
from app.modules.blast_radius import BlastRadiusService
from app.modules.investigations import InvestigationService

router = APIRouter(prefix="/blast-radius", tags=["blast-radius"])


@router.post("/analyze", summary="Reconstruct all outstanding disclosures")
def analyze(db: Session = Depends(get_db)):
    return success(BlastRadiusService(db).analyze_all())


@router.post("/reconstruct/{vuln_ref}", summary="Reconstruct a single disclosure")
def reconstruct(vuln_ref: str, db: Session = Depends(get_db)):
    svc = BlastRadiusService(db)
    result = svc.reconstruct(vuln_ref)
    db.commit()
    return success(result)


@router.get("/disclosures", summary="List disclosure events")
def disclosures(db: Session = Depends(get_db)):
    rows = db.scalars(select(Vulnerability).order_by(Vulnerability.disclosed_at.desc())).all()
    out = []
    for v in rows:
        ep = db.get(Endpoint, v.affected_endpoint_id)
        out.append({
            "vuln_ref": v.vuln_ref, "disclosure_type": v.disclosure_type, "title": v.title,
            "severity": v.severity, "cvss": v.cvss, "patch_status": v.patch_status,
            "affected_endpoint": ep.endpoint_ref if ep else None,
            "affected_algorithm": v.affected_algorithm,
            "exposure_window_start": v.exposure_window_start.isoformat(),
            "exposure_window_end": v.exposure_window_end.isoformat() if v.exposure_window_end else None,
            "disclosed_at": v.disclosed_at.isoformat(),
        })
    return success(out)


@router.get("/investigations", summary="Retrospective investigations")
def investigations(db: Session = Depends(get_db)):
    items, total = InvestigationService(db).list(engine=Engine.BLAST_RADIUS, page_size=50)
    return success({"reconstructions": items, "total": total})
