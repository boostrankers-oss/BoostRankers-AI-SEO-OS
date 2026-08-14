from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from models.api_key import APIKey
from models.user import User


# ==========================================================
# API Key Configuration
# ==========================================================

@dataclass(slots=True)
class APIKeySettings:

    prefix: str = "br"

    key_length: int = 48

    default_expiry_days: int = 365

    max_keys_per_user: int = 25

    hash_algorithm: str = "sha256"


DEFAULT_SETTINGS = APIKeySettings()


# ==========================================================
# API Key Service
# ==========================================================

class APIKeyService:

    def __init__(
        self,
        db: Session,
        settings: APIKeySettings | None = None,
    ):

        self.db = db

        self.settings = settings or DEFAULT_SETTINGS


# ==========================================================
# Current Time
# ==========================================================

    @staticmethod
    def now() -> datetime:

        return datetime.now(UTC)


# ==========================================================
# Generate Secret
# ==========================================================

    def generate_secret(self) -> str:

        return secrets.token_urlsafe(

            self.settings.key_length

        )


# ==========================================================
# Generate Prefix ID
# ==========================================================

    @staticmethod
    def identifier() -> str:

        return secrets.token_hex(4)


# ==========================================================
# Build API Key
# ==========================================================

    def generate_key(self) -> tuple[str, str]:

        identifier = self.identifier()

        secret = self.generate_secret()

        key = (

            f"{self.settings.prefix}_"

            f"{identifier}_"

            f"{secret}"

        )

        return key, identifier


# ==========================================================
# Hash API Key
# ==========================================================

    def hash_key(
        self,
        key: str,
    ) -> str:

        return hashlib.new(

            self.settings.hash_algorithm,

            key.encode(),

        ).hexdigest()


# ==========================================================
# Verify API Key
# ==========================================================

    def verify_key(
        self,
        key: str,
        hashed: str,
    ) -> bool:

        calculated = self.hash_key(key)

        return hmac.compare_digest(

            calculated,

            hashed,

        )


# ==========================================================
# Expiry Date
# ==========================================================

    def expires_at(
        self,
        days: int | None = None,
    ) -> datetime:

        return self.now() + timedelta(

            days=days

            or

            self.settings.default_expiry_days

        )


# ==========================================================
# User Key Count
# ==========================================================

    def key_count(
        self,
        user_id: int,
    ) -> int:

        return (

            self.db.query(APIKey)

            .filter(

                APIKey.user_id == user_id,

                APIKey.revoked.is_(False),

            )

            .count()

        )
        
        # ==========================================================
# Lookup By Prefix
# ==========================================================

    def by_prefix(
        self,
        prefix: str,
    ) -> APIKey | None:

        return (

            self.db.query(APIKey)

            .filter(

                APIKey.key_prefix == prefix

            )

            .first()

        )


# ==========================================================
# Lookup By ID
# ==========================================================

    def by_id(
        self,
        key_id: int,
    ) -> APIKey | None:

        return (

            self.db.query(APIKey)

            .filter(

                APIKey.id == key_id

            )

            .first()

        )


# ==========================================================
# Is Expired
# ==========================================================

    def is_expired(
        self,
        record: APIKey,
    ) -> bool:

        if record.expires_at is None:

            return False

        return record.expires_at <= self.now()


# ==========================================================
# Is Revoked
# ==========================================================

    @staticmethod
    def is_revoked(
        record: APIKey,
    ) -> bool:

        return bool(record.revoked)


# ==========================================================
# Authenticate API Key
# ==========================================================

    def authenticate(
        self,
        raw_key: str,
    ) -> APIKey:

        try:

            _, identifier, _ = raw_key.split(
                "_",
                2,
            )

        except ValueError:

            raise ValueError(
                "Invalid API key format."
            )

        record = self.by_prefix(identifier)

        if record is None:

            raise ValueError(
                "API key not found."
            )

        if self.is_revoked(record):

            raise ValueError(
                "API key has been revoked."
            )

        if self.is_expired(record):

            raise ValueError(
                "API key has expired."
            )

        if not self.verify_key(

            raw_key,

            record.key_hash,

        ):

            raise ValueError(
                "Invalid API key."
            )

        self.mark_used(record)

        return record


