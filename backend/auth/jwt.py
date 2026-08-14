from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Literal
from uuid import uuid4

import jwt

from jwt import ExpiredSignatureError
from jwt import InvalidTokenError


# ==========================================================
# JWT Configuration
# ==========================================================

Algorithm = Literal["HS256", "RS256"]


@dataclass(slots=True)
class JWTSettings:

    secret_key: str

    issuer: str = "BoostRankers"

    audience: str = "BoostRankers-AI-SEO-OS"

    algorithm: Algorithm = "HS256"

    access_token_minutes: int = 30

    refresh_token_days: int = 30

    leeway_seconds: int = 30


# ==========================================================
# Token Types
# ==========================================================

ACCESS_TOKEN = "access"

REFRESH_TOKEN = "refresh"


# ==========================================================
# JWT Service
# ==========================================================

class JWTService:

    def __init__(
        self,
        settings: JWTSettings,
    ):

        self.settings = settings


# ==========================================================
# Current Time
# ==========================================================

    @staticmethod
    def now() -> datetime:

        return datetime.now(UTC)


# ==========================================================
# JWT ID
# ==========================================================

    @staticmethod
    def generate_jti() -> str:

        return uuid4().hex


# ==========================================================
# Base Claims
# ==========================================================

    def base_claims(
        self,
        subject: str,
        token_type: str,
        expires: timedelta,
    ) -> dict[str, Any]:

        issued = self.now()

        return {

            "sub": subject,

            "type": token_type,

            "iss": self.settings.issuer,

            "aud": self.settings.audience,

            "iat": int(
                issued.timestamp()
            ),

            "nbf": int(
                issued.timestamp()
            ),

            "exp": int(
                (
                    issued + expires
                ).timestamp()
            ),

            "jti": self.generate_jti(),

        }


# ==========================================================
# Access Claims
# ==========================================================

    def access_claims(
        self,
        user_id: int,
        email: str,
        company_id: int | None,
        roles: list[str],
        permissions: list[str],
        token_version: int = 1,
    ) -> dict[str, Any]:

        claims = self.base_claims(

            subject=str(user_id),

            token_type=ACCESS_TOKEN,

            expires=timedelta(
                minutes=self.settings.access_token_minutes
            ),

        )

        claims.update(

            {

                "uid": user_id,

                "email": email,

                "company_id": company_id,

                "roles": roles,

                "permissions": permissions,

                "version": token_version,

            }

        )

        return claims


# ==========================================================
# Refresh Claims
# ==========================================================

    def refresh_claims(
        self,
        user_id: int,
        token_version: int = 1,
    ) -> dict[str, Any]:

        claims = self.base_claims(

            subject=str(user_id),

            token_type=REFRESH_TOKEN,

            expires=timedelta(
                days=self.settings.refresh_token_days
            ),

        )

        claims["version"] = token_version

        return claims
        
        # ==========================================================
# Encode JWT
# ==========================================================

    def encode(
        self,
        claims: dict[str, Any],
    ) -> str:

        return jwt.encode(

            payload=claims,

            key=self.settings.secret_key,

            algorithm=self.settings.algorithm,

        )


# ==========================================================
# Decode JWT
# ==========================================================

    def decode(
        self,
        token: str,
        verify_exp: bool = True,
    ) -> dict[str, Any]:

        options = {

            "verify_exp": verify_exp,

            "verify_signature": True,

            "verify_aud": True,

            "verify_iss": True,

        }

        return jwt.decode(

            jwt=token,

            key=self.settings.secret_key,

            algorithms=[

                self.settings.algorithm

            ],

            audience=self.settings.audience,

            issuer=self.settings.issuer,

            options=options,

            leeway=self.settings.leeway_seconds,

        )


# ==========================================================
# Safe Decode
# ==========================================================

    def try_decode(
        self,
        token: str,
    ) -> tuple[bool, dict[str, Any] | None]:

        try:

            payload = self.decode(token)

            return True, payload

        except (

            ExpiredSignatureError,

            InvalidTokenError,

        ):

            return False, None


