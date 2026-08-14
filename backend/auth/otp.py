from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import pyotp
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from models.user import User
from models.otp import OTPRecord


# ==========================================================
# OTP Configuration
# ==========================================================

@dataclass(slots=True)
class OTPSettings:

    issuer: str = "Boost Rankers"

    digits: int = 6

    interval: int = 30

    algorithm: str = "SHA1"

    email_expiry_minutes: int = 10

    sms_expiry_minutes: int = 5

    max_attempts: int = 5

    backup_codes: int = 10

    secret_length: int = 32

    trusted_device_days: int = 30


DEFAULT_SETTINGS = OTPSettings()


# ==========================================================
# OTP Service
# ==========================================================

class OTPService:

    def __init__(
        self,
        db: Session,
        encryption_key: str,
        settings: OTPSettings | None = None,
    ):

        self.db = db

        self.settings = settings or DEFAULT_SETTINGS

        self.cipher = Fernet(encryption_key.encode())


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

        return pyotp.random_base32(
            length=self.settings.secret_length
        )


# ==========================================================
# Encrypt Secret
# ==========================================================

    def encrypt_secret(
        self,
        secret: str,
    ) -> str:

        return self.cipher.encrypt(
            secret.encode()
        ).decode()


# ==========================================================
# Decrypt Secret
# ==========================================================

    def decrypt_secret(
        self,
        encrypted: str,
    ) -> str:

        return self.cipher.decrypt(
            encrypted.encode()
        ).decode()


# ==========================================================
# Generate Recovery Code
# ==========================================================

    @staticmethod
    def generate_backup_code() -> str:

        return secrets.token_hex(5).upper()


# ==========================================================
# Generate Recovery Codes
# ==========================================================

    def generate_backup_codes(
        self,
    ) -> list[str]:

        return [

            self.generate_backup_code()

            for _ in range(

                self.settings.backup_codes

            )

        ]


# ==========================================================
# Hash Backup Code
# ==========================================================

    @staticmethod
    def hash_backup_code(
        code: str,
    ) -> str:

        return hashlib.sha256(

            code.encode()

        ).hexdigest()


# ==========================================================
# Verify Backup Code
# ==========================================================

    @staticmethod
    def verify_backup_code(
        code: str,
        hashed: str,
    ) -> bool:

        return hmac.compare_digest(

            hashlib.sha256(

                code.encode()

            ).hexdigest(),

            hashed,

        )


# ==========================================================
# Store Backup Codes
# ==========================================================

    def hashed_backup_codes(
        self,
        codes: list[str],
    ) -> list[str]:

        return [

            self.hash_backup_code(code)

            for code in codes

        ]
        
        # ==========================================================
# Create TOTP
# ==========================================================

    def totp(
        self,
        secret: str,
    ) -> pyotp.TOTP:

        return pyotp.TOTP(

            secret,

            digits=self.settings.digits,

            interval=self.settings.interval,

            digest=getattr(hashlib, self.settings.algorithm.lower()),

        )


# ==========================================================
# Create HOTP
# ==========================================================

    def hotp(
        self,
        secret: str,
    ) -> pyotp.HOTP:

        return pyotp.HOTP(

            secret,

            digits=self.settings.digits,

            digest=getattr(hashlib, self.settings.algorithm.lower()),

        )


# ==========================================================
# Generate TOTP Code
# ==========================================================

    def generate_totp_code(
        self,
        secret: str,
    ) -> str:

        return self.totp(secret).now()


# ==========================================================
# Verify TOTP Code
# ==========================================================

    def verify_totp(
        self,
        secret: str,
        code: str,
        valid_window: int = 1,
    ) -> bool:

        return self.totp(secret).verify(

            code,

            valid_window=valid_window,

        )


# ==========================================================
# Generate HOTP Code
# ==========================================================

    def generate_hotp_code(
        self,
        secret: str,
        counter: int,
    ) -> str:

        return self.hotp(secret).at(counter)


# ==========================================================
# Verify HOTP Code
# ==========================================================

    def verify_hotp(
        self,
        secret: str,
        code: str,
        counter: int,
    ) -> bool:

        return self.hotp(secret).verify(

            code,

            counter,

        )


