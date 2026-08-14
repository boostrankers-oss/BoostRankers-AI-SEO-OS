from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from models.device import Device
from models.user import User


# ==========================================================
# Device Configuration
# ==========================================================

@dataclass(slots=True)
class DeviceSettings:

    trusted_days: int = 30

    fingerprint_algorithm: str = "sha256"

    max_devices_per_user: int = 25

    suspicious_login_window_hours: int = 24

    inactive_days: int = 180


DEFAULT_SETTINGS = DeviceSettings()


# ==========================================================
# Device Service
# ==========================================================

class DeviceService:

    def __init__(
        self,
        db: Session,
        settings: DeviceSettings | None = None,
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
# Fingerprint
# ==========================================================

    def fingerprint(

        self,

        user_agent: str,

        platform: str,

        screen: str,

        language: str,

    ) -> str:

        raw = "|".join(

            [

                user_agent,

                platform,

                screen,

                language,

            ]

        )

        return hashlib.new(

            self.settings.fingerprint_algorithm,

            raw.encode(),

        ).hexdigest()


# ==========================================================
# Device Identifier
# ==========================================================

    @staticmethod
    def device_identifier() -> str:

        return secrets.token_hex(16)


# ==========================================================
# Device Count
# ==========================================================

    def device_count(

        self,

        user_id: int,

    ) -> int:

        return (

            self.db.query(Device)

            .filter(

                Device.user_id == user_id,

                Device.revoked.is_(False),

            )

            .count()

        )


# ==========================================================
# Lookup Device
# ==========================================================

    def by_identifier(

        self,

        identifier: str,

    ) -> Device | None:

        return (

            self.db.query(Device)

            .filter(

                Device.device_identifier

                ==

                identifier

            )

            .first()

        )


# ==========================================================
# Lookup Fingerprint
# ==========================================================

    def by_fingerprint(

        self,

        fingerprint: str,

    ) -> Device | None:

        return (

            self.db.query(Device)

            .filter(

                Device.fingerprint

                ==

                fingerprint

            )

            .first()

        )


# ==========================================================
# Register Device
# ==========================================================

    def register(

        self,

        *,

        user: User,

        fingerprint: str,

        device_name: str,

        browser: str,

        operating_system: str,

        ip_address: str,

        location: str | None = None,

    ) -> Device:

        if (

            self.device_count(user.id)

            >=

            self.settings.max_devices_per_user

        ):

            raise ValueError(

                "Maximum number of devices reached."

            )

        record = Device(

            user_id=user.id,

            device_identifier=self.device_identifier(),

            fingerprint=fingerprint,

            device_name=device_name,

            browser=browser,

            operating_system=operating_system,

            ip_address=ip_address,

            location=location,

            trusted=False,

            trusted_until=None,

            created_at=self.now(),

            last_seen_at=self.now(),

            login_count=1,

            revoked=False,

        )

        self.db.add(record)

        self.db.commit()

        self.db.refresh(record)

        return record
        
        # ==========================================================
# Authenticate Device
# ==========================================================

    def authenticate(
        self,
        identifier: str,
        fingerprint: str,
    ) -> Device:

        device = self.by_identifier(identifier)

        if device is None:

            raise ValueError(
                "Device not found."
            )

        if device.revoked:

            raise ValueError(
                "Device has been revoked."
            )

        if device.fingerprint != fingerprint:

            raise ValueError(
                "Invalid device fingerprint."
            )

        self.mark_seen(device)

        return device


# ==========================================================
# Update Last Seen
# ==========================================================

    def mark_seen(
        self,
        device: Device,
        ip_address: str | None = None,
    ) -> None:

        device.last_seen_at = self.now()

        device.login_count += 1

        if ip_address:

            device.ip_address = ip_address

        self.db.commit()


# ==========================================================
# Trust Device
# ==========================================================

    def trust_device(
        self,
        device: Device,
    ) -> None:

        device.trusted = True

        device.trusted_until = (

            self.now()

            +

            timedelta(

                days=self.settings.trusted_days

            )

        )

        self.db.commit()


# ==========================================================
# Is Trusted
# ==========================================================

    def is_trusted(
        self,
        device: Device,
    ) -> bool:

        if not device.trusted:

            return False

        if device.trusted_until is None:

            return False

        return device.trusted_until > self.now()


# ==========================================================
# Remove Trust
# ==========================================================

    def untrust_device(
        self,
        device: Device,
    ) -> None:

        device.trusted = False

        device.trusted_until = None

        self.db.commit()


# ==========================================================
# Revoke Device
# ==========================================================

    def revoke(
        self,
        device: Device,
        reason: str | None = None,
    ) -> None:

        device.revoked = True

        device.revoked_at = self.now()

        device.revocation_reason = reason

        self.db.commit()


# ==========================================================
# Browser Detection
# ==========================================================

    @staticmethod
    def browser_name(
        user_agent: str,
    ) -> str:

        ua = user_agent.lower()

        if "edg/" in ua:

            return "Microsoft Edge"

        if "chrome/" in ua:

            return "Google Chrome"

        if "firefox/" in ua:

            return "Mozilla Firefox"

        if "safari/" in ua and "chrome/" not in ua:

            return "Safari"

        if "opr/" in ua:

            return "Opera"

        return "Unknown"


# ==========================================================
# Operating System Detection
# ==========================================================

    @staticmethod
    def operating_system(
        user_agent: str,
    ) -> str:

        ua = user_agent.lower()

        if "windows" in ua:

            return "Windows"

        if "mac os" in ua:

            return "macOS"

        if "android" in ua:

            return "Android"

        if "iphone" in ua or "ipad" in ua:

            return "iOS"

        if "linux" in ua:

            return "Linux"

        return "Unknown"


# ==========================================================
# New Device Detection
# ==========================================================

    def is_new_device(
        self,
        user_id: int,
        fingerprint: str,
    ) -> bool:

        device = (

            self.db.query(Device)

            .filter(

                Device.user_id == user_id,

                Device.fingerprint == fingerprint,

            )

            .first()

        )

        return device is None


# ==========================================================
# Associate Session
# ==========================================================

    def assign_session(
        self,
        device: Device,
        session_id: str,
    ) -> None:

        device.session_id = session_id

        self.db.commit()
        
        # ==========================================================
# User Devices
# ==========================================================

    def user_devices(
        self,
        user_id: int,
    ) -> list[Device]:

        return (

            self.db.query(Device)

            .filter(

                Device.user_id == user_id

            )

            .order_by(

                Device.last_seen_at.desc()

            )

            .all()

        )


# ==========================================================
# Active Devices
# ==========================================================

    def active_devices(
        self,
        user_id: int,
    ) -> list[Device]:

        return (

            self.db.query(Device)

            .filter(

                Device.user_id == user_id,

                Device.revoked.is_(False),

            )

            .order_by(

                Device.last_seen_at.desc()

            )

            .all()

        )


# ==========================================================
# Inactive Devices
# ==========================================================

    def inactive_devices(
        self,
        days: int | None = None,
    ) -> list[Device]:

        cutoff = self.now() - timedelta(

            days=days

            or

            self.settings.inactive_days

        )

        return (

            self.db.query(Device)

            .filter(

                Device.last_seen_at < cutoff,

                Device.revoked.is_(False),

            )

            .all()

        )


# ==========================================================
# Cleanup Inactive Devices
# ==========================================================

    def cleanup_inactive(
        self,
        days: int | None = None,
    ) -> int:

        devices = self.inactive_devices(days)

        count = len(devices)

        for device in devices:

            self.db.delete(device)

        self.db.commit()

        return count


# ==========================================================
# Bulk Revoke Devices
# ==========================================================

    def revoke_user_devices(
        self,
        user_id: int,
        reason: str = "bulk_revoke",
    ) -> int:

        devices = self.active_devices(user_id)

        count = 0

        for device in devices:

            device.revoked = True

            device.revoked_at = self.now()

            device.revocation_reason = reason

            count += 1

        self.db.commit()

        return count


# ==========================================================
# Device Risk Score
# ==========================================================

    def risk_score(
        self,
        device: Device,
    ) -> int:

        score = 0

        if not self.is_trusted(device):

            score += 20

        if device.login_count <= 1:

            score += 25

        if device.location is None:

            score += 10

        if device.revoked:

            score += 100

        age = (

            self.now()

            -

            device.created_at

        ).days

        if age < 7:

            score += 15

        return min(score, 100)


# ==========================================================
# Suspicious Login
# ==========================================================

    def suspicious_login(
        self,
        device: Device,
        ip_address: str,
        location: str | None,
    ) -> bool:

        if device.ip_address != ip_address:

            return True

        if (

            location

            and

            device.location

            and

            location != device.location

        ):

            return True

        return False


# ==========================================================
# Login History
# ==========================================================

    def login_history(
        self,
        user_id: int,
    ) -> list[dict[str, Any]]:

        records = self.user_devices(user_id)

        history = []

        for device in records:

            history.append(

                {

                    "device": device.device_name,

                    "browser": device.browser,

                    "operating_system":

                        device.operating_system,

                    "ip_address":

                        device.ip_address,

                    "location":

                        device.location,

                    "last_seen":

                        device.last_seen_at,

                    "login_count":

                        device.login_count,

                    "trusted":

                        self.is_trusted(device),

                }

            )

        return history


# ==========================================================
# Device Statistics
# ==========================================================

    def statistics(
        self,
        user_id: int | None = None,
    ) -> dict[str, Any]:

        query = self.db.query(Device)

        if user_id is not None:

            query = query.filter(

                Device.user_id == user_id

            )

        total = query.count()

        active = query.filter(

            Device.revoked.is_(False)

        ).count()

        trusted = query.filter(

            Device.trusted.is_(True)

        ).count()

        revoked = query.filter(

            Device.revoked.is_(True)

        ).count()

        return {

            "total": total,

            "active": active,

            "trusted": trusted,

            "revoked": revoked,

        }


# ==========================================================
# Audit Event
# ==========================================================

    def audit_event(
        self,
        event: str,
        device: Device | None = None,
    ) -> dict[str, Any]:

        return {

            "timestamp": self.now(),

            "event": event,

            "device_id":

                device.device_identifier

                if device else None,

            "user_id":

                device.user_id

                if device else None,

            "ip_address":

                device.ip_address

                if device else None,

            "trusted":

                device.trusted

                if device else None,

        }
        
        # ==========================================================
# Expire Trusted Devices
# ==========================================================

    def expire_trusted_devices(
        self,
    ) -> int:

        devices = (

            self.db.query(Device)

            .filter(

                Device.trusted.is_(True),

                Device.trusted_until.is_not(None),

                Device.trusted_until < self.now(),

            )

            .all()

        )

        count = 0

        for device in devices:

            device.trusted = False

            device.trusted_until = None

            count += 1

        self.db.commit()

        return count


# ==========================================================
# Security Report
# ==========================================================

    def security_report(
        self,
        user_id: int,
    ) -> dict[str, Any]:

        devices = self.user_devices(user_id)

        return {

            "total_devices": len(devices),

            "trusted_devices": sum(

                self.is_trusted(device)

                for device in devices

            ),

            "revoked_devices": sum(

                device.revoked

                for device in devices

            ),

            "high_risk_devices": sum(

                self.risk_score(device) >= 70

                for device in devices

            ),

        }


# ==========================================================
# Device Health
# ==========================================================

    def device_health(
        self,
        device: Device,
    ) -> dict[str, Any]:

        return {

            "device_identifier":

                device.device_identifier,

            "trusted":

                self.is_trusted(device),

            "revoked":

                device.revoked,

            "risk_score":

                self.risk_score(device),

            "last_seen":

                device.last_seen_at,

            "login_count":

                device.login_count,

            "browser":

                device.browser,

            "operating_system":

                device.operating_system,

            "ip_address":

                device.ip_address,

        }


# ==========================================================
# Export Device
# ==========================================================

    def export_device(
        self,
        device: Device,
    ) -> dict[str, Any]:

        return {

            "id": device.id,

            "user_id": device.user_id,

            "identifier":

                device.device_identifier,

            "device_name":

                device.device_name,

            "browser":

                device.browser,

            "operating_system":

                device.operating_system,

            "ip_address":

                device.ip_address,

            "location":

                device.location,

            "trusted":

                device.trusted,

            "trusted_until":

                device.trusted_until,

            "created_at":

                device.created_at,

            "last_seen_at":

                device.last_seen_at,

            "login_count":

                device.login_count,

            "revoked":

                device.revoked,

        }


# ==========================================================
# Service Health
# ==========================================================

    def health(
        self,
    ) -> dict[str, Any]:

        stats = self.statistics()

        return {

            "service": "DeviceService",

            "status": "healthy",

            "total_devices":

                stats["total"],

            "active_devices":

                stats["active"],

            "trusted_devices":

                stats["trusted"],

            "revoked_devices":

                stats["revoked"],

        }


# ==========================================================
# Maintenance
# ==========================================================

    def maintenance(
        self,
    ) -> dict[str, int]:

        expired_trust = self.expire_trusted_devices()

        removed = self.cleanup_inactive()

        return {

            "expired_trusted":

                expired_trust,

            "inactive_removed":

                removed,

        }


# ==========================================================
# Diagnostics
# ==========================================================

    def diagnostics(
        self,
    ) -> dict[str, Any]:

        return {

            "health":

                self.health(),

            "statistics":

                self.statistics(),

            "inactive_devices":

                len(

                    self.inactive_devices()

                ),

        }


# ==========================================================
# Configuration Validation
# ==========================================================

    def validate_configuration(
        self,
    ) -> bool:

        if self.settings.max_devices_per_user <= 0:

            raise ValueError(

                "max_devices_per_user must be greater than zero."

            )

        if self.settings.trusted_days <= 0:

            raise ValueError(

                "trusted_days must be greater than zero."

            )

        if self.settings.inactive_days <= 0:

            raise ValueError(

                "inactive_days must be greater than zero."

            )

        return True
        
        # ==========================================================
# Singleton
# ==========================================================

_device_service: DeviceService | None = None


def initialize_device_service(
    db: Session,
    settings: DeviceSettings | None = None,
) -> DeviceService:

    global _device_service

    _device_service = DeviceService(
        db=db,
        settings=settings,
    )

    _device_service.validate_configuration()

    return _device_service


# ==========================================================
# Get Service
# ==========================================================

def get_device_service() -> DeviceService:

    if _device_service is None:

        raise RuntimeError(
            "DeviceService has not been initialized."
        )

    return _device_service


# ==========================================================
# Convenience Functions
# ==========================================================

def register_device(**kwargs):

    return get_device_service().register(
        **kwargs
    )


def authenticate_device(
    identifier: str,
    fingerprint: str,
):

    return get_device_service().authenticate(
        identifier,
        fingerprint,
    )


def trust_device(
    device: Device,
):

    return get_device_service().trust_device(
        device
    )


def revoke_device(
    device: Device,
    reason: str | None = None,
):

    return get_device_service().revoke(
        device,
        reason,
    )


def user_devices(
    user_id: int,
):

    return get_device_service().user_devices(
        user_id
    )


def active_devices(
    user_id: int,
):

    return get_device_service().active_devices(
        user_id
    )


def security_report(
    user_id: int,
):

    return get_device_service().security_report(
        user_id
    )


def maintenance():

    return get_device_service().maintenance()


def diagnostics():

    return get_device_service().diagnostics()


# ==========================================================
# Public Exports
# ==========================================================

__all__ = [

    "DeviceSettings",

    "DeviceService",

    "initialize_device_service",

    "get_device_service",

    "register_device",

    "authenticate_device",

    "trust_device",

    "revoke_device",

    "user_devices",

    "active_devices",

    "security_report",

    "maintenance",

    "diagnostics",

]