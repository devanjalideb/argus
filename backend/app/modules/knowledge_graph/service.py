"""Knowledge Graph engine — builds investigation subgraphs from relational data."""
from __future__ import annotations

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models import (
    Customer,
    Device,
    Endpoint,
    Evidence,
    Investigation,
    IPAddress,
    Transaction,
    Vulnerability,
)
from app.modules.risk_memory import RiskMemoryService

logger = get_logger(__name__)


class KnowledgeGraphService:
    def __init__(self, session: Session):
        self.s = session
        self.rm = RiskMemoryService(session)

    # ------------------------------------------------------------ investigation graph
    def investigation_graph(self, code: str) -> dict:
        inv = self.s.scalar(select(Investigation).where(Investigation.code == code))
        if not inv:
            raise NotFoundError(f"Unknown investigation '{code}'")

        g = nx.Graph()
        root = f"investigation:{inv.code}"
        g.add_node(root, label=inv.code, type="investigation",
                   meta={"title": inv.title, "severity": inv.severity, "status": inv.status})

        # Primary anchors.
        if inv.primary_customer_id:
            self._add_customer(g, root, inv.primary_customer_id, "subject_of")
        if inv.primary_endpoint_id:
            self._add_endpoint(g, root, inv.primary_endpoint_id, "affected_infrastructure")
        if inv.vulnerability_id:
            v = self.s.get(Vulnerability, inv.vulnerability_id)
            if v:
                self._add(g, f"vulnerability:{v.vuln_ref}", v.vuln_ref, "vulnerability", root,
                          "triggered_by", meta={"title": v.title, "severity": v.severity,
                                                "type": v.disclosure_type})

        # Evidence-sourced entities.
        evidence = self.s.scalars(select(Evidence).where(Evidence.investigation_id == inv.id)).all()
        for e in evidence:
            if not e.source_entity_type or not e.source_entity_id:
                continue
            self._add_evidence_entity(g, root, e.source_entity_type, e.source_entity_id, e.category)

        # Blast Radius: connect top affected customers.
        recon = (inv.meta or {}).get("reconstruction") or {}
        for tc in recon.get("top_customers", [])[:6]:
            cust = self.s.scalar(select(Customer).where(Customer.customer_ref == tc["ref"]))
            if cust:
                self._add_customer(g, root, cust.id, "exposed")

        return self._serialize(g, root)

    # ------------------------------------------------------------ node context
    def node_context(self, node_type: str, node_id: str) -> dict:
        if node_type == "customer":
            c = self.s.get(Customer, node_id) or self.s.scalar(
                select(Customer).where(Customer.customer_ref == node_id))
            if not c:
                raise NotFoundError("Customer not found")
            prof = self.rm.get_customer_profile(c.id)
            return {"type": "customer", "ref": c.customer_ref, "name": c.full_name,
                    "customer_type": c.customer_type, "region": c.region, "risk_memory": prof}
        if node_type == "device":
            d = self.s.get(Device, node_id)
            if not d:
                raise NotFoundError("Device not found")
            return {"type": "device", "fingerprint": d.fingerprint, "os": d.os,
                    "browser": d.browser, "trust_score": d.trust_score,
                    "first_seen": d.first_seen.isoformat(), "last_seen": d.last_seen.isoformat()}
        if node_type == "ip":
            ip = self.s.get(IPAddress, node_id)
            if not ip:
                raise NotFoundError("IP not found")
            return {"type": "ip", "address": ip.address, "country": ip.country, "city": ip.city,
                    "isp": ip.isp, "reputation_score": ip.reputation_score}
        if node_type == "endpoint":
            ep = self.s.get(Endpoint, node_id) or self.s.scalar(
                select(Endpoint).where(Endpoint.endpoint_ref == node_id))
            if not ep:
                raise NotFoundError("Endpoint not found")
            return {"type": "endpoint", "ref": ep.endpoint_ref, "name": ep.name,
                    "category": ep.category, "criticality": ep.criticality,
                    "encryption_profile": ep.encryption_profile,
                    "data_sensitivity": ep.data_sensitivity}
        raise NotFoundError(f"Unsupported node type '{node_type}'")

    # ------------------------------------------------------------ builders
    def _add(self, g, node_id, label, ntype, parent, relation, meta=None):
        if node_id not in g:
            g.add_node(node_id, label=label, type=ntype, meta=meta or {})
        g.add_edge(parent, node_id, relation=relation)

    def _add_customer(self, g, parent, customer_id, relation):
        c = self.s.get(Customer, customer_id)
        if not c:
            return
        prof = self.rm.get_customer_profile(c.id) or {}
        self._add(g, f"customer:{c.id}", c.customer_ref, "customer", parent, relation,
                  meta={"name": c.full_name, "type": c.customer_type,
                        "trust": prof.get("trust_score"), "region": c.region})

    def _add_endpoint(self, g, parent, endpoint_id, relation):
        ep = self.s.get(Endpoint, endpoint_id)
        if not ep:
            return
        self._add(g, f"endpoint:{ep.id}", ep.endpoint_ref, "endpoint", parent, relation,
                  meta={"name": ep.name, "criticality": ep.criticality,
                        "cipher": ep.encryption_profile})

    def _add_evidence_entity(self, g, root, etype, eid, category):
        if etype == "customer":
            c = self.s.get(Customer, eid) or self.s.scalar(
                select(Customer).where(Customer.customer_ref == eid))
            if c:
                self._add_customer(g, root, c.id, category)
        elif etype == "device":
            d = self.s.get(Device, eid)
            if d:
                self._add(g, f"device:{d.id}", d.fingerprint[:14], "device", root, category,
                          meta={"os": d.os, "browser": d.browser, "trust": d.trust_score})
        elif etype == "ip":
            ip = self.s.get(IPAddress, eid)
            if ip:
                self._add(g, f"ip:{ip.id}", ip.address, "ip", root, category,
                          meta={"country": ip.country, "reputation": ip.reputation_score})
        elif etype == "endpoint":
            self._add_endpoint(g, root, self._endpoint_id(eid), category)
        elif etype == "transaction":
            t = self.s.scalar(select(Transaction).where(Transaction.txn_ref == eid))
            if t:
                self._add(g, f"transaction:{t.txn_ref}", t.txn_ref[:14], "transaction", root,
                          category, meta={"amount": float(t.amount or 0), "category": t.category})
        elif etype == "vulnerability":
            v = self.s.scalar(select(Vulnerability).where(Vulnerability.vuln_ref == eid))
            if v:
                self._add(g, f"vulnerability:{v.vuln_ref}", v.vuln_ref, "vulnerability", root,
                          category, meta={"title": v.title, "severity": v.severity})

    def _endpoint_id(self, ref_or_id: str) -> str | None:
        ep = self.s.get(Endpoint, ref_or_id) or self.s.scalar(
            select(Endpoint).where(Endpoint.endpoint_ref == ref_or_id))
        return ep.id if ep else None

    # ------------------------------------------------------------ layout / serialize
    @staticmethod
    def _serialize(g: nx.Graph, root: str) -> dict:
        # Deterministic layout; root fixed at centre.
        pos = nx.spring_layout(g, seed=42, k=1.1, iterations=80)
        nodes = []
        for nid, data in g.nodes(data=True):
            x, y = pos[nid]
            nodes.append({"id": nid, "label": data.get("label", nid),
                          "type": data.get("type", "entity"),
                          "x": round(float(x), 4), "y": round(float(y), 4),
                          "degree": g.degree(nid), "is_root": nid == root,
                          "meta": data.get("meta", {})})
        edges = [{"source": u, "target": v, "relation": d.get("relation", "related")}
                 for u, v, d in g.edges(data=True)]
        type_counts: dict[str, int] = {}
        for n in nodes:
            type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1
        return {"nodes": nodes, "edges": edges,
                "stats": {"node_count": len(nodes), "edge_count": len(edges),
                          "by_type": type_counts}}