# ==========================================================
# Provisioning URI
# ==========================================================

    def provisioning_uri(
        self,
        email: str,
        secret: str,
    ) -> str:

        return self.totp(secret).provisioning_uri(

            name=email,

            issuer_name=self.settings.issuer,

        )


# ==========================================================
# QR Code URI
# ==========================================================

    def qr_uri(
        self,
        email: str,
        secret: str,
    ) -> str:

        return self.provisioning_uri(

            email,

            secret,

        )


# ==========================================================
# Generate Email OTP
# ==========================================================

    def generate_email_code(
        self,
    ) -> str:

        return f"{secrets.randbelow(1000000):06d}"


# ==========================================================
# Generate SMS OTP
# ==========================================================

    def generate_sms_code(
        self,
    ) -> str:

        return f"{secrets.randbelow(1000000):06d}"


# ==========================================================
# Store OTP
# ==========================================================

    def create_otp(
        self,
        *,
        user_id: int,
        channel: str,
        code: str,
        expires_at: datetime,
    ) -> OTPRecord:

        record = OTPRecord(

            user_id=user_id,

            channel=channel,

            code_hash=hashlib.sha256(

                code.encode()

            ).hexdigest(),

            issued_at=self.now(),

            expires_at=expires_at,

            attempts=0,

            verified=False,

        )

        self.db.add(record)

        self.db.commit()

        self.db.refresh(record)

        return record


# ==========================================================
# Generate Email OTP Record
# ==========================================================

    def issue_email_otp(
        self,
        user_id: int,
    ) -> tuple[str, OTPRecord]:

        code = self.generate_email_code()

        expires = self.now() + timedelta(

            minutes=self.settings.email_expiry_minutes

        )

        record = self.create_otp(

            user_id=user_id,

            channel="email",

            code=code,

            expires_at=expires,

        )

        return code, record


# ==========================================================
# Generate SMS OTP Record
# ==========================================================

    def issue_sms_otp(
        self,
        user_id: int,
    ) -> tuple[str, OTPRecord]:

        code = self.generate_sms_code()

        expires = self.now() + timedelta(

            minutes=self.settings.sms_expiry_minutes

        )

        record = self.create_otp(

            user_id=user_id,

            channel="sms",

            code=code,

            expires_at=expires,

        )

        return code, record
        
        # ==========================================================
# Lookup OTP
# ==========================================================

    def get_otp(
        self,
        otp_id: int,
    ) -> OTPRecord | None:

        return (

            self.db.query(OTPRecord)

            .filter(

                OTPRecord.id == otp_id

            )

            .first()

        )


# ==========================================================
# Check Expiration
# ==========================================================

    def is_expired(
        self,
        record: OTPRecord,
    ) -> bool:

        return self.now() >= record.expires_at


# ==========================================================
# Increment Attempts
# ==========================================================

    def increment_attempts(
        self,
        record: OTPRecord,
    ) -> None:

        record.attempts += 1

        self.db.commit()


# ==========================================================
# Max Attempts Reached
# ==========================================================

    def max_attempts_reached(
        self,
        record: OTPRecord,
    ) -> bool:

        return (

            record.attempts

            >=

            self.settings.max_attempts

        )


# ==========================================================
# Mark Verified
# ==========================================================

    def mark_verified(
        self,
        record: OTPRecord,
    ) -> None:

        record.verified = True

        record.verified_at = self.now()

        self.db.commit()


# ==========================================================
# Invalidate OTP
# ==========================================================

    def invalidate(
        self,
        record: OTPRecord,
    ) -> None:

        self.db.delete(record)

        self.db.commit()


# ==========================================================
# Verify Email/SMS OTP
# ==========================================================

    def verify_otp(
        self,
        record: OTPRecord,
        code: str,
    ) -> bool:

        if record.verified:

            return False

        if self.is_expired(record):

            return False

        if self.max_attempts_reached(record):

            return False

        expected = hashlib.sha256(

            code.encode()

        ).hexdigest()

        if not hmac.compare_digest(

            expected,

            record.code_hash,

        ):

            self.increment_attempts(record)

            return False

        self.mark_verified(record)

        self.invalidate(record)

        return True


