"""Core banking & infrastructure entities (stable identities, not activity).

Behaviour lives in Risk Memory; operational activity lives in the event tables.
These tables model *who* and *what* exists in the bank.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

from .base import CreatedAtMixin, TimestampMixin, UUIDMixin


class Customer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    customer_ref: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    customer_type: Mapped[str] = mapped_column(String(24), index=True)
    tier: Mapped[str] = mapped_column(String(24), default="standard")
    risk_classification: Mapped[str] = mapped_column(String(16), default="low")
    onboarding_date: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="active")
    preferred_channel: Mapped[str] = mapped_column(String(16), default="mobile")
    region: Mapped[str] = mapped_column(String(48), default="IN")
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)

    accounts: Mapped[list["Account"]] = relationship(back_populates="customer")


class Account(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "accounts"

    account_number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    account_type: Mapped[str] = mapped_column(String(24), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    current_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")
    tier: Mapped[str] = mapped_column(String(24), default="standard")
    branch_id: Mapped[str] = mapped_column(String(16), default="BR-DEL-01")
    opened_at: Mapped[datetime] = mapped_column(DateTime)

    customer: Mapped["Customer"] = relationship(back_populates="accounts")


class Location(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "locations"

    country: Mapped[str] = mapped_column(String(48), index=True)
    city: Mapped[str] = mapped_column(String(64))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(48), default="Asia/Kolkata")
    region: Mapped[str] = mapped_column(String(48), default="APAC")

    __table_args__ = (Index("idx_location_country_city", "country", "city"),)


class Device(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "devices"

    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    os: Mapped[str] = mapped_column(String(48))
    browser: Mapped[str] = mapped_column(String(48))
    manufacturer: Mapped[str | None] = mapped_column(String(48), nullable=True)
    category: Mapped[str] = mapped_column(String(16), default="mobile")  # mobile|desktop|tablet
    first_seen: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)
    trust_score: Mapped[float] = mapped_column(Float, default=0.5)


class IPAddress(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ip_addresses"

    address: Mapped[str] = mapped_column(String(45), unique=True, index=True)
    asn: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str] = mapped_column(String(48), default="India")
    city: Mapped[str] = mapped_column(String(64), default="Delhi")
    isp: Mapped[str] = mapped_column(String(96), default="Unknown ISP")
    reputation_score: Mapped[float] = mapped_column(Float, default=0.5)
    first_seen: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)
    investigation_count: Mapped[int] = mapped_column(default=0)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True)


class Endpoint(UUIDMixin, TimestampMixin, Base):
    """Banking infrastructure asset. Blast Radius reconstruction targets endpoints."""

    __tablename__ = "endpoints"

    endpoint_ref: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(32), index=True)
    service_owner: Mapped[str] = mapped_column(String(64), default="Platform Engineering")
    application: Mapped[str] = mapped_column(String(64), default="core-banking")
    environment: Mapped[str] = mapped_column(String(16), default="production")
    encryption_profile: Mapped[str] = mapped_column(String(80), default="TLS1.3-AES256-GCM")
    security_posture: Mapped[str] = mapped_column(String(16), default="hardened")
    criticality: Mapped[str] = mapped_column(String(16), default="medium", index=True)
    data_sensitivity: Mapped[str] = mapped_column(String(32), default="pii")
    status: Mapped[str] = mapped_column(String(16), default="operational")
    active_from: Mapped[datetime] = mapped_column(DateTime)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
