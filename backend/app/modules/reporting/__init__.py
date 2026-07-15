"""Reporting: the final communication layer. Combines every engine's output into
professional, evidence-based documents (PDF / JSON / CSV). Documents investigations —
never introduces new conclusions.
"""
from .service import ReportService

__all__ = ["ReportService"]