# ==========================================================
# Access Token
# ==========================================================

    def create_access_token(
        self,
        *,
        user_id: int,
        email: str,
        company_id: int | None,
        roles: list[str],
        permissions: list[str],
        token_version: int = 1,
    ) -> str:

        claims = self.access_claims(

            user_id=user_id,

            email=email,

            company_id=company_id,

            roles=roles,

            permissions=permissions,

            token_version=token_version,

        )

        return self.encode(claims)


# ==========================================================
# Refresh Token
# ==========================================================

    def create_refresh_token(
        self,
        *,
        user_id: int,
        token_version: int = 1,
    ) -> str:

        claims = self.refresh_claims(

            user_id=user_id,

            token_version=token_version,

        )

        return self.encode(claims)


# ==========================================================
# Validate Token Type
# ==========================================================

    @staticmethod
    def validate_token_type(
        payload: dict[str, Any],
        expected: str,
    ) -> bool:

        return (

            payload.get("type")

            == expected

        )


# ==========================================================
# Require Access Token
# ==========================================================

    def require_access_token(
        self,
        token: str,
    ) -> dict[str, Any]:

        payload = self.decode(token)

        if not self.validate_token_type(

            payload,

            ACCESS_TOKEN,

        ):

            raise InvalidTokenError(

                "Expected access token."

            )

        return payload


# ==========================================================
# Require Refresh Token
# ==========================================================

    def require_refresh_token(
        self,
        token: str,
    ) -> dict[str, Any]:

        payload = self.decode(token)

        if not self.validate_token_type(

            payload,

            REFRESH_TOKEN,

        ):

            raise InvalidTokenError(

                "Expected refresh token."

            )

        return payload
        
        # ==========================================================
# JWT ID
# ==========================================================

    @staticmethod
    def jti(
        payload: dict[str, Any],
    ) -> str | None:

        return payload.get("jti")


# ==========================================================
# User ID
# ==========================================================

    @staticmethod
    def user_id(
        payload: dict[str, Any],
    ) -> int | None:

        value = payload.get("uid")

        if value is None:

            return None

        return int(value)


# ==========================================================
# Subject
# ==========================================================

    @staticmethod
    def subject(
        payload: dict[str, Any],
    ) -> str | None:

        return payload.get("sub")


# ==========================================================
# Company ID
# ==========================================================

    @staticmethod
    def company_id(
        payload: dict[str, Any],
    ) -> int | None:

        company = payload.get("company_id")

        if company is None:

            return None

        return int(company)


# ==========================================================
# Roles
# ==========================================================

    @staticmethod
    def roles(
        payload: dict[str, Any],
    ) -> list[str]:

        return list(

            payload.get("roles", [])

        )


# ==========================================================
# Permissions
# ==========================================================

    @staticmethod
    def permissions(
        payload: dict[str, Any],
    ) -> list[str]:

        return list(

            payload.get("permissions", [])

        )


# ==========================================================
# Token Version
# ==========================================================

    @staticmethod
    def token_version(
        payload: dict[str, Any],
    ) -> int:

        return int(

            payload.get("version", 1)

        )


# ==========================================================
# Expiration
# ==========================================================

    @staticmethod
    def expires_at(
        payload: dict[str, Any],
    ) -> datetime:

        return datetime.fromtimestamp(

            payload["exp"],

            tz=UTC,

        )


# ==========================================================
# Issued At
# ==========================================================

    @staticmethod
    def issued_at(
        payload: dict[str, Any],
    ) -> datetime:

        return datetime.fromtimestamp(

            payload["iat"],

            tz=UTC,

        )


# ==========================================================
# Remaining Lifetime
# ==========================================================

    def remaining_lifetime(
        self,
        payload: dict[str, Any],
    ) -> timedelta:

        expires = self.expires_at(
            payload
        )

        remaining = expires - self.now()

        if remaining.total_seconds() < 0:

            return timedelta(0)

        return remaining


# ==========================================================
# Token Expired
# ==========================================================

    def is_expired(
        self,
        payload: dict[str, Any],
    ) -> bool:

        return self.remaining_lifetime(

            payload

        ) == timedelta(0)