# ==========================================================
# Register Trusted Device
# ==========================================================

    def trust_device(
        self,
        user: User,
        device_id: str,
    ) -> None:

        trusted = getattr(

            user,

            "trusted_devices",

            {},

        )

        trusted[device_id] = (

            self.now()

            +

            timedelta(

                days=self.settings.trusted_device_days

            )

        ).isoformat()

        user.trusted_devices = trusted

        self.db.commit()


# ==========================================================
# Is Trusted Device
# ==========================================================

    def is_trusted_device(
        self,
        user: User,
        device_id: str,
    ) -> bool:

        trusted = getattr(

            user,

            "trusted_devices",

            {},

        )

        expiry = trusted.get(device_id)

        if not expiry:

            return False

        return (

            datetime.fromisoformat(expiry)

            >

            self.now()

        )


# ==========================================================
# Remove Trusted Device
# ==========================================================

    def revoke_trusted_device(
        self,
        user: User,
        device_id: str,
    ) -> None:

        trusted = getattr(

            user,

            "trusted_devices",

            {},

        )

        trusted.pop(device_id, None)

        user.trusted_devices = trusted

        self.db.commit()


# ==========================================================
# Audit Event
# ==========================================================

    def audit_event(
        self,
        event: str,
        user_id: int,
        channel: str,
    ) -> dict[str, Any]:

        return {

            "timestamp": self.now(),

            "event": event,

            "user_id": user_id,

            "channel": channel,

        }
        
        # ==========================================================
# Enable MFA
# ==========================================================

    def enable_mfa(
        self,
        user: User,
        encrypted_secret: str,
        backup_codes: list[str],
    ) -> None:

        user.mfa_enabled = True

        user.mfa_secret = encrypted_secret

        user.mfa_backup_codes = backup_codes

        user.mfa_enabled_at = self.now()

        self.db.commit()


# ==========================================================
# Disable MFA
# ==========================================================

    def disable_mfa(
        self,
        user: User,
    ) -> None:

        user.mfa_enabled = False

        user.mfa_secret = None

        user.mfa_backup_codes = []

        user.mfa_enabled_at = None

        self.db.commit()


# ==========================================================
# Consume Backup Code
# ==========================================================

    def use_backup_code(
        self,
        user: User,
        code: str,
    ) -> bool:

        stored = list(user.mfa_backup_codes or [])

        for hashed in stored:

            if self.verify_backup_code(
                code,
                hashed,
            ):

                stored.remove(hashed)

                user.mfa_backup_codes = stored

                self.db.commit()

                return True

        return False


# ==========================================================
# Remaining Backup Codes
# ==========================================================

    def remaining_backup_codes(
        self,
        user: User,
    ) -> int:

        return len(

            user.mfa_backup_codes

            or

            []

        )


# ==========================================================
# Regenerate Backup Codes
# ==========================================================

    def regenerate_backup_codes(
        self,
        user: User,
    ) -> list[str]:

        codes = self.generate_backup_codes()

        user.mfa_backup_codes = (

            self.hashed_backup_codes(

                codes

            )

        )

        self.db.commit()

        return codes


# ==========================================================
# MFA Status
# ==========================================================

    def mfa_status(
        self,
        user: User,
    ) -> dict[str, Any]:

        return {

            "enabled": user.mfa_enabled,

            "backup_codes":

                self.remaining_backup_codes(

                    user

                ),

            "trusted_devices":

                len(

                    getattr(

                        user,

                        "trusted_devices",

                        {},

                    )

                ),

            "enabled_at":

                user.mfa_enabled_at,

        }