# ==========================================================
# Mark Last Used
# ==========================================================

    def mark_used(
        self,
        record: APIKey,
    ) -> None:

        record.last_used_at = self.now()

        record.usage_count += 1

        self.db.commit()


# ==========================================================
# Revoke API Key
# ==========================================================

    def revoke(
        self,
        record: APIKey,
        reason: str | None = None,
    ) -> None:

        record.revoked = True

        record.revoked_at = self.now()

        record.revocation_reason = reason

        self.db.commit()


# ==========================================================
# Rotate API Key
# ==========================================================

    def rotate(
        self,
        record: APIKey,
    ) -> tuple[str, APIKey]:

        raw_key, identifier = self.generate_key()

        record.key_hash = self.hash_key(raw_key)

        record.key_prefix = identifier

        record.last_rotated_at = self.now()

        record.revoked = False

        self.db.commit()

        self.db.refresh(record)

        return raw_key, record


# ==========================================================
# Validate Scope
# ==========================================================

    @staticmethod
    def has_scope(
        record: APIKey,
        scope: str,
    ) -> bool:

        return scope in (

            record.scopes

            or

            []

        )


# ==========================================================
# Validate Multiple Scopes
# ==========================================================

    @staticmethod
    def has_all_scopes(
        record: APIKey,
        scopes: list[str],
    ) -> bool:

        current = set(

            record.scopes

            or

            []

        )

        return all(

            scope in current

            for scope in scopes

        )


# ==========================================================
# Validate Any Scope
# ==========================================================

    @staticmethod
    def has_any_scope(
        record: APIKey,
        scopes: list[str],
    ) -> bool:

        current = set(

            record.scopes

            or

            []

        )

        return any(

            scope in current

            for scope in scopes

        )
        
        # ==========================================================
# Validate IP Address
# ==========================================================

    @staticmethod
    def ip_allowed(
        record: APIKey,
        ip_address: str,
    ) -> bool:

        allowlist = record.ip_allowlist or []

        if not allowlist:

            return True

        import ipaddress

        ip = ipaddress.ip_address(ip_address)

        for entry in allowlist:

            try:

                network = ipaddress.ip_network(
                    entry,
                    strict=False,
                )

                if ip in network:

                    return True

            except ValueError:

                if ip_address == entry:

                    return True

        return False


# ==========================================================
# Company Validation
# ==========================================================

    @staticmethod
    def validate_company(
        record: APIKey,
        company_id: int | None,
    ) -> bool:

        if record.company_id is None:

            return True

        return record.company_id == company_id


# ==========================================================
# User Keys
# ==========================================================

    def user_keys(
        self,
        user_id: int,
    ) -> list[APIKey]:

        return (

            self.db.query(APIKey)

            .filter(

                APIKey.user_id == user_id

            )

            .order_by(

                APIKey.created_at.desc()

            )

            .all()

        )


# ==========================================================
# Active Keys
# ==========================================================

    def active_keys(
        self,
        user_id: int,
    ) -> list[APIKey]:

        return (

            self.db.query(APIKey)

            .filter(

                APIKey.user_id == user_id,

                APIKey.revoked.is_(False),

            )

            .all()

        )


# ==========================================================
# Revoke User Keys
# ==========================================================

    def revoke_user_keys(
        self,
        user_id: int,
        reason: str = "bulk_revoke",
    ) -> int:

        records = self.active_keys(user_id)

        count = 0

        for record in records:

            record.revoked = True

            record.revoked_at = self.now()

            record.revocation_reason = reason

            count += 1

        self.db.commit()

        return count


