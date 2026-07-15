"""Watchtower: forward-looking behavioural anomaly detection.

Combines Risk Memory context, engineered features, an Isolation Forest, and deterministic
correlation rules — no single algorithm decides an investigation on its own.
"""
from .service import WatchtowerService

__all__ = ["WatchtowerService"]
