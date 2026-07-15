"""Knowledge Graph: the relational memory of ARGUS.

Builds investigation graphs on demand from relational data with NetworkX — no separate
graph database. Nodes and edges model genuine business relationships; the graph supports
investigation, not decoration.
"""
from .service import KnowledgeGraphService

__all__ = ["KnowledgeGraphService"]