# ==========================================================
# Cleanup Expired Keys
# ==========================================================

    def cleanup_expired(
        self,
    ) -> int:

        expired = (

            self.db.query(APIKey)

            .filter(

                APIKey.expires_at.is_not(None),

                APIKey.expires_at < self.now(),

            )

            .all()

        )

        count = len(expired)

        for record in expired:

            self.db.delete(record)

        self.db.commit()

        return count


# ==========================================================
# Usage Statistics
# ==========================================================

    def statistics(
        self,
        user_id: int | None = None,
    ) -> dict[str, Any]:

        query = self.db.query(APIKey)

        if user_id is not None:

            query = query.filter(

                APIKey.user_id == user_id

            )

        total = query.count()

        active = query.filter(

            APIKey.revoked.is_(False)

        ).count()

        revoked = query.filter(

            APIKey.revoked.is_(True)

        ).count()

        expired = query.filter(

            APIKey.expires_at.is_not(None),

            APIKey.expires_at < self.now(),

        ).count()

        usage = sum(

            key.usage_count

            for key in query.all()

        )

        return {

            "total": total,

            "active": active,

            "revoked": revoked,

            "expired": expired,

            "usage_count": usage,

        }


# ==========================================================
# Audit Event
# ==========================================================

    def audit_event(
        self,
        event: str,
        record: APIKey | None = None,
    ) -> dict[str, Any]:

        return {

            "timestamp": self.now(),

            "event": event,

            "api_key_id":

                record.id if record else None,

            "user_id":

                record.user_id if record else None,

            "company_id":

                record.company_id if record else None,

            "key_prefix":

                record.key_prefix if record else None,

            "usage_count":

                record.usage_count if record else None,

        }


# ==========================================================
# Security Report
# ==========================================================

    def security_report(
        self,
        user_id: int,
    ) -> dict[str, Any]:

        records = self.user_keys(user_id)

        return {

            "total_keys": len(records),

            "active_keys": sum(

                not key.revoked

                for key in records

            ),

            "revoked_keys": sum(

                key.revoked

                for key in records

            ),

            "expired_keys": sum(

                self.is_expired(key)

                for key in records

            ),

            "total_usage": sum(

                key.usage_count

                for key in records

            ),

        }
        
        # ==========================================================
