from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any


# ==========================================================
# CSRF Configuration
# ==========================================================

@dataclass(slots=True)
class CSRFSettings:

    secret_key: str = secrets.token_urlsafe(64)

    token_length: int = 64

    expiry_minutes: int = 60

    cookie_name: str = "__Host-csrf"

    header_name: str = "X-CSRF-Token"

    same_site: str = "Strict"

    secure_cookie: bool = True

    http_only_cookie: bool = False

    rotate_after_validation: bool = True

    require_origin_validation: bool = True

    require_referer_validation: bool = False


DEFAULT_SETTINGS = CSRFSettings()


# ==========================================================
# CSRF Service
# ==========================================================

class CSRFService:

    def __init__(
        self,
        settings: CSRFSettings | None = None,
    ):

        self.settings = settings or DEFAULT_SETTINGS

        self._session_tokens: dict[str, dict[str, Any]] = {}


# ==========================================================
# Current Time
# ==========================================================

    @staticmethod
    def now() -> datetime:

        return datetime.now(UTC)


# ==========================================================
# Generate Random Secret
# ==========================================================

    def generate_secret(
        self,
    ) -> str:

        return secrets.token_urlsafe(

            self.settings.token_length

        )


# ==========================================================
# Sign Token
# ==========================================================

    def sign_token(
        self,
        value: str,
    ) -> str:

        signature = hmac.new(

            self.settings.secret_key.encode(),

            value.encode(),

            hashlib.sha256,

        ).hexdigest()

        return f"{value}.{signature}"


# ==========================================================
# Verify Signature
# ==========================================================

    def verify_signature(
        self,
        token: str,
    ) -> bool:

        try:

            value, signature = token.rsplit(".", 1)

        except ValueError:

            return False

        expected = hmac.new(

            self.settings.secret_key.encode(),

            value.encode(),

            hashlib.sha256,

        ).hexdigest()

        return hmac.compare_digest(

            signature,

            expected,

        )


# ==========================================================
# Generate CSRF Token
# ==========================================================

    def generate_token(
        self,
        session_id: str,
    ) -> str:

        secret = self.generate_secret()

        expires = (

            self.now()

            +

            timedelta(

                minutes=self.settings.expiry_minutes

            )

        )

        self._session_tokens[session_id] = {

            "secret": secret,

            "expires": expires,

        }

        return self.sign_token(secret)


# ==========================================================
# Session Secret
# ==========================================================

    def session_secret(
        self,
        session_id: str,
    ) -> str | None:

        record = self._session_tokens.get(

            session_id

        )

        if record is None:

            return None

        return record["secret"]


# ==========================================================
# Token Expiry
# ==========================================================

    def token_expired(
        self,
        session_id: str,
    ) -> bool:

        record = self._session_tokens.get(

            session_id

        )

        if record is None:

            return True

        return record["expires"] < self.now()
        
        # ==========================================================
# Validate Token
# ==========================================================

    def validate_token(
        self,
        session_id: str,
        token: str,
    ) -> bool:

        if self.token_expired(session_id):

            return False

        if not self.verify_signature(token):

            return False

        value = token.rsplit(".", 1)[0]

        stored = self.session_secret(session_id)

        if stored is None:

            return False

        valid = hmac.compare_digest(
            value,
            stored,
        )

        if (
            valid
            and
            self.settings.rotate_after_validation
        ):

            self.generate_token(session_id)

        return valid


# ==========================================================
# Double Submit Cookie
# ==========================================================

    def validate_cookie(
        self,
        cookie_token: str,
        header_token: str,
    ) -> bool:

        return hmac.compare_digest(

            cookie_token,

            header_token,

        )


# ==========================================================
# Cookie Attributes
# ==========================================================

    def cookie_options(
        self,
    ) -> dict[str, Any]:

        return {

            "key":

                self.settings.cookie_name,

            "secure":

                self.settings.secure_cookie,

            "httponly":

                self.settings.http_only_cookie,

            "samesite":

                self.settings.same_site,

        }


# ==========================================================
# Rotate Token
# ==========================================================

    def rotate_token(
        self,
        session_id: str,
    ) -> str:

        return self.generate_token(
            session_id
        )


# ==========================================================
# Revoke Token
# ==========================================================

    def revoke_token(
        self,
        session_id: str,
    ) -> bool:

        if session_id not in self._session_tokens:

            return False

        del self._session_tokens[
            session_id
        ]

        return True


# ==========================================================
# Invalidate Session
# ==========================================================

    def invalidate_session(
        self,
        session_id: str,
    ) -> None:

        self.revoke_token(
            session_id
        )


# ==========================================================
# Origin Validation
# ==========================================================

    def validate_origin(
        self,
        request_origin: str | None,
        allowed_origins: list[str],
    ) -> bool:

        if not self.settings.require_origin_validation:

            return True

        if not request_origin:

            return False

        return request_origin in allowed_origins


