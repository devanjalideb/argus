"""Report APIs — generate, list and download investigation reports."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.modules.reporting import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])

_MIME = {"pdf": "application/pdf", "json": "application/json", "csv": "text/csv"}


@router.get("", summary="List generated reports")
def list_reports(code: str | None = None, db: Session = Depends(get_db)):
    return success(ReportService(db).list_reports(code))


@router.post("/{code}/generate", summary="Generate a report")
def generate(code: str, report_type: str = Body("executive", embed=True),
             export_format: str = Body("pdf", embed=True), db: Session = Depends(get_db)):
    return success(ReportService(db).generate(code, report_type, export_format))


@router.get("/{report_id}/download", summary="Download a generated report")
def download(report_id: int, db: Session = Depends(get_db)):
    path = ReportService(db).path_for(report_id)
    ext = path.suffix.lstrip(".")
    return FileResponse(str(path), media_type=_MIME.get(ext, "application/octet-stream"),
                        filename=path.name)
