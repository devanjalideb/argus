"""Operational activity: sessions, authentication events, transactions, and the
immutable normalized event ledger that ingestion writes and every engine reads.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

from .base import CreatedAtMixin, UUIDMixin, utcnow

# BigInteger PK that degrades to Integer under SQLite (used by unit tests).
_BIGPK = BigInteger().with_variant(Integer, "sqlite")


class Session(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "sessions"

    session_ref: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True, nullable=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    ip_id: Mapped[str | None] = mapped_column(ForeignKey("ip_addresses.id"), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(16), default="closed")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    auth_strength: Mapped[str] = mapped_column(String(16), default="password")
    behaviour_summary: Mapped[dict] = mapped_column(JSON, default=dict)


class AuthEvent(CreatedAtMixin, Base):
    __tablename__ = "auth_events"

    id: Mapped[int] = mapped_column(_BIGPK, primary_key=True, autoincrement=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    result: Mapped[str] = mapped_column(String(16), index=True)
    method: Mapped[str] = mapped_column(String(24), default="password")
    factor: Mapped[str] = mapped_column(String(24), default="single")
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True, nullable=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    ip_id: Mapped[str | None] = mapped_column(ForeignKey("ip_addresses.id"), nullable=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    session_ref: Mapped[str | None] = mapped_column(String(48), index=True, nullable=True)
    endpoint_id: Mapped[str | None] = mapped_column(ForeignKey("endpoints.id"), index=True, nullable=True)
    browser: Mapped[str | None] = mapped_column(String(48), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (Index("idx_auth_customer_time", "customer_id", "event_time"),)


class Transaction(CreatedAtMixin, Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(_BIGPK, primary_key=True, autoincrement=True)
    txn_ref: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    source_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), index=True, nullable=True)
    dest_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    dest_external: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True, nullable=True)
    session_ref: Mapped[str | None] = mapped_column(String(48), index=True, nullable=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    ip_id: Mapped[str | None] = mapped_column(ForeignKey("ip_addresses.id"), nullable=True)
    auth_event_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    endpoint_id: Mapped[str | None] = mapped_column(ForeignKey("endpoints.id"), index=True, nullable=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    category: Mapped[str] = mapped_column(String(24), index=True)
    channel: Mapped[str] = mapped_column(String(16), default="mobile")
    status: Mapped[str] = mapped_column(String(16), default="completed")
    fraud_status: Mapped[str] = mapped_column(String(16), default="none")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("idx_txn_endpoint_time", "endpoint_id", "event_time"),
        Index("idx_txn_customer_time", "customer_id", "event_time"),
    )


class EventLedger(Base):
    """Immutable, normalized chronological history — the spine of ARGUS.

    Ingestion is the only writer. Blast Radius replays it by endpoint + time window;
    Watchtower and Risk Memory consume it forward. Never mutated after insert.
    """

    __tablename__ = "event_ledger"

    id: Mapped[int] = mapped_column(_BIGPK, primary_key=True, autoincrement=True)
    event_uid: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(24), index=True)
    event_category: Mapped[str] = mapped_column(String(24), default="operational")
    event_source: Mapped[str] = mapped_column(String(32), default="core-banking")
    event_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ip_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    session_ref: Mapped[str | None] = mapped_column(String(48), index=True, nullable=True)
    endpoint_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    investigation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ref_table: Mapped[str | None] = mapped_column(String(24), nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        # Blast Radius depends on this composite index for exact window reconstruction.
        Index("idx_ledger_endpoint_time", "endpoint_id", "event_time"),
        Index("idx_ledger_customer_time", "customer_id", "event_time"),
        Index("idx_ledger_type_time", "event_type", "event_time"),
    )


class IngestionAudit(Base):
    """One row per ingested request: what entered, when, and how it was processed."""

    __tablename__ = "ingestion_audit"

    id: Mapped[int] = mapped_column(_BIGPK, primary_key=True, autoincrement=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    event_type: Mapped[str] = mapped_column(String(24))
    source: Mapped[str] = mapped_column(String(32), default="api")
    validation_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    normalized: Mapped[bool] = mapped_column(Boolean, default=True)
    enriched: Mapped[bool] = mapped_column(Boolean, default=False)
    persisted: Mapped[bool] = mapped_column(Boolean, default=True)
    correlation_id: Mapped[str] = mapped_column(String(36), index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_preview: Mapped[dict] = mapped_column(JSON, default=dict)
