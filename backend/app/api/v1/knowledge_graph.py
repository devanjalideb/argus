"""Knowledge Graph APIs — investigation graphs + node exploration."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.modules.knowledge_graph import KnowledgeGraphService

router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])


@router.get("/investigation/{code}", summary="Investigation subgraph")
def investigation_graph(code: str, db: Session = Depends(get_db)):
    return success(KnowledgeGraphService(db).investigation_graph(code))


@router.get("/node/{node_type}/{node_id}", summary="Contextual metadata for a node")
def node_context(node_type: str, node_id: str, db: Session = Depends(get_db)):
    return success(KnowledgeGraphService(db).node_context(node_type, node_id))
