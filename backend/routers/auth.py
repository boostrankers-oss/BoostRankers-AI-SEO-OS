from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.session import get_db
from schemas.auth import LoginRequest, RegisterRequest
from services.auth_service import (
    AuthService,
    authenticate_user,
    register_user,
)
from api.deps.current_user import get_current_user
from models.client import Client
from models.user import User


router = APIRouter(
    tags=["Authentication"],
)


# ==========================================================
# Register
# ==========================================================

@router.post("/register", response_model=dict)
def register(
    user: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Canonical registration endpoint used by the current frontend."""
    return register_user(db, user)


@router.post("/signup", response_model=dict)
def signup(
    user: RegisterRequest,
    db: Session = Depends(get_db),
):
    """Backward-compatible registration alias."""
    return register_user(db, user)


# ==========================================================
# Login
# ==========================================================

@router.post("/login", response_model=dict)
def login(
    user_credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate a user and return JWT tokens."""
    return authenticate_user(
        db,
        user_credentials.email,
        user_credentials.password,
    )


# ==========================================================
# Refresh
# ==========================================================

class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=dict)
def refresh(
    request: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Refresh the current JWT access token."""
    service = AuthService(db)
    return service.refresh(request.refresh_token)


# ==========================================================
# Logout
# ==========================================================

@router.post("/logout", response_model=dict)
def logout(
    request: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Revoke the supplied refresh token."""
    service = AuthService(db)
    return service.logout(request.refresh_token)


# ==========================================================
# Current User
# ==========================================================

@router.get("/me", response_model=dict)
def me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the authenticated user's profile.

    For single-client accounts, resolve the client record belonging
    to the user's private company and matching signup email.
    """

    client = None

    if current_user.role == "client" and current_user.company_id:
        client = db.scalar(
            select(Client)
            .where(
                Client.company_id == current_user.company_id,
                Client.email == current_user.email,
            )
            .order_by(Client.created_at.asc())
        )

    return {
        "id": current_user.id,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "email": current_user.email,
        "role": current_user.role,
        "company_id": current_user.company_id,
        "client_id": client.id if client else None,
        "account_type": (
            "client"
            if current_user.role == "client"
            else "agency"
        ),
        "is_verified": current_user.is_verified,
    }