# ==========================================================
# Refresh Rotation
# ==========================================================

    def rotate_refresh_token(
        self,
        payload: dict[str, Any],
    ) -> tuple[str, str]:

        """
        Creates a completely new
        access token and refresh token.
        """

        access = self.create_access_token(

            user_id=self.user_id(payload),

            email=payload.get("email", ""),

            company_id=self.company_id(payload),

            roles=self.roles(payload),

            permissions=self.permissions(payload),

            token_version=self.token_version(payload),

        )

        refresh = self.create_refresh_token(

            user_id=self.user_id(payload),

            token_version=self.token_version(payload),

        )

        return access, refresh


# ==========================================================
# Revocation Hook
# ==========================================================

    def is_revoked(
        self,
        jti: str,
    ) -> bool:

        """
        Placeholder.

        Future implementation:

            Redis

            Database

            Distributed cache

        """

        return False


# ==========================================================
# Validate Revocation
# ==========================================================

    def ensure_not_revoked(
        self,
        payload: dict[str, Any],
    ):

        token_id = self.jti(payload)

        if token_id and self.is_revoked(token_id):

            raise InvalidTokenError(

                "Token has been revoked."

            )
            
            # ==========================================================
# Session ID
# ==========================================================

    @staticmethod
    def session_id(
        payload: dict[str, Any],
    ) -> str | None:

        return payload.get("sid")


# ==========================================================
# Device ID
# ==========================================================

    @staticmethod
    def device_id(
        payload: dict[str, Any],
    ) -> str | None:

        return payload.get("device_id")


# ==========================================================
# Token Fingerprint
# ==========================================================

    @staticmethod
    def fingerprint(
        payload: dict[str, Any],
    ) -> str | None:

        return payload.get("fingerprint")


# ==========================================================
# Add Custom Claims
# ==========================================================

    @staticmethod
    def with_claims(
        claims: dict[str, Any],
        **extra: Any,
    ) -> dict[str, Any]:

        merged = claims.copy()

        merged.update(extra)

        return merged


