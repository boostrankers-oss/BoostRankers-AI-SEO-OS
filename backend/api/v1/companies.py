from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from database.session import get_db

from schemas.auth import (
    LoginRequest,
    RegisterRequest,
)

from schemas.token import (
    TokenResponse,
)

from services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

@router.post(
    "/register",
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):

    service = AuthService(db)

    return service.register(request)
    
@router.post(
    "/login",
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):

    service = AuthService(db)

    return service.login(request)
    
from pydantic import BaseModel


class RefreshRequest(BaseModel):

    refresh_token: str


@router.post(
    "/refresh",
)
def refresh(
    request: RefreshRequest,
    db: Session = Depends(get_db),
):

    service = AuthService(db)

    return service.refresh(
        request.refresh_token
    )
    
@router.post(
    "/logout",
)
def logout(
    request: RefreshRequest,
    db: Session = Depends(get_db),
):

    service = AuthService(db)

    return service.logout(
        request.refresh_token
    )
    
from api.deps.current_user import (
    get_current_user,
)

from models.user import User


@router.get(
    "/me",
)
def me(
    current_user: User = Depends(
        get_current_user
    ),
):

    return current_user