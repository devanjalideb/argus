"""Explainable AI Decision engine.

Transforms structured investigation evidence into human-readable narratives for different
audiences. It explains evidence — it never creates it. Works fully offline via a grounded
template narrator; uses OpenRouter when configured.
"""
from .service import ExplainService

__all__ = ["ExplainService"]