# ==========================================================
# Bind Session
# ==========================================================

    def bind_session(
        self,
        claims: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:

        return self.with_claims(

            claims,

            sid=session_id,

        )


# ==========================================================
# Bind Device
# ==========================================================

    def bind_device(
        self,
        claims: dict[str, Any],
        device_id: str,
        fingerprint: str,
    ) -> dict[str, Any]:

        return self.with_claims(

            claims,

            device_id=device_id,

            fingerprint=fingerprint,

        )


# ==========================================================
# Validate Device
# ==========================================================

    def validate_device(
        self,
        payload: dict[str, Any],
        device_id: str,
        fingerprint: str,
    ) -> bool:

        return (

            payload.get("device_id") == device_id

            and

            payload.get("fingerprint") == fingerprint

        )


# ==========================================================
# Tenant Validation
# ==========================================================

    @staticmethod
    def validate_company(
        payload: dict[str, Any],
        company_id: int | None,
    ) -> bool:

        return (

            payload.get("company_id")

            == company_id

        )


# ==========================================================
# Has Role
# ==========================================================

    @staticmethod
    def has_role(
        payload: dict[str, Any],
        role: str,
    ) -> bool:

        return role in payload.get(

            "roles",

            [],

        )


# ==========================================================
# Has Permission
# ==========================================================

    @staticmethod
    def has_permission(
        payload: dict[str, Any],
        permission: str,
    ) -> bool:

        return permission in payload.get(

            "permissions",

            [],

        )


# ==========================================================
# Has Any Permission
# ==========================================================

    @staticmethod
    def has_any_permission(
        payload: dict[str, Any],
        permissions: list[str],
    ) -> bool:

        token_permissions = set(

            payload.get(

                "permissions",

                [],

            )

        )

        return any(

            permission in token_permissions

            for permission in permissions

        )


# ==========================================================
# Has All Permissions
# ==========================================================

    @staticmethod
    def has_all_permissions(
        payload: dict[str, Any],
        permissions: list[str],
    ) -> bool:

        token_permissions = set(

            payload.get(

                "permissions",

                [],

            )

        )

        return all(

            permission in token_permissions

            for permission in permissions

        )


# ==========================================================
# Validate Token
# ==========================================================

    def validate(
        self,
        token: str,
    ) -> dict[str, Any]:

        payload = self.decode(token)

        self.ensure_not_revoked(payload)

        return payload


# ==========================================================
# Token Information
# ==========================================================

    def token_information(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        return {

            "user_id": self.user_id(payload),

            "company_id": self.company_id(payload),

            "roles": self.roles(payload),

            "permissions": self.permissions(payload),

            "issued_at": self.issued_at(payload),

            "expires_at": self.expires_at(payload),

            "remaining": str(

                self.remaining_lifetime(payload)

            ),

            "session_id": self.session_id(payload),

            "device_id": self.device_id(payload),

            "token_type": payload.get("type"),

            "version": self.token_version(payload),

        }
        
        # ==========================================================
# Token Pair
# ==========================================================

    def create_token_pair(
        self,
        *,
        user_id: int,
        email: str,
        company_id: int | None,
        roles: list[str],
        permissions: list[str],
        token_version: int = 1,
        session_id: str | None = None,
        device_id: str | None = None,
        fingerprint: str | None = None,
    ) -> dict[str, Any]:

        access_claims = self.access_claims(
            user_id=user_id,
            email=email,
            company_id=company_id,
            roles=roles,
            permissions=permissions,
            token_version=token_version,
        )

        if session_id:

            access_claims = self.bind_session(
                access_claims,
                session_id,
            )

        if device_id and fingerprint:

            access_claims = self.bind_device(
                access_claims,
                device_id,
                fingerprint,
            )

        access_token = self.encode(
            access_claims
        )

        refresh_token = self.create_refresh_token(
            user_id=user_id,
            token_version=token_version,
        )

        return {

            "access_token": access_token,

            "refresh_token": refresh_token,

            "token_type": "Bearer",

            "expires_in":
                self.settings.access_token_minutes * 60,

            "refresh_expires_in":
                self.settings.refresh_token_days * 86400,

        }


# ==========================================================
# Configuration Validation
# ==========================================================

    def validate_configuration(self):

        if not self.settings.secret_key:

            raise RuntimeError(
                "JWT secret key not configured."
            )

        if len(self.settings.secret_key) < 32:

            raise RuntimeError(
                "JWT secret key must be at least 32 characters."
            )

        return True


# ==========================================================
# Service Health
# ==========================================================

    def health(self) -> dict:

        return {

            "service": "JWTService",

            "status": "healthy",

            "algorithm":
                self.settings.algorithm,

            "issuer":
                self.settings.issuer,

            "audience":
                self.settings.audience,

            "access_minutes":
                self.settings.access_token_minutes,

            "refresh_days":
                self.settings.refresh_token_days,

            "clock_leeway":
                self.settings.leeway_seconds,

        }


# ==========================================================
# Singleton
# ==========================================================

jwt_service: JWTService | None = None


def initialize_jwt(
    settings: JWTSettings,
) -> JWTService:

    global jwt_service

    jwt_service = JWTService(settings)

    jwt_service.validate_configuration()

    return jwt_service


# ==========================================================
# Convenience Functions
# ==========================================================

def get_jwt_service() -> JWTService:

    if jwt_service is None:

        raise RuntimeError(
            "JWTService has not been initialized."
        )

    return jwt_service


def create_access_token(**kwargs):

    return get_jwt_service().create_access_token(
        **kwargs
    )


def create_refresh_token(**kwargs):

    return get_jwt_service().create_refresh_token(
        **kwargs
    )


def create_token_pair(**kwargs):

    return get_jwt_service().create_token_pair(
        **kwargs
    )


def decode_token(token: str):

    return get_jwt_service().decode(token)


def validate_token(token: str):

    return get_jwt_service().validate(token)


# ==========================================================
# Public Exports
# ==========================================================

__all__ = [

    "JWTSettings",

    "JWTService",

    "ACCESS_TOKEN",

    "REFRESH_TOKEN",

    "initialize_jwt",

    "get_jwt_service",

    "create_access_token",

    "create_refresh_token",

    "create_token_pair",

    "decode_token",

    "validate_token",

]