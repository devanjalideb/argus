"""Test harness: a throwaway SQLite database, seeded once and run through the full
detection pipeline. Deterministic and MySQL-free so the suite is portable.
"""
import os
import pathlib
import tempfile

# Point the app at a temp SQLite DB *before* importing any app module (settings caches).
_DB = pathlib.Path(tempfile.gettempdir()) / "argus_test.db"
if _DB.exists():
    _DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB.as_posix()}"
os.environ["AI_ENABLED"] = "true"
os.environ["OPENROUTER_API_KEY"] = ""

import pytest  # noqa: E402

import app.models  # noqa: E402,F401  register models
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.modules.pipeline import run_detection  # noqa: E402
from app.synthetic.seed import run_seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _bootstrap():
    Base.metadata.create_all(engine)
    run_seed(reset=True, num_customers=15, baseline_days=30)
    with SessionLocal() as s:
        run_detection(s, reset=True, enrich=True)
    yield


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
