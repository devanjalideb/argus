"""ReportService — generate, persist and version investigation reports."""
from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models import Investigation, Report
from app.modules.investigations import InvestigationService
from . import pdf

logger = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[4]
REPORTS_DIR = ROOT / settings.reports_dir
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class ReportService:
    def __init__(self, session: Session):
        self.s = session
        self.inv = InvestigationService(session)

    def generate(self, code: str, report_type: str = "executive",
                 export_format: str = "pdf") -> dict:
        inv = self.s.scalar(select(Investigation).where(Investigation.code == code))
        if not inv:
            raise NotFoundError(f"Unknown investigation '{code}'")
        detail = self.inv.detail(code)

        version = (self.s.scalar(select(func.count()).select_from(Report).where(
            Report.investigation_id == inv.id, Report.report_type == report_type,
            Report.export_format == export_format)) or 0) + 1
        fname = f"{code}_{report_type}_v{version}.{export_format}"
        path = REPORTS_DIR / fname

        started = time.perf_counter()
        if export_format == "pdf":
            pdf.build(detail, report_type, str(path))
        elif export_format == "json":
            path.write_text(json.dumps(detail, indent=2, default=str), encoding="utf-8")
        elif export_format == "csv":
            self._csv(detail, path)
        else:
            raise NotFoundError(f"Unsupported export format '{export_format}'")
        elapsed = int((time.perf_counter() - started) * 1000)

        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        row = Report(
            investigation_id=inv.id, report_type=report_type, export_format=export_format,
            title=f"{report_type.title()} Report - {code}", status="ready",
            document_path=str(path), version=version, author="ARGUS",
            integrity_hash=digest, generation_ms=elapsed,
        )
        self.s.add(row)
        self.s.commit()
        logger.info("Report %s (%s/%s) v%d generated in %d ms", code, report_type,
                    export_format, version, elapsed)
        return {"id": row.id, "investigation": code, "report_type": report_type,
                "export_format": export_format, "version": version, "path": str(path),
                "filename": fname, "integrity_hash": digest, "generation_ms": elapsed}

    @staticmethod
    def _csv(detail: dict, path: Path) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["category", "title", "description", "confidence_contribution",
                        "source_entity_type", "source_entity_id", "event_time"])
            for e in detail.get("evidence", []):
                w.writerow([e["category"], e["title"], e["description"],
                            e["confidence_contribution"], e.get("source_entity_type"),
                            e.get("source_entity_id"), e.get("event_time")])

    def list_reports(self, code: str | None = None) -> list[dict]:
        stmt = select(Report).order_by(Report.created_at.desc())
        if code:
            inv = self.s.scalar(select(Investigation).where(Investigation.code == code))
            stmt = stmt.where(Report.investigation_id == (inv.id if inv else "__none__"))
        rows = self.s.scalars(stmt).all()
        # Map investigation ids back to codes for display.
        codes = {i.id: i.code for i in self.s.scalars(select(Investigation)).all()}
        return [{
            "id": r.id, "investigation": codes.get(r.investigation_id),
            "report_type": r.report_type, "export_format": r.export_format, "title": r.title,
            "status": r.status, "version": r.version, "filename": Path(r.document_path).name,
            "integrity_hash": (r.integrity_hash or "")[:16], "generation_ms": r.generation_ms,
            "created_at": r.created_at.isoformat(),
        } for r in rows]

    def path_for(self, report_id: int) -> Path:
        r = self.s.get(Report, report_id)
        if not r or not r.document_path or not Path(r.document_path).exists():
            raise NotFoundError("Report file not found")
        return Path(r.document_path)
