"""Seed entrypoint: (optionally) wipe operational data and regenerate the ecosystem.

Usage (from backend/, venv active):  python -m app.synthetic.seed
"""
from __future__ import annotations

import json

from sqlalchemy import text

import app.models  # noqa: F401 — register all models on Base.metadata
from app.core.database import Base, SessionLocal, ensure_database_exists, engine
from app.core.logging import configure_logging, get_logger
from .generator import SyntheticGenerator

logger = get_logger(__name__)


def wipe(session) -> None:
    """Delete all rows, children first (respects FK constraints on MySQL)."""
    session.execute(text("SET FOREIGN_KEY_CHECKS=0")) if engine.dialect.name == "mysql" else None
    for table in reversed(Base.metadata.sorted_tables):
        if table.name == "alembic_version":
            continue
        session.execute(table.delete())
    if engine.dialect.name == "mysql":
        session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    session.commit()


def run_seed(reset: bool = True, seed: int = 42, num_customers: int = 45,
             baseline_days: int = 75) -> dict:
    ensure_database_exists()
    with SessionLocal() as session:
        if reset:
            logger.info("Wiping existing operational data ...")
            wipe(session)
        gen = SyntheticGenerator(session, seed=seed, num_customers=num_customers,
                                 baseline_days=baseline_days)
        return gen.generate()


def main() -> None:
    configure_logging("INFO")
    summary = run_seed()
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
