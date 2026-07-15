"""ARGUS FastAPI application entrypoint (API + Infrastructure layers).

Run (from backend/):  uvicorn app.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import check_connection
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.response import success

configure_logging(settings.log_level)
logger = get_logger("app.main")

# frontend/dist (React build) is served in production; absent during development.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s v%s [%s]", settings.app_name, __version__, settings.environment)
    if check_connection():
        logger.info("Database connectivity OK (%s).", settings.mysql_db)
        try:
            from app.core.database import SessionLocal
            from app.core.security import ensure_default_users
            with SessionLocal() as db:
                ensure_default_users(db)
        except Exception as exc:  # noqa: BLE001 — non-fatal (e.g. tables not migrated yet)
            logger.warning("Default user seeding skipped: %s", exc)
    else:
        logger.warning("Database unreachable at startup — /system/ready will report not-ready.")
    live_ai = settings.ai_enabled and bool(settings.openrouter_api_key)
    logger.info("AI Decision Layer: %s", "OpenRouter (live)" if live_ai else "offline grounded fallback")
    yield
    logger.info("Shutting down %s.", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/api", tags=["root"])
    def api_root():
        return success({
            "app": settings.app_name,
            "tagline": "We don't generate alerts. We generate decisions.",
            "version": __version__,
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/system/health",
        })

    # Serve the compiled React app when present (production / after `npm run build`).
    # /assets is served statically; every other non-API path falls back to index.html
    # so client-side routes (e.g. /investigation/ARG-2026-0001) resolve on hard refresh.
    if FRONTEND_DIST.exists():
        assets = FRONTEND_DIST / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")
        index_file = FRONTEND_DIST / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            if full_path.startswith("api"):
                raise HTTPException(status_code=404, detail="Not found")
            candidate = FRONTEND_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(index_file))

        logger.info("Serving compiled frontend from %s", FRONTEND_DIST)

    return app


app = create_app()
