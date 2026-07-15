"""Ingestion module: the single entrance to ARGUS.

Validates, normalizes, enriches and commits every event to the immutable ledger.
Performs no analytics — anomaly detection belongs to Watchtower.
"""
from .service import IngestionService

__all__ = ["IngestionService"]
