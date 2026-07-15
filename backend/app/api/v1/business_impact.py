"""Business Impact APIs."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.models import Investigation
from app.modules.business_impact import BusinessImpactService
from app.modules.investigations import InvestigationService

router = APIRouter(prefix="/business-impact", tags=["business-impact"])


@router.post("/assess-all", summary="Assess every investigation")
def assess_all(db: Session = Depends(get_db)):
    svc = BusinessImpactService(db)
    codes = [i.code for i in db.scalars(select(Investigation)).all()]
    return success({"assessed": [svc.assess(c) for c in codes]})


@router.post("/{code}/assess", summary="Assess a single investigation")
def assess(code: str, db: Session = Depends(get_db)):
    return success(BusinessImpactService(db).assess(code))


@router.get("/{code}", summary="Business Impact assessment for an investigation")
def get_impact(code: str, db: Session = Depends(get_db)):
    detail = InvestigationService(db).detail(code)
    return success({"investigation": code, "business_impact": detail["business_impact"],
                    "recommendations": detail["recommendations"]})
