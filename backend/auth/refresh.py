from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from auth.jwt import JWTService
from models.refresh_token import RefreshToken


# ==========================================================
# Refresh Configuration
# ==========================================================

@dataclass(slots=True)
class RefreshSettings:

    rotation_enabled: bool = True

    one_time_use: bool = True

    family_tracking: bool = True

    revoke_family_on_reuse: bool = True

    cleanup_days: int = 30


DEFAULT_SETTINGS = RefreshSettings()


# ==========================================================
# Refresh Service
# ==========================================================

class RefreshTokenService:

    def __init__(
        self,
        db: Session,
        jwt_service: JWTService,
        settings: RefreshSettings | None = None,
    ):

        self.db = db

        self.jwt = jwt_service

        self.settings = settings or DEFAULT_SETTINGS


# ==========================================================
# Current Time
# ==========================================================

    @staticmethod
    def now() -> datetime:

        return datetime.now(UTC)


# ==========================================================
# Generate Family ID
# ==========================================================

    @staticmethod
    def family_id() -> str:

        return uuid4().hex


# ==========================================================
# Generate Refresh ID
# ==========================================================

    @staticmethod
    def refresh_id() -> str:

        return uuid4().hex


# ==========================================================
# Create Refresh Record
# ==========================================================

    def create_record(
        self,
        *,
        user_id: int,
        session_id: str,
        device_id: str,
        token: str,
        expires_at: datetime,
        family_id: str | None = None,
        parent_id: str | None = None,
    ) -> RefreshToken:

        record = RefreshToken(

            user_id=user_id,

            token=token,

            session_id=session_id,

            device_id=device_id,

            refresh_id=self.refresh_id(),

            family_id=family_id
            or self.family_id(),

            parent_refresh_id=parent_id,

            expires_at=expires_at,

            issued_at=self.now(),

            revoked=False,

            reused=False,

        )

        self.db.add(record)

        self.db.commit()

        self.db.refresh(record)

        return record


# ==========================================================
# Lookup By Token
# ==========================================================

    def by_token(
        self,
        token: str,
    ) -> RefreshToken | None:

        return (

            self.db.query(RefreshToken)

            .filter(

                RefreshToken.token == token

            )

            .first()

        )


# ==========================================================
# Lookup By Refresh ID
# ==========================================================

    def by_refresh_id(
        self,
        refresh_id: str,
    ) -> RefreshToken | None:

        return (

            self.db.query(RefreshToken)

            .filter(

                RefreshToken.refresh_id
                == refresh_id

            )

            .first()

        )


# ==========================================================
# Is Expired
# ==========================================================

    def is_expired(
        self,
        record: RefreshToken,
    ) -> bool:

        return (

            record.expires_at

            <= self.now()

        )
        
        # ==========================================================
# Validate Refresh Token
# ==========================================================

    def validate(
        self,
        token: str,
    ) -> RefreshToken:

        record = self.by_token(token)

        if record is None:

            raise ValueError(
                "Refresh token not found."
            )

        if record.revoked:

            raise ValueError(
                "Refresh token revoked."
            )

        if record.reused:

            raise ValueError(
                "Refresh token already used."
            )

        if self.is_expired(record):

            raise ValueError(
                "Refresh token expired."
            )

        payload = self.jwt.require_refresh_token(
            token
        )

        self.jwt.ensure_not_revoked(payload)

        return record


# ==========================================================
# Mark As Used
# ==========================================================

    def mark_used(
        self,
        record: RefreshToken,
    ) -> None:

        record.reused = True

        record.used_at = self.now()

        self.db.commit()


# ==========================================================
# Revoke Refresh Token
# ==========================================================

    def revoke(
        self,
        record: RefreshToken,
        reason: str | None = None,
    ) -> None:

        record.revoked = True

        record.revoked_at = self.now()

        record.revocation_reason = reason

        self.db.commit()


