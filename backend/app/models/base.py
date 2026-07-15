"""Shared model primitives: UUID/timestamp mixins and helpers."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


def gen_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Naive UTC timestamp (MySQL DATETIME has no timezone; we standardize on UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UUIDMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class CreatedAtMixin:
    """For immutable records (evidence, ledger, narratives) — created only, never updated."""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
