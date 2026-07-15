# ARGUS — Architecture

## Layers (strict downward dependency)
1. **Presentation** — React/TS. Visualization only; no business logic.
2. **API** — FastAPI routers. Validate requests, delegate to services, format the response
   envelope. No business logic in routes.
3. **AI Decision** — turns structured investigations into grounded narratives (OpenRouter or
   offline). Consumes only validated evidence; never touches raw data.
4. **Core Intelligence** — Risk Memory, Watchtower, Blast Radius, Business Impact, Knowledge Graph.
5. **Data** — SQLAlchemy models + the immutable **event ledger** (the spine).
6. **Infrastructure** — config, logging, database, security, error handling.

## The central object: the Investigation
Every module either **creates, enriches, explains, visualizes, or resolves** investigations.
Evidence, Business Impact, AI Narratives, Recommendations and Reports are all separate tables
referencing the Investigation, so history is preserved and assessments evolve independently.

## Module contracts

| Module | Owns | Public surface |
|---|---|---|
| `ingestion` | validate → normalize (UTC) → enrich → commit to ledger → audit | `IngestionService.ingest_*` |
| `risk_memory` | evolving per-entity behavioural profiles (trust vs confidence, decay, feedback) | `get_*_profile`, `recompute_all`, `apply_feedback` |
| `watchtower` | feature engineering vs Risk Memory + Isolation Forest + correlation rules → investigations | `WatchtowerService.analyze` |
| `blast_radius` | disclosure-triggered deterministic ledger replay → retrospective investigations | `reconstruct`, `analyze_all` |
| `business_impact` | ₹ exposure, segmentation, regulatory, executive priority (≠ severity), recommendations | `BusinessImpactService.assess` |
| `explain` | grounded executive/technical/confidence/evidence/action narratives + hallucination guard | `ExplainService.generate` |
| `knowledge_graph` | NetworkX subgraph built on demand from relational data + node context | `investigation_graph`, `node_context` |
| `reporting` | ReportLab PDF + JSON + CSV, versioned + hashed | `ReportService.generate` |
| `investigations` | lifecycle + list/detail serialization | `InvestigationService` |
| `pipeline` | orchestrates reset → Risk Memory → Watchtower → Blast Radius → enrichment | `run_detection` |

## Data flow
```
event  ->  ingestion  ->  event_ledger (immutable)
                             |
        Risk Memory  <-------+-------> Watchtower --------\
                             |                             > Investigation + Evidence
        Blast Radius  <------+  (disclosure replay) ------/
                             v
                    Business Impact  ->  Explainable AI  ->  Knowledge Graph  ->  Reports
```

## Key engineering decisions
- **Isolation Forest** — unlabelled outlier detection; one input to a transparent confidence score.
- **Deterministic Blast Radius** — reconstruction must be exact and auditable; SQL over an
  immutable ledger beats probabilistic inference.
- **Business priority ≠ technical severity** — a simple credential compromise touching thousands
  of active customers can outrank a sophisticated attack on an isolated test system.
- **LLM explains, never decides** — deterministic detection/logic + grounded narration with an
  offline fallback, so the platform is trustworthy, testable and network-independent.
- **MySQL in production, SQLite for tests** — same SQLAlchemy models; one connection-string switch.
