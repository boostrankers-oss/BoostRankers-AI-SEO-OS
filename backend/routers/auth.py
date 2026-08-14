from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from schemas.auth import LoginRequest, RegisterRequest
from services.auth_service import register_user, authenticate_user

router = APIRouter()


@router.post("/signup", response_model=dict)
def signup(
    user: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new client account.

    RegisterRequest is used intentionally here instead of the legacy
    UserCreate schema because the frontend sends first_name, last_name,
    confirm_password, and company_name. This prevents those fields from
    being stripped before they reach AuthService.
    """
    return register_user(db, user)


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