# ==========================================================
# Referer Validation
# ==========================================================

    def validate_referer(
        self,
        referer: str | None,
        allowed_origins: list[str],
    ) -> bool:

        if not self.settings.require_referer_validation:

            return True

        if not referer:

            return False

        return any(

            referer.startswith(origin)

            for origin in allowed_origins

        )


# ==========================================================
# SameSite Validation
# ==========================================================

    def validate_same_site(
        self,
        cookie_same_site: str,
    ) -> bool:

        return (

            cookie_same_site.lower()

            ==

            self.settings.same_site.lower()

        )


# ==========================================================
# Replay Protection
# ==========================================================

    def replay_protection(
        self,
        session_id: str,
        token: str,
    ) -> bool:

        return self.validate_token(

            session_id,

            token,

        )
        
        # ==========================================================
# Active Sessions
# ==========================================================

    def active_sessions(
        self,
    ) -> list[str]:

        return list(self._session_tokens.keys())


# ==========================================================
# Session Information
# ==========================================================

    def session_information(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:

        record = self._session_tokens.get(session_id)

        if record is None:
            return None

        return {

            "session_id": session_id,

            "expires": record["expires"],

            "expired": self.token_expired(session_id),

        }


# ==========================================================
# Cleanup Expired Tokens
# ==========================================================

    def cleanup_expired(
        self,
    ) -> int:

        expired = []

        for session_id, record in self._session_tokens.items():

            if record["expires"] < self.now():

                expired.append(session_id)

        for session_id in expired:

            del self._session_tokens[session_id]

        return len(expired)


# ==========================================================
# Token Statistics
# ==========================================================

    def statistics(
        self,
    ) -> dict[str, Any]:

        total = len(self._session_tokens)

        expired = sum(

            1

            for session in self._session_tokens

            if self.token_expired(session)

        )

        active = total - expired

        return {

            "total_sessions": total,

            "active_tokens": active,

            "expired_tokens": expired,

        }


# ==========================================================
# Security Report
# ==========================================================

    def security_report(
        self,
    ) -> dict[str, Any]:

        stats = self.statistics()

        return {

            "csrf_enabled": True,

            "token_rotation":

                self.settings.rotate_after_validation,

            "origin_validation":

                self.settings.require_origin_validation,

            "referer_validation":

                self.settings.require_referer_validation,

            "same_site":

                self.settings.same_site,

            "secure_cookie":

                self.settings.secure_cookie,

            "statistics": stats,

        }


# ==========================================================
# Export Token
# ==========================================================

    def export_token(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:

        record = self._session_tokens.get(session_id)

        if record is None:

            return None

        return {

            "session_id": session_id,

            "expires": record["expires"],

            "has_secret": True,

        }


# ==========================================================
# Service Health
# ==========================================================

    def health(
        self,
    ) -> dict[str, Any]:

        stats = self.statistics()

        return {

            "service": "CSRFService",

            "status": "healthy",

            "active_sessions":

                stats["active_tokens"],

            "expired_tokens":

                stats["expired_tokens"],

        }


# ==========================================================
# Diagnostics
# ==========================================================

    def diagnostics(
        self,
    ) -> dict[str, Any]:

        return {

            "health": self.health(),

            "statistics": self.statistics(),

            "security": self.security_report(),

        }


# ==========================================================
# Maintenance
# ==========================================================

    def maintenance(
        self,
    ) -> dict[str, int]:

        removed = self.cleanup_expired()

        return {

            "expired_removed": removed,

        }


# ==========================================================
# Audit Event
# ==========================================================

    def audit_event(
        self,
        event: str,
        session_id: str,
    ) -> dict[str, Any]:

        return {

            "timestamp": self.now(),

            "event": event,

            "session_id": session_id,

        }
        
        # ==========================================================
# Trusted Origins
# ==========================================================

    def set_allowed_origins(
        self,
        origins: list[str],
    ) -> None:

        self._allowed_origins = {

            origin.rstrip("/")

            for origin in origins

        }


    def allowed_origins(
        self,
    ) -> list[str]:

        return sorted(

            getattr(

                self,

                "_allowed_origins",

                set(),

            )

        )


    def add_allowed_origin(
        self,
        origin: str,
    ) -> None:

        if not hasattr(

            self,

            "_allowed_origins",

        ):

            self._allowed_origins = set()

        self._allowed_origins.add(

            origin.rstrip("/")

        )


    def remove_allowed_origin(
        self,
        origin: str,
    ) -> bool:

        if not hasattr(

            self,

            "_allowed_origins",

        ):

            return False

        return (

            self._allowed_origins.discard(

                origin.rstrip("/")

            )

            is None

        )


# ==========================================================
# Tenant Origins
# ==========================================================

    def set_tenant_origins(
        self,
        tenant_id: str,
        origins: list[str],
    ) -> None:

        if not hasattr(

            self,

            "_tenant_origins",

        ):

            self._tenant_origins = {}

        self._tenant_origins[tenant_id] = {

            origin.rstrip("/")

            for origin in origins

        }


    def validate_tenant_origin(
        self,
        tenant_id: str,
        origin: str,
    ) -> bool:

        tenants = getattr(

            self,

            "_tenant_origins",

            {},

        )

        allowed = tenants.get(

            tenant_id,

            set(),

        )

        return origin.rstrip("/") in allowed


# ==========================================================
# Cookie Builder
# ==========================================================

    def build_cookie(
        self,
        token: str,
    ) -> dict[str, Any]:

        return {

            "key":

                self.settings.cookie_name,

            "value":

                token,

            "secure":

                self.settings.secure_cookie,

            "httponly":

                self.settings.http_only_cookie,

            "samesite":

                self.settings.same_site,

            "path": "/",

        }


# ==========================================================
# Request Validation
# ==========================================================

    def validate_request(
        self,
        *,
        session_id: str,
        csrf_token: str,
        cookie_token: str,
        origin: str | None,
        referer: str | None,
    ) -> bool:

        if not self.validate_token(

            session_id,

            csrf_token,

        ):

            return False

        if not self.validate_cookie(

            cookie_token,

            csrf_token,

        ):

            return False

        allowed = self.allowed_origins()

        if allowed:

            if not self.validate_origin(

                origin,

                allowed,

            ):

                return False

            if not self.validate_referer(

                referer,

                allowed,

            ):

                return False

        return True


# ==========================================================
# Middleware Context
# ==========================================================

    def middleware_context(
        self,
        session_id: str,
    ) -> dict[str, Any]:

        token = self.generate_token(

            session_id

        )

        return {

            "csrf_token": token,

            "cookie":

                self.build_cookie(

                    token,

                ),

            "header":

                self.settings.header_name,

        }


# ==========================================================
# Security Headers
# ==========================================================

    def security_headers(
        self,
    ) -> dict[str, str]:

        return {

            "X-CSRF-Header":

                self.settings.header_name,

            "X-CSRF-Cookie":

                self.settings.cookie_name,

            "X-Frame-Options":

                "DENY",

            "X-Content-Type-Options":

                "nosniff",

            "Referrer-Policy":

                "strict-origin-when-cross-origin",

        }


# ==========================================================
# Configuration Validation
# ==========================================================

    def validate_configuration(
        self,
    ) -> bool:

        if not self.settings.secret_key:

            raise ValueError(

                "secret_key is required."

            )

        if self.settings.expiry_minutes <= 0:

            raise ValueError(

                "expiry_minutes must be greater than zero."

            )

        if self.settings.token_length < 32:

            raise ValueError(

                "token_length must be at least 32."

            )

        if self.settings.same_site not in (

            "Strict",

            "Lax",

            "None",

        ):

            raise ValueError(

                "Invalid SameSite policy."

            )

        return True
        
        # ==========================================================
# Singleton
# ==========================================================

_csrf_service: CSRFService | None = None


def initialize_csrf_service(
    settings: CSRFSettings | None = None,
) -> CSRFService:

    global _csrf_service

    _csrf_service = CSRFService(
        settings=settings,
    )

    _csrf_service.validate_configuration()

    return _csrf_service


# ==========================================================
# Get Service
# ==========================================================

def get_csrf_service() -> CSRFService:

    if _csrf_service is None:

        raise RuntimeError(
            "CSRFService has not been initialized."
        )

    return _csrf_service


# ==========================================================
# Convenience Functions
# ==========================================================

def generate_csrf_token(
    session_id: str,
) -> str:

    return get_csrf_service().generate_token(
        session_id
    )


def validate_csrf_token(
    session_id: str,
    token: str,
) -> bool:

    return get_csrf_service().validate_token(
        session_id,
        token,
    )


def revoke_csrf_token(
    session_id: str,
) -> bool:

    return get_csrf_service().revoke_token(
        session_id
    )


def csrf_cookie(
    token: str,
) -> dict[str, Any]:

    return get_csrf_service().build_cookie(
        token
    )


def csrf_security_headers() -> dict[str, str]:

    return get_csrf_service().security_headers()


def csrf_health():

    return get_csrf_service().health()


def csrf_diagnostics():

    return get_csrf_service().diagnostics()


def csrf_maintenance():

    return get_csrf_service().maintenance()


# ==========================================================
# Public Exports
# ==========================================================

__all__ = [

    "CSRFSettings",

    "CSRFService",

    "initialize_csrf_service",

    "get_csrf_service",

    "generate_csrf_token",

    "validate_csrf_token",

    "revoke_csrf_token",

    "csrf_cookie",

    "csrf_security_headers",

    "csrf_health",

    "csrf_diagnostics",

    "csrf_maintenance",

]