# Recent Activity
# ==========================================================

    def recent_activity(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[APIKey]:

        return (

            self.db.query(APIKey)

            .filter(

                APIKey.user_id == user_id

            )

            .order_by(

                APIKey.last_used_at.desc()

            )

            .limit(limit)

            .all()

        )


# ==========================================================
# Most Used Keys
# ==========================================================

    def most_used_keys(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[APIKey]:

        return (

            self.db.query(APIKey)

            .filter(

                APIKey.user_id == user_id

            )

            .order_by(

                APIKey.usage_count.desc()

            )

            .limit(limit)

            .all()

        )


# ==========================================================
# Keys Expiring Soon
# ==========================================================

    def expiring_keys(
        self,
        days: int = 30,
    ) -> list[APIKey]:

        cutoff = self.now() + timedelta(days=days)

        return (

            self.db.query(APIKey)

            .filter(

                APIKey.revoked.is_(False),

                APIKey.expires_at.is_not(None),

                APIKey.expires_at <= cutoff,

            )

            .order_by(

                APIKey.expires_at.asc()

            )

            .all()

        )


# ==========================================================
# Rotate Expiring Keys
# ==========================================================

    def rotate_expiring_keys(
        self,
        days: int = 30,
    ) -> list[tuple[str, APIKey]]:

        rotated: list[tuple[str, APIKey]] = []

        for record in self.expiring_keys(days):

            rotated.append(

                self.rotate(record)

            )

        return rotated


# ==========================================================
# Last Activity Report
# ==========================================================

    def activity_report(
        self,
        user_id: int,
    ) -> dict[str, Any]:

        records = self.user_keys(user_id)

        if not records:

            return {

                "last_used": None,

                "total_requests": 0,

                "active_keys": 0,

            }

        latest = max(

            records,

            key=lambda r: (

                r.last_used_at

                or

                datetime.min.replace(

                    tzinfo=UTC

                )

            ),

        )

        return {

            "last_used": latest.last_used_at,

            "total_requests": sum(

                r.usage_count

                for r in records

            ),

            "active_keys": sum(

                not r.revoked

                for r in records

            ),

        }


# ==========================================================
# Key Health
# ==========================================================

    def key_health(
        self,
        record: APIKey,
    ) -> dict[str, Any]:

        return {

            "key_id": record.id,

            "active": not record.revoked,

            "expired": self.is_expired(record),

            "usage_count": record.usage_count,

            "last_used": record.last_used_at,

            "expires_at": record.expires_at,

            "has_ip_allowlist":

                bool(record.ip_allowlist),

            "scope_count":

                len(record.scopes or []),

        }


# ==========================================================
# Health Report
# ==========================================================

    def health(
        self,
    ) -> dict[str, Any]:

        stats = self.statistics()

        return {

            "service": "APIKeyService",

            "status": "healthy",

            "total_keys": stats["total"],

            "active_keys": stats["active"],

            "revoked_keys": stats["revoked"],

            "expired_keys": stats["expired"],

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
# Export Key
# ==========================================================

    def export_key(
        self,
        record: APIKey,
    ) -> dict[str, Any]:

        return {

            "id": record.id,

            "user_id": record.user_id,

            "company_id": record.company_id,

            "name": record.name,

            "key_prefix": record.key_prefix,

            "created_at": record.created_at,

            "last_used_at": record.last_used_at,

            "last_rotated_at":

                getattr(

                    record,

                    "last_rotated_at",

                    None,

                ),

            "expires_at": record.expires_at,

            "usage_count": record.usage_count,

            "revoked": record.revoked,

            "scopes": record.scopes,

            "ip_allowlist":

                record.ip_allowlist,

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

            "expiring_keys":

                len(

                    self.expiring_keys()

                ),

        }
        
        # ==========================================================
# Configuration Validation
# ==========================================================

    def validate_configuration(self) -> bool:

        if self.settings.key_length < 32:

            raise ValueError(
                "API key length must be at least 32."
            )

        if self.settings.max_keys_per_user <= 0:

            raise ValueError(
                "max_keys_per_user must be greater than zero."
            )

        if self.settings.default_expiry_days <= 0:

            raise ValueError(
                "default_expiry_days must be greater than zero."
            )

        return True


# ==========================================================
# Singleton
# ==========================================================

_api_key_service: APIKeyService | None = None


def initialize_api_key_service(
    db: Session,
    settings: APIKeySettings | None = None,
) -> APIKeyService:

    global _api_key_service

    _api_key_service = APIKeyService(

        db=db,

        settings=settings,

    )

    _api_key_service.validate_configuration()

    return _api_key_service


# ==========================================================
# Get Service
# ==========================================================

def get_api_key_service() -> APIKeyService:

    if _api_key_service is None:

        raise RuntimeError(

            "APIKeyService has not been initialized."

        )

    return _api_key_service


# ==========================================================
# Convenience Functions
# ==========================================================

def create_api_key(
    **kwargs,
):

    return get_api_key_service().create_key(
        **kwargs
    )


def authenticate_api_key(
    raw_key: str,
):

    return get_api_key_service().authenticate(
        raw_key
    )


def revoke_api_key(
    record: APIKey,
    reason: str | None = None,
):

    return get_api_key_service().revoke(

        record,

        reason,

    )


def rotate_api_key(
    record: APIKey,
):

    return get_api_key_service().rotate(
        record
    )


def cleanup_api_keys():

    return get_api_key_service().maintenance()


# ==========================================================
# Public Exports
# ==========================================================

__all__ = [

    "APIKeySettings",

    "APIKeyService",

    "initialize_api_key_service",

    "get_api_key_service",

    "create_api_key",

    "authenticate_api_key",

    "revoke_api_key",

    "rotate_api_key",

    "cleanup_api_keys",

]