from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.database import get_db
from schemas.auth import LoginRequest, RegisterRequest
from services.auth_service import register_user, authenticate_user, AuthService

router = APIRouter()


@router.post("/register", response_model=dict)
def register(
    user: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Canonical registration endpoint used by the current frontend.
    """
    return register_user(db, user)


@router.post("/signup", response_model=dict)
def signup(
    user: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Backward-compatible registration alias.
    """
    return register_user(db, user)


@router.post("/login", response_model=dict)
def login(
    user_credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate user and return JWT tokens.
    """
    return authenticate_user(
        db,
        user_credentials.email,
        user_credentials.password,
    )

class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=dict)
def refresh(
    request: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Refresh the current JWT access token using a valid refresh token."""
    service = AuthService(db)
    return service.refresh(request.refresh_token)


@router.post("/logout", response_model=dict)
def logout(
    request: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Revoke the supplied refresh token and end the current session."""
    service = AuthService(db)
    return service.logout(request.refresh_token)
