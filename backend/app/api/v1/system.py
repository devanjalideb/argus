"""System APIs: health, readiness and diagnostics for developers and judges."""
from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.core.config import settings
from app.core.database import check_connection
from app.core.response import success

router = APIRouter(prefix="/system", tags=["system"])


def _ai_provider() -> str:
    """Reflect the actual configured LLM provider (Gemini via OpenAI-compat, OpenRouter,
    or the offline grounded fallback)."""
    if not (settings.ai_enabled and settings.openrouter_api_key):
        return "offline-grounded-fallback"
    return "gemini" if "googleapis" in settings.openrouter_base_url else "openrouter"


@router.get("/health", summary="Liveness probe")
def health():
    """Confirms the application process is up and serving requests."""
    return success({
        "status": "ok",
        "app": settings.app_name,
        "version": __version__,
        "environment": settings.environment,
    })


@router.get("/ready", summary="Readiness probe")
def ready():
    """Verifies database connectivity and AI provider configuration."""
    db_ok = check_connection()
    return success({
        "ready": db_ok,
        "checks": {
            "database": "ok" if db_ok else "unreachable",
            "ai_provider": _ai_provider(),
            "ai_live": bool(settings.ai_enabled and settings.openrouter_api_key),
        },
    })


@router.get("/info", summary="Application & integration diagnostics")
def info():
    """Non-secret configuration surface for the Integrations page."""
    return success({
        "app": settings.app_name,
        "description": settings.app_description,
        "version": __version__,
        "environment": settings.environment,
        "database": {
            "engine": "mysql" if settings.is_mysql else "other",
            "host": settings.mysql_host,
            "port": settings.mysql_port,
            "database": settings.mysql_db,
            "connected": check_connection(),
        },
        "ai": {
            "enabled": settings.ai_enabled,
            "provider": _ai_provider(),
            "model": settings.openrouter_model,
            "live": bool(settings.ai_enabled and settings.openrouter_api_key),
        },
        "api_prefix": settings.api_v1_prefix,
    })
