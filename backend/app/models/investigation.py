"""The investigation and everything that references it: evidence, business impact,
AI narratives, recommendations, reports — plus the Risk Memory behavioural store.

Investigations never embed these; they are separate tables joined by foreign keys so
history is preserved and assessments can evolve independently.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

from .base import CreatedAtMixin, TimestampMixin, UUIDMixin, utcnow

_BIGPK = BigInteger().with_variant(Integer, "sqlite")


class Investigation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "investigations"

    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)  # ARG-2026-0001
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)  # 0..100
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    originating_engine: Mapped[str] = mapped_column(String(16), index=True)
    lifecycle_stage: Mapped[str] = mapped_column(String(16), default="detected")
    business_priority: Mapped[str] = mapped_column(String(4), default="P3", index=True)
    assigned_analyst_id: Mapped[str | None] = mapped_column(ForeignKey("analysts.id"), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Convenience denormalized anchors (also modelled relationally via evidence).
    primary_customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    primary_endpoint_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    vulnerability_id: Mapped[str | None] = mapped_column(ForeignKey("vulnerabilities.id"), nullable=True)

    # Confidence breakdown, feature contributions, predicted next step, entity roster.
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )


class Evidence(CreatedAtMixin, Base):
    """One observation supporting an investigation. Immutable once created."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(_BIGPK, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    category: Mapped[str] = mapped_column(String(24), index=True)
    evidence_type: Mapped[str] = mapped_column(String(48))
    source_module: Mapped[str] = mapped_column(String(24))
    source_entity_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    source_entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    confidence_contribution: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    event_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    ledger_ref: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    investigation: Mapped["Investigation"] = relationship(back_populates="evidence")


class RiskMemory(TimestampMixin, Base):
    """Evolving behavioural profile per monitored entity. Continuously updated, never
    recalculated from scratch. Provides context; it never declares behaviour suspicious.
    """

    __tablename__ = "risk_memory"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_risk_entity"),
        Index("idx_risk_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(_BIGPK, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[str] = mapped_column(String(64))

    trust_score: Mapped[float] = mapped_column(Float, default=0.5)          # how consistent
    behavioural_confidence: Mapped[float] = mapped_column(Float, default=0.1)  # how well known
    baseline_confidence: Mapped[float] = mapped_column(Float, default=0.1)

    amt_mean: Mapped[float] = mapped_column(Float, default=0.0)
    amt_median: Mapped[float] = mapped_column(Float, default=0.0)
    amt_std: Mapped[float] = mapped_column(Float, default=1.0)
    amt_max: Mapped[float] = mapped_column(Float, default=0.0)
    txn_frequency_daily: Mapped[float] = mapped_column(Float, default=0.0)
    auth_success_rate: Mapped[float] = mapped_column(Float, default=1.0)

    preferred_hours: Mapped[list] = mapped_column(JSON, default=list)     # [int hours]
    normal_countries: Mapped[list] = mapped_column(JSON, default=list)
    preferred_devices: Mapped[list] = mapped_column(JSON, default=list)   # [fingerprint]
    home_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    observation_count: Mapped[int] = mapped_column(default=0)
    historical_anomalies: Mapped[int] = mapped_column(default=0)
    false_positives: Mapped[int] = mapped_column(default=0)
    true_positives: Mapped[int] = mapped_column(default=0)
    behavioural_variance: Mapped[float] = mapped_column(Float, default=0.0)
    decay_factor: Mapped[float] = mapped_column(Float, default=0.98)
    last_recalculated: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    history: Mapped[list] = mapped_column(JSON, default=list)  # snapshots of trust over time


class BusinessImpact(CreatedAtMixin, Base):
    __tablename__ = "business_impact"

    id: Mapped[int] = mapped_column(_BIGPK, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    financial_exposure: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    affected_customers: Mapped[int] = mapped_column(default=0)
    affected_accounts: Mapped[int] = mapped_column(default=0)
    customer_segmentation: Mapped[dict] = mapped_column(JSON, default=dict)
    data_sensitivity: Mapped[str] = mapped_column(String(32), default="pii")
    infrastructure_criticality: Mapped[str] = mapped_column(String(16), default="medium")
    operational_disruption: Mapped[str] = mapped_column(String(32), default="moderate")
    regulatory_flags: Mapped[list] = mapped_column(JSON, default=list)
    executive_priority: Mapped[str] = mapped_column(String(4), default="P3")
    executive_severity: Mapped[str] = mapped_column(String(16), default="medium")
    estimated_remediation_cost: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    business_confidence: Mapped[float] = mapped_column(Float, default=0.7)
    recommended_urgency: Mapped[str] = mapped_column(String(24), default="standard")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AINarrative(CreatedAtMixin, Base):
    __tablename__ = "ai_narratives"

    id: Mapped[int] = mapped_column(_BIGPK, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    provider: Mapped[str] = mapped_column(String(24), default="offline")  # openrouter|offline
    model_id: Mapped[str] = mapped_column(String(80), default="offline-grounded")
    prompt_version: Mapped[str] = mapped_column(String(16), default="v1")
    executive_summary: Mapped[str] = mapped_column(Text, default="")
    technical_summary: Mapped[str] = mapped_column(Text, default="")
    confidence_explanation: Mapped[str] = mapped_column(Text, default="")
    evidence_summary: Mapped[str] = mapped_column(Text, default="")
    recommended_action_summary: Mapped[str] = mapped_column(Text, default="")
    structured_refs: Mapped[dict] = mapped_column(JSON, default=dict)
    grounded: Mapped[bool] = mapped_column(Boolean, default=True)
    generation_ms: Mapped[int] = mapped_column(default=0)
    regeneration_count: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(_BIGPK, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    rec_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(4), default="P3")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    investigation: Mapped["Investigation"] = relationship(back_populates="recommendations")


class Report(CreatedAtMixin, Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(_BIGPK, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    report_type: Mapped[str] = mapped_column(String(24), index=True)
    export_format: Mapped[str] = mapped_column(String(8), default="pdf")
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="generating")
    document_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    version: Mapped[int] = mapped_column(default=1)
    author: Mapped[str] = mapped_column(String(64), default="ARGUS")
    integrity_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generation_ms: Mapped[int] = mapped_column(default=0)


class AnalystAction(CreatedAtMixin, Base):
    """Audit trail of human decisions on an investigation (assign/escalate/close/etc.)."""

    __tablename__ = "analyst_actions"

    id: Mapped[int] = mapped_column(_BIGPK, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    action: Mapped[str] = mapped_column(String(48))
    actor: Mapped[str] = mapped_column(String(64), default="analyst")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
