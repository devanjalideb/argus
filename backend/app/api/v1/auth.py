"""Authentication APIs — JWT login + current user."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ArgusError
from app.core.response import success
from app.core.security import create_access_token, current_user, verify_password
from app.models import Analyst

router = APIRouter(prefix="/auth", tags=["auth"])


class Unauthorized(ArgusError):
    status_code = 401
    code = "unauthorized"


@router.post("/login", summary="Obtain a JWT access token")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(Analyst).where(Analyst.username == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        raise Unauthorized("Invalid username or password")
    token = create_access_token(user.username, user.role)
    return success({"access_token": token, "token_type": "bearer",
                    "user": {"username": user.username, "full_name": user.full_name,
                             "role": user.role}})


@router.get("/me", summary="Current authenticated analyst")
def me(user: Analyst = Depends(current_user)):
    return success({"username": user.username, "full_name": user.full_name,
                    "role": user.role, "email": user.email})
