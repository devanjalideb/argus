"""JWT authentication + password hashing (Infrastructure layer).

Basic bearer-token auth architected so role-based authorization can be added later
without structural change. Endpoints are intentionally left open in the MVP demo; the
`current_user` dependency is available to protect routes when required.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Analyst

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login",
                                     auto_error=False)


def hash_password(pw: str) -> str:
    # bcrypt caps at 72 bytes; slice defensively.
    return bcrypt.hashpw(pw.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def current_user(token: str | None = Depends(oauth2_scheme),
                 db: Session = Depends(get_db)) -> Analyst:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.scalar(select(Analyst).where(Analyst.username == payload.get("sub")))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user


def ensure_default_users(db: Session) -> None:
    """Seed a default analyst so login works out of the box."""
    if db.scalar(select(Analyst).where(Analyst.username == "analyst")):
        return
    db.add(Analyst(username="analyst", full_name="S. Sharma", email="analyst@argus.local",
                   role="analyst", hashed_password=hash_password("analyst123"), is_active=True))
    db.commit()
