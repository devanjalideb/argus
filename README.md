# ARGUS — AI Cyber Decision Intelligence Platform

> **"We don't generate alerts. We generate decisions."**

ARGUS is a production-inspired banking cybersecurity **investigation** platform. Modern banks
already drown in alerts; the hard problem is *understanding what actually happened*. ARGUS
automatically constructs complete investigations that answer six questions — **what happened,
why was it detected, what evidence supports it, what is the business impact, who was affected,
and what should the bank do next** — for both live threats and historically-disclosed weaknesses.

Built for **FinSpark'26 · Problem Statement 2** (correlate cybersecurity telemetry with
transactional behaviour, including harvest-now-decrypt-later quantum risk).

---

## Two complementary intelligence engines

| | **Watchtower** (forward) | **Blast Radius** (retrospective) |
|---|---|---|
| Question | "Is this happening now?" | "Now that we know this weakness existed, what happened before we found it?" |
| Method | Isolation Forest scored against each entity's **own** Risk Memory baseline + deterministic correlation | Deterministic SQL replay of the immutable event ledger over the exposure window |
| Detects | Account takeover, credential stuffing, insider misuse, API abuse | Weak-cipher (Sweet32) exposure, quantum harvest-now-decrypt-later |

Both converge on one **Business Impact** assessment (₹ exposure, affected customers, regulatory
obligations, executive priority), a strictly-grounded **Explainable AI** narrative, a **Knowledge
Graph**, deterministic **Recommendations**, and exportable **Reports**.

---

## Tech stack

- **Backend:** FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 (modular monolith, six layers)
- **Database:** MySQL 8 (SQLite used only for the portable test suite)
- **Intelligence:** scikit-learn (Isolation Forest) · NetworkX · deterministic SQL & rules
- **AI Decision Layer:** OpenRouter *(optional)* with a fully **offline grounded narrator** fallback
- **Reports:** ReportLab (PDF) + JSON + CSV
- **Frontend:** React + TypeScript + Vite (calm, executive, investigation-first UI)
- **Deploy:** Docker + Docker Compose

---

## Quick start

You need a running **MySQL 8** and its root password. Three ways to run:

### Option A — Windows (native)
```powershell
# 1. set your MySQL password
notepad backend\.env        # set MYSQL_PASSWORD=...

# 2. one-time setup (venv, deps, frontend build, migrate, seed, run engines)
.\scripts\setup.ps1

# 3. launch  ->  http://localhost:8000
.\scripts\run.ps1
```

### Option B — macOS / Linux (native)
```bash
# set MYSQL_PASSWORD in backend/.env, then:
./scripts/run.sh            # sets up venv+build+migrate+seed on first run, then serves
```

### Option C — Docker (bundles MySQL, zero local deps)
```bash
docker compose up --build   #  ->  http://localhost:8000
```

Open **http://localhost:8000**. Click **"Rebuild demo"** (top-right) any time to regenerate the
synthetic ecosystem and re-run every engine end to end.

> **AI note:** ARGUS works with **no internet and no API key** — the offline grounded narrator
> produces the explanations. To use a live LLM, set `OPENROUTER_API_KEY` in `backend/.env`.

Default login (JWT is wired but not enforced in the demo): `analyst` / `analyst123`.

---

## The application (9 screens)

`Investigation Queue` · `Investigation Workspace` · `Watchtower` · `Blast Radius` ·
`Risk Memory` · `Knowledge Graph` · `Reports` · `Integrations` · `Settings`

The **Investigation Workspace** is the heart of the product: executive summary → chronological
timeline → categorized evidence (with confidence contributions) → Business Impact → confidence
breakdown → multi-audience AI narratives → recommendations → knowledge graph — one continuous
investigation, no context switching.

---

## Testing

```bash
cd backend && .venv/Scripts/python -m pytest -q     # (or .venv/bin/python on *nix)
```

The suite runs against a throwaway SQLite database (no MySQL needed) and includes the
**Blast Radius exact-reconstruction spine**: reconstruction must equal the ledger ground truth,
no more and no less.

---

## Architecture

Six layers, each talking only to the one beneath it:

```
Presentation (React)  ->  API (FastAPI routers)  ->  AI Decision (grounded narratives)
   ->  Core Intelligence (Risk Memory, Watchtower, Blast Radius, Business Impact,
        Knowledge Graph)  ->  Data (SQLAlchemy models + immutable event ledger)  ->  Infrastructure
```

Data lifecycle: **raw events → normalized ledger → correlated evidence → investigations →
business decisions → executive reports.** Every stage increases the value of the information.

```
backend/
  app/
    core/         config, logging, database, security, response envelope, exceptions
    models/       Customer, Account, Device, IP, Session, AuthEvent, Transaction, Endpoint,
                  Vulnerability, EventLedger, Investigation, Evidence, RiskMemory,
                  BusinessImpact, AINarrative, Recommendation, Report, Analyst
    modules/      ingestion · risk_memory · watchtower · blast_radius · business_impact ·
                  knowledge_graph · explain · reporting · investigations · pipeline
    api/v1/       thin routers (one per capability) — business logic stays in services
    synthetic/    deterministic banking ecosystem + 6 investigation scenarios
  alembic/        versioned migrations
  tests/          unit + integration + e2e (SQLite)
frontend/         React + TS + Vite (served compiled by FastAPI in production)
deployment/       entrypoint
docs/             DEMO.md, ARCHITECTURE.md
scripts/          setup / run / seed
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for module contracts and
[`docs/DEMO.md`](docs/DEMO.md) for the judge walkthrough and Q&A.

API docs are live at **/docs** (OpenAPI) when the server is running.
