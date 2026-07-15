"""Risk Memory: the long-term behavioural memory of ARGUS.

Compares every entity primarily against its own history, not the global population.
Provides context to analytical engines; it never declares behaviour suspicious itself.
"""
from .service import RiskMemoryService

__all__ = ["RiskMemoryService"]
