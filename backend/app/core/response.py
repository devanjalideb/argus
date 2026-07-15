"""Standard API response envelope (API layer contract).

Every endpoint — success or failure — returns this shape so the React client never
needs endpoint-specific parsing logic.

    success:  { "success": true,  "data": ..., "meta": {...}, "timestamp": "..." }
    failure:  { "success": false, "error": { "code", "message", "details" },
                "correlation_id": "...", "timestamp": "..." }
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def success(data: Any = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"success": True, "data": data, "timestamp": _now()}
    if meta is not None:
        body["meta"] = meta
    return body


def error(code: str, message: str, details: Any = None,
          correlation_id: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "success": False,
        "error": {"code": code, "message": message, "details": details},
        "timestamp": _now(),
    }
    if correlation_id:
        body["correlation_id"] = correlation_id
    return body


def paginated(items: list[Any], total: int, page: int, page_size: int,
              extra_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    page_count = (total + page_size - 1) // page_size if page_size else 0
    meta = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "page_count": page_count,
        "has_next": page < page_count,
        "has_prev": page > 1,
    }
    if extra_meta:
        meta.update(extra_meta)
    return success(items, meta=meta)
