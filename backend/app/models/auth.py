"""Analyst / user accounts for JWT authentication and investigation ownership."""
from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

from .base import TimestampMixin, UUIDMixin


class Analyst(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "analysts"

    username: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    role: Mapped[str] = mapped_column(String(24), default="analyst")
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