# ==========================================================
# Cleanup Expired OTP Records
# ==========================================================

    def cleanup_expired(
        self,
    ) -> int:

        expired = (

            self.db.query(OTPRecord)

            .filter(

                OTPRecord.expires_at

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
# OTP Statistics
# ==========================================================

    def statistics(
        self,
    ) -> dict[str, Any]:

        total = (

            self.db.query(

                OTPRecord

            )

            .count()

        )

        verified = (

            self.db.query(

                OTPRecord

            )

            .filter(

                OTPRecord.verified.is_(True)

            )

            .count()

        )

        pending = total - verified

        expired = (

            self.db.query(

                OTPRecord

            )

            .filter(

                OTPRecord.expires_at

                <

                self.now()

            )

            .count()

        )

        return {

            "total": total,

            "verified": verified,

            "pending": pending,

            "expired": expired,

        }


# ==========================================================
# Health
# ==========================================================

    def health(
        self,
    ) -> dict[str, Any]:

        return {

            "service": "OTPService",

            "status": "healthy",

            "issuer": self.settings.issuer,

            "digits": self.settings.digits,

            "interval": self.settings.interval,

            "max_attempts":

                self.settings.max_attempts,

            "backup_codes":

                self.settings.backup_codes,

        }


# ==========================================================
# Security Report
# ==========================================================

    def security_report(
        self,
        user: User,
    ) -> dict[str, Any]:

        return {

            "mfa_enabled":

                user.mfa_enabled,

            "trusted_devices":

                len(

                    getattr(

                        user,

                        "trusted_devices",

                        {},

                    )

                ),

            "backup_codes":

                self.remaining_backup_codes(

                    user

                ),

            "enabled_at":

                user.mfa_enabled_at,

        }
        
        # ==========================================================
# Configuration Validation
# ==========================================================

    def validate_configuration(self) -> bool:

        if self.settings.digits < 6:

            raise ValueError(
                "OTP must contain at least 6 digits."
            )

        if self.settings.interval <= 0:

            raise ValueError(
                "OTP interval must be greater than zero."
            )

        if self.settings.max_attempts <= 0:

            raise ValueError(
                "max_attempts must be greater than zero."
            )

        if self.settings.backup_codes <= 0:

            raise ValueError(
                "backup_codes must be greater than zero."
            )

        return True


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
# Diagnostics
# ==========================================================

    def diagnostics(
        self,
    ) -> dict[str, Any]:

        return {

            "configuration":

                self.validate_configuration(),

            "health":

                self.health(),

            "statistics":

                self.statistics(),

        }


# ==========================================================
# Export User MFA
# ==========================================================

    def export_user(
        self,
        user: User,
    ) -> dict[str, Any]:

        return {

            "user_id": user.id,

            "mfa_enabled": user.mfa_enabled,

            "enabled_at": user.mfa_enabled_at,

            "trusted_devices":

                len(

                    getattr(

                        user,

                        "trusted_devices",

                        {},

                    )

                ),

            "backup_codes":

                self.remaining_backup_codes(

                    user

                ),

        }


# ==========================================================
# Singleton
# ==========================================================

_otp_service: OTPService | None = None


def initialize_otp_service(
    db: Session,
    encryption_key: str,
    settings: OTPSettings | None = None,
) -> OTPService:

    global _otp_service

    _otp_service = OTPService(

        db=db,

        encryption_key=encryption_key,

        settings=settings,

    )

    _otp_service.validate_configuration()

    return _otp_service


# ==========================================================
# Service Getter
# ==========================================================

def get_otp_service() -> OTPService:

    if _otp_service is None:

        raise RuntimeError(

            "OTPService has not been initialized."

        )

    return _otp_service


# ==========================================================
# Convenience Helpers
# ==========================================================

def issue_email_otp(
    user_id: int,
):

    return get_otp_service().issue_email_otp(
        user_id
    )


def issue_sms_otp(
    user_id: int,
):

    return get_otp_service().issue_sms_otp(
        user_id
    )


def verify_otp(
    record: OTPRecord,
    code: str,
):

    return get_otp_service().verify_otp(

        record,

        code,

    )


def enable_mfa(
    user: User,
    encrypted_secret: str,
    backup_codes: list[str],
):

    return get_otp_service().enable_mfa(

        user,

        encrypted_secret,

        backup_codes,

    )


def disable_mfa(
    user: User,
):

    return get_otp_service().disable_mfa(
        user
    )


def cleanup_otps():

    return get_otp_service().maintenance()


# ==========================================================
# Public Exports
# ==========================================================

__all__ = [

    "OTPSettings",

    "OTPService",

    "initialize_otp_service",

    "get_otp_service",

    "issue_email_otp",

    "issue_sms_otp",

    "verify_otp",

    "enable_mfa",

    "disable_mfa",

    "cleanup_otps",

]