# ==========================================================
# Revoke Token Family
# ==========================================================

    def revoke_family(
        self,
        family_id: str,
        reason: str = "family_revoked",
    ) -> int:

        records = (

            self.db.query(RefreshToken)

            .filter(
                RefreshToken.family_id == family_id
            )

            .all()

        )

        count = 0

        for record in records:

            if not record.revoked:

                record.revoked = True

                record.revoked_at = self.now()

                record.revocation_reason = reason

                count += 1

        self.db.commit()

        return count


# ==========================================================
# Replay Attack Detection
# ==========================================================

    def detect_replay(
        self,
        record: RefreshToken,
    ) -> bool:

        if record.reused:

            if self.settings.revoke_family_on_reuse:

                self.revoke_family(

                    record.family_id,

                    reason="refresh_replay",

                )

            return True

        return False


# ==========================================================
# Rotate Refresh Token
# ==========================================================

    def rotate(
        self,
        token: str,
        *,
        new_token: str,
        expires_at: datetime,
    ) -> RefreshToken:

        current = self.validate(token)

        if self.detect_replay(current):

            raise ValueError(
                "Refresh token replay detected."
            )

        if self.settings.one_time_use:

            self.mark_used(current)

        return self.create_record(

            user_id=current.user_id,

            session_id=current.session_id,

            device_id=current.device_id,

            token=new_token,

            expires_at=expires_at,

            family_id=current.family_id,

            parent_id=current.refresh_id,

        )


# ==========================================================
# Family History
# ==========================================================

    def family_history(
        self,
        family_id: str,
    ) -> list[RefreshToken]:

        return (

            self.db.query(RefreshToken)

            .filter(
                RefreshToken.family_id == family_id
            )

            .order_by(
                RefreshToken.issued_at.asc()
            )

            .all()

        )
        
        # ==========================================================
# Session Refresh Tokens
# ==========================================================

    def session_tokens(
        self,
        session_id: str,
    ) -> list[RefreshToken]:

        return (

            self.db.query(RefreshToken)

            .filter(

                RefreshToken.session_id
                == session_id

            )

            .order_by(

                RefreshToken.issued_at.desc()

            )

            .all()

        )


# ==========================================================
# Device Refresh Tokens
# ==========================================================

    def device_tokens(
        self,
        device_id: str,
    ) -> list[RefreshToken]:

        return (

            self.db.query(RefreshToken)

            .filter(

                RefreshToken.device_id
                == device_id

            )

            .order_by(

                RefreshToken.issued_at.desc()

            )

            .all()

        )


# ==========================================================
# User Refresh Tokens
# ==========================================================

    def user_tokens(
        self,
        user_id: int,
    ) -> list[RefreshToken]:

        return (

            self.db.query(RefreshToken)

            .filter(

                RefreshToken.user_id
                == user_id

            )

            .order_by(

                RefreshToken.issued_at.desc()

            )

            .all()

        )


# ==========================================================
# Logout Current Session
# ==========================================================

    def revoke_session(
        self,
        session_id: str,
        reason: str = "logout",
    ) -> int:

        records = self.session_tokens(
            session_id
        )

        count = 0

        for record in records:

            if not record.revoked:

                record.revoked = True

                record.revoked_at = self.now()

                record.revocation_reason = reason

                count += 1

        self.db.commit()

        return count


# ==========================================================
# Logout Device
# ==========================================================

    def revoke_device(
        self,
        device_id: str,
        reason: str = "device_logout",
    ) -> int:

        records = self.device_tokens(
            device_id
        )

        count = 0

        for record in records:

            if not record.revoked:

                record.revoked = True

                record.revoked_at = self.now()

                record.revocation_reason = reason

                count += 1

        self.db.commit()

        return count


# ==========================================================
# Logout All Devices
# ==========================================================

    def revoke_user(
        self,
        user_id: int,
        reason: str = "logout_all",
    ) -> int:

        records = self.user_tokens(
            user_id
        )

        count = 0

        for record in records:

            if not record.revoked:

                record.revoked = True

                record.revoked_at = self.now()

                record.revocation_reason = reason

                count += 1

        self.db.commit()

        return count


# ==========================================================
# Cleanup Expired Tokens
# ==========================================================

    def cleanup_expired(
        self,
    ) -> int:

        expired = (

            self.db.query(RefreshToken)

            .filter(

                RefreshToken.expires_at

                <

                self.now()

            )

            .all()

        )

        count = len(expired)

        for record in expired:

            self.db.delete(record)

        self.db.commit()

        return count


# ==========================================================
# Cleanup Revoked Tokens
# ==========================================================

    def cleanup_revoked(
        self,
    ) -> int:

        cutoff = self.now() - timedelta(

            days=self.settings.cleanup_days

        )

        revoked = (

            self.db.query(RefreshToken)

            .filter(

                RefreshToken.revoked.is_(True),

                RefreshToken.revoked_at < cutoff,

            )

            .all()

        )

        count = len(revoked)

        for record in revoked:

            self.db.delete(record)

        self.db.commit()

        return count
        
        # ==========================================================
# Active Token Count
# ==========================================================

    def active_count(
        self,
        user_id: int | None = None,
    ) -> int:

        query = self.db.query(RefreshToken).filter(
            RefreshToken.revoked.is_(False),
            RefreshToken.reused.is_(False),
            RefreshToken.expires_at > self.now(),
        )

        if user_id is not None:
            query = query.filter(
                RefreshToken.user_id == user_id
            )

        return query.count()


# ==========================================================
# Token Statistics
# ==========================================================

    def statistics(
        self,
        user_id: int | None = None,
    ) -> dict[str, Any]:

        query = self.db.query(RefreshToken)

        if user_id is not None:
            query = query.filter(
                RefreshToken.user_id == user_id
            )

        total = query.count()

        active = self.active_count(user_id)

        revoked = query.filter(
            RefreshToken.revoked.is_(True)
        ).count()

        reused = query.filter(
            RefreshToken.reused.is_(True)
        ).count()

        expired = query.filter(
            RefreshToken.expires_at <= self.now()
        ).count()

        return {

            "total": total,

            "active": active,

            "revoked": revoked,

            "reused": reused,

            "expired": expired,

        }


# ==========================================================
# Session Summary
# ==========================================================

    def session_summary(
        self,
        session_id: str,
    ) -> dict[str, Any]:

        records = self.session_tokens(
            session_id
        )

        return {

            "session_id": session_id,

            "tokens": len(records),

            "active": sum(
                not r.revoked and not r.reused
                for r in records
            ),

            "revoked": sum(
                r.revoked
                for r in records
            ),

            "reused": sum(
                r.reused
                for r in records
            ),

        }


# ==========================================================
# Device Summary
# ==========================================================

    def device_summary(
        self,
        device_id: str,
    ) -> dict[str, Any]:

        records = self.device_tokens(
            device_id
        )

        return {

            "device_id": device_id,

            "tokens": len(records),

            "active": sum(
                not r.revoked and not r.reused
                for r in records
            ),

            "revoked": sum(
                r.revoked
                for r in records
            ),

            "reused": sum(
                r.reused
                for r in records
            ),

        }


# ==========================================================
# Family Integrity Check
# ==========================================================

    def verify_family(
        self,
        family_id: str,
    ) -> bool:

        records = self.family_history(
            family_id
        )

        ids = {

            r.refresh_id

            for r in records

        }

        for record in records:

            if (
                record.parent_refresh_id
                and
                record.parent_refresh_id not in ids
            ):
                return False

        return True


# ==========================================================
# Replay Report
# ==========================================================

    def replay_report(
        self,
    ) -> list[dict[str, Any]]:

        records = (

            self.db.query(RefreshToken)

            .filter(

                RefreshToken.reused.is_(True)

            )

            .all()

        )

        return [

            {

                "user_id": r.user_id,

                "refresh_id": r.refresh_id,

                "family_id": r.family_id,

                "used_at": r.used_at,

                "device_id": r.device_id,

                "session_id": r.session_id,

            }

            for r in records

        ]


# ==========================================================
# Service Health
# ==========================================================

    def health(
        self,
    ) -> dict[str, Any]:

        return {

            "service": "RefreshTokenService",

            "status": "healthy",

            "rotation_enabled":
                self.settings.rotation_enabled,

            "one_time_use":
                self.settings.one_time_use,

            "family_tracking":
                self.settings.family_tracking,

            "cleanup_days":
                self.settings.cleanup_days,

        }


# ==========================================================
# Audit Hook
# ==========================================================

    def audit_event(
        self,
        event: str,
        record: RefreshToken | None = None,
    ) -> dict[str, Any]:

        return {

            "timestamp": self.now(),

            "event": event,

            "user_id":
                record.user_id if record else None,

            "refresh_id":
                record.refresh_id if record else None,

            "family_id":
                record.family_id if record else None,

            "session_id":
                record.session_id if record else None,

            "device_id":
                record.device_id if record else None,

        }
        
        # ==========================================================
# Configuration Validation
# ==========================================================

    def validate_configuration(self) -> bool:

        if self.settings.cleanup_days <= 0:

            raise ValueError(
                "cleanup_days must be greater than zero."
            )

        if self.settings.rotation_enabled is False:

            print(
                "WARNING: Refresh token rotation is disabled."
            )

        return True


# ==========================================================
# Bulk Maintenance
# ==========================================================

    def maintenance(self) -> dict[str, int]:

        expired = self.cleanup_expired()

        revoked = self.cleanup_revoked()

        return {

            "expired_removed": expired,

            "revoked_removed": revoked,

        }


# ==========================================================
# Refresh Token Health
# ==========================================================

    def diagnostics(self) -> dict[str, Any]:

        return {

            "configuration": self.validate_configuration(),

            "statistics": self.statistics(),

            "health": self.health(),

        }


# ==========================================================
# Export Token Metadata
# ==========================================================

    def export_token(
        self,
        record: RefreshToken,
    ) -> dict[str, Any]:

        return {

            "user_id": record.user_id,

            "refresh_id": record.refresh_id,

            "family_id": record.family_id,

            "parent_refresh_id": record.parent_refresh_id,

            "session_id": record.session_id,

            "device_id": record.device_id,

            "issued_at": record.issued_at,

            "expires_at": record.expires_at,

            "used_at": record.used_at,

            "revoked": record.revoked,

            "revoked_at": record.revoked_at,

            "reused": record.reused,

        }


# ==========================================================
# Singleton
# ==========================================================

_refresh_service: RefreshTokenService | None = None


def initialize_refresh_service(
    db: Session,
    jwt_service: JWTService,
    settings: RefreshSettings | None = None,
) -> RefreshTokenService:

    global _refresh_service

    _refresh_service = RefreshTokenService(

        db=db,

        jwt_service=jwt_service,

        settings=settings,

    )

    _refresh_service.validate_configuration()

    return _refresh_service


# ==========================================================
# Get Service
# ==========================================================

def get_refresh_service() -> RefreshTokenService:

    if _refresh_service is None:

        raise RuntimeError(

            "RefreshTokenService has not been initialized."

        )

    return _refresh_service


# ==========================================================
# Convenience Functions
# ==========================================================

def validate_refresh_token(
    token: str,
) -> RefreshToken:

    return get_refresh_service().validate(token)


def rotate_refresh_token(
    token: str,
    *,
    new_token: str,
    expires_at: datetime,
) -> RefreshToken:

    return get_refresh_service().rotate(

        token,

        new_token=new_token,

        expires_at=expires_at,

    )


def revoke_session(
    session_id: str,
) -> int:

    return get_refresh_service().revoke_session(
        session_id
    )


def revoke_user(
    user_id: int,
) -> int:

    return get_refresh_service().revoke_user(
        user_id
    )


def cleanup_refresh_tokens() -> dict[str, int]:

    return get_refresh_service().maintenance()


# ==========================================================
# Public Exports
# ==========================================================

__all__ = [

    "RefreshSettings",

    "RefreshTokenService",

    "initialize_refresh_service",

    "get_refresh_service",

    "validate_refresh_token",

    "rotate_refresh_token",

    "revoke_session",

    "revoke_user",

    "cleanup_refresh_tokens",

]