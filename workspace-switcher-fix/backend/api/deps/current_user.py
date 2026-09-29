from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from database.database import get_db
from models.user import User
from models.company import Company

from core.jwt import decode_access_token


# ============================================================
# HTTP BEARER
# ============================================================

bearer_scheme = HTTPBearer(
    auto_error=False,
)


# ============================================================
# JWT PAYLOAD
# ============================================================

def _decode_token(
    credentials: HTTPAuthorizationCredentials | None,
) -> dict[str, Any]:

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    token = credentials.credentials.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is missing.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    try:
        payload = decode_access_token(token)

    except (JWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    return payload


# ============================================================
# CURRENT USER
# ============================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:

    payload = _decode_token(credentials)

    # --------------------------------------------------------
    # The current AuthService puts the user ID in `sub`.
    # --------------------------------------------------------

    user_id = payload.get("sub")

    if not user_id:
        # Backward compatibility with tokens that may contain
        # user_id instead of sub.
        user_id = payload.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token does not contain a user identity.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    user = db.scalar(
        select(User).where(
            User.id == str(user_id)
        )
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled.",
        )

    return user


# ============================================================
# CURRENT COMPANY
# ============================================================

def get_current_company(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:

    company_id = getattr(
        current_user,
        "company_id",
        None,
    )

    # Agency workspace context. The frontend sends a client ID only after
    # an agency selects a managed client workspace. Never trust the header
    # by itself: verify that the agency owns the client or has active
    # agency_client_access before changing the request company context.
    workspace_client_id = request.headers.get("X-Workspace-Client-ID")
    agency_roles = {"super_admin", "agency_admin", "manager"}
    if workspace_client_id and str(getattr(current_user, "role", "")).lower() in agency_roles:
        row = db.execute(
            text(
                """
                SELECT c.company_id
                FROM clients c
                WHERE c.id = :client_id
                  AND (
                    c.company_id = :agency_company
                    OR EXISTS (
                      SELECT 1
                      FROM agency_client_access a
                      WHERE a.client_id = c.id
                        AND a.agency_company_id = :agency_company
                        AND a.status = 'active'
                    )
                  )
                LIMIT 1
                """
            ),
            {"client_id": workspace_client_id, "agency_company": str(company_id)},
        ).scalar()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have active access to this client workspace.",
            )
        company_id = str(row)
        # Keep the already-authenticated User object request-scoped so routes
        # that read current_user.company_id directly see the same workspace.
        current_user.company_id = company_id

    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not associated with a company.",
        )

    company = db.scalar(
        select(Company).where(
            Company.id == company_id
        )
    )

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company associated with this account was not found.",
        )

    if hasattr(company, "is_active") and not company.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company account is inactive.",
        )

    return company