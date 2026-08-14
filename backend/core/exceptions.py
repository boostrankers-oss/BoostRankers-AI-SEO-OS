"""
JWT Utilities
Boost Rankers AI SEO OS

Features
--------
- Access Token
- Refresh Token
- JWT Verification
- Token Rotation
- Token Revocation Support
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from config import settings


# ==========================================================
# JWT Configuration
# ==========================================================

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = getattr(
    settings,
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    15,
)

REFRESH_TOKEN_EXPIRE_DAYS = getattr(
    settings,
    "REFRESH_TOKEN_EXPIRE_DAYS",
    30,
)


# ==========================================================
# Generic Token Creator
# ==========================================================

def _create_token(
    payload: dict[str, Any],
    expires_delta: timedelta,
) -> str:
    """
    Internal helper for creating JWTs.
    """

    now = datetime.now(UTC)

    data = payload.copy()

    data.update(
        {
            "iat": now,
            "nbf": now,
            "exp": now + expires_delta,
        }
    )

    return jwt.encode(
        data,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


# ==========================================================
# Access Token
# ==========================================================

def create_access_token(
    *,
    user_id: str,
    email: str,
    company_id: str | None,
    role: str,
    permissions: list[str] | None = None,
) -> str:

    payload = {
        "type": "access",
        "sub": user_id,
        "email": email,
        "company_id": company_id,
        "role": role,
        "permissions": permissions or [],
    }

    return _create_token(
        payload,
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


# ==========================================================
# Refresh Token
# ==========================================================

def create_refresh_token(
    *,
    user_id: str,
    session_id: str,
) -> str:

    payload = {
        "type": "refresh",
        "sub": user_id,
        "sid": session_id,
    }

    return _create_token(
        payload,
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )


# ==========================================================
# Decode
# ==========================================================

def decode_token(
    token: str,
) -> dict[str, Any]:

    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[ALGORITHM],
    )


# ==========================================================
# Verify
# ==========================================================

def verify_token(
    token: str,
    token_type: str | None = None,
) -> dict[str, Any]:
    """
    Decode and validate a JWT.

    Raises:
        JWTError
    """

    payload = decode_token(token)

    if token_type:

        if payload.get("type") != token_type:
            raise JWTError("Invalid token type.")

    return payload


# ==========================================================
# Access Helpers
# ==========================================================

def get_user_id(token: str) -> str:
    return verify_token(token)["sub"]


def get_company_id(token: str) -> str | None:
    return verify_token(token).get("company_id")


def get_role(token: str) -> str:
    return verify_token(token)["role"]


def get_permissions(token: str) -> list[str]:
    return verify_token(token).get("permissions", [])


# ==========================================================
# Refresh Helpers
# ==========================================================

def get_session_id(token: str) -> str:
    payload = verify_token(
        token,
        token_type="refresh",
    )

    return payload["sid"]


# ==========================================================
# Expiration
# ==========================================================

def token_expiration(
    token: str,
) -> datetime:

    payload = verify_token(token)

    return datetime.fromtimestamp(
        payload["exp"],
        tz=UTC,
    )


def is_expired(
    token: str,
) -> bool:

    return token_expiration(token) <= datetime.now(UTC)


# ==========================================================
# Rotation
# ==========================================================

def rotate_refresh_token(
    *,
    user_id: str,
    session_id: str,
) -> str:
    """
    Creates a new refresh token.
    The database service will revoke the old one.
    """

    return create_refresh_token(
        user_id=user_id,
        session_id=session_id,
    )


# ==========================================================
# Authorization Helpers
# ==========================================================

def has_permission(
    payload: dict[str, Any],
    permission: str,
) -> bool:

    permissions = payload.get(
        "permissions",
        [],
    )

    return permission in permissions


def has_role(
    payload: dict[str, Any],
    role: str,
) -> bool:

    return payload.get("role") == role


# ==========================================================
# Optional Blacklist Hook
# ==========================================================

def is_blacklisted(
    token: str,
) -> bool:
    """
    Placeholder.

    Can later integrate:
        Redis
        PostgreSQL
        Cache
    """

    return False