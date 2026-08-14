from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet


# ==========================================================
# Environment
# ==========================================================

class Environment(StrEnum):

    DEVELOPMENT = "development"

    TESTING = "testing"

    STAGING = "staging"

    PRODUCTION = "production"


# ==========================================================
# Configuration
# ==========================================================

@dataclass(slots=True)
class ConfigurationSettings:

    environment: Environment = Environment.DEVELOPMENT

    app_name: str = "Boost Rankers AI SEO OS"

    version: str = "1.0.0"

    company_name: str = "Boost Rankers"

    debug: bool = True

    secret_key: str = os.getenv(
        "SECRET_KEY",
        "CHANGE_ME",
    )

    encryption_key: bytes = field(

        default_factory=Fernet.generate_key

    )

    config_directory: Path = Path("config")

    config_file: str = "application.json"

    auto_reload: bool = False

    reload_interval: int = 30

    validate_on_load: bool = True


DEFAULT_SETTINGS = ConfigurationSettings()


# ==========================================================
# Configuration Service
# ==========================================================

class ConfigurationService:

    def __init__(
        self,
        settings: ConfigurationSettings | None = None,
    ):

        self.settings = settings or DEFAULT_SETTINGS

        self._cipher = Fernet(

            self.settings.encryption_key

        )

        self._lock = threading.RLock()

        self._configuration: dict[str, Any] = {}

        self._runtime: dict[str, Any] = {}

        self._companies: dict[str, dict[str, Any]] = {}

        self._last_loaded: datetime | None = None

        self._load_configuration()


# ==========================================================
# Current Time
# ==========================================================

    @staticmethod
    def now() -> datetime:

        return datetime.now(UTC)


# ==========================================================
# Configuration Path
# ==========================================================

    @property
    def config_path(self) -> Path:

        return (

            self.settings.config_directory

            /

            self.settings.config_file

        )


# ==========================================================
# Load Configuration
# ==========================================================

    def _load_configuration(self) -> None:

        with self._lock:

            self.settings.config_directory.mkdir(

                parents=True,

                exist_ok=True,

            )

            if self.config_path.exists():

                self._configuration = json.loads(

                    self.config_path.read_text(

                        encoding="utf-8"

                    )

                )

            else:

                self._configuration = {}

                self.save()

            self._last_loaded = self.now()


# ==========================================================
# Save Configuration
# ==========================================================

    def save(self) -> None:

        with self._lock:

            self.config_path.write_text(

                json.dumps(

                    self._configuration,

                    indent=4,

                    ensure_ascii=False,

                ),

                encoding="utf-8",

            )


# ==========================================================
# Get Value
# ==========================================================

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:

        return self._configuration.get(

            key,

            default,

        )


# ==========================================================
# Set Value
# ==========================================================

    def set(
        self,
        key: str,
        value: Any,
        save: bool = True,
    ) -> None:

        with self._lock:

            self._configuration[key] = value

            if save:

                self.save()


# ==========================================================
# Runtime Configuration
# ==========================================================

    def runtime_get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:

        return self._runtime.get(

            key,

            default,

        )


    def runtime_set(
        self,
        key: str,
        value: Any,
    ) -> None:

        with self._lock:

            self._runtime[key] = value


# ==========================================================
# Encryption
# ==========================================================

    def encrypt(
        self,
        value: str,
    ) -> str:

        return self._cipher.encrypt(

            value.encode()

        ).decode()


    def decrypt(
        self,
        value: str,
    ) -> str:

        return self._cipher.decrypt(

            value.encode()

        ).decode()


# ==========================================================
# Secret Manager
# ==========================================================

    def set_secret(
        self,
        name: str,
        value: str,
    ) -> None:

        self.set(

            f"secret:{name}",

            self.encrypt(value),

        )


    def get_secret(
        self,
        name: str,
    ) -> str | None:

        value = self.get(

            f"secret:{name}"

        )

        if value is None:

            return None

        return self.decrypt(value)
        
        # ==========================================================
# Environment Validation
# ==========================================================

    def validate_environment(self) -> bool:

        if self.settings.environment not in Environment:

            raise ValueError(

                f"Invalid environment: {self.settings.environment}"

            )

        return True


# ==========================================================
# Configuration Validation
# ==========================================================

    def validate(self) -> bool:

        self.validate_environment()

        if not self.settings.app_name:

            raise ValueError(

                "Application name is required."

            )

        if not self.settings.version:

            raise ValueError(

                "Application version is required."

            )

        if not self.settings.company_name:

            raise ValueError(

                "Company name is required."

            )

        if not self.settings.secret_key:

            raise ValueError(

                "Secret key is required."

            )

        if self.settings.reload_interval <= 0:

            raise ValueError(

                "Reload interval must be greater than zero."

            )

        return True


# ==========================================================
# Reload Configuration
# ==========================================================

    def reload(self) -> None:

        with self._lock:

            self._load_configuration()


# ==========================================================
# Dynamic Update
# ==========================================================

    def update(
        self,
        values: dict[str, Any],
        save: bool = True,
    ) -> None:

        with self._lock:

            self._configuration.update(values)

            if save:

                self.save()


# ==========================================================
# Merge Configuration
# ==========================================================

    def merge(
        self,
        values: dict[str, Any],
    ) -> None:

        def recursive_merge(
            target: dict[str, Any],
            source: dict[str, Any],
        ) -> None:

            for key, value in source.items():

                if (

                    isinstance(value, dict)

                    and

                    isinstance(target.get(key), dict)

                ):

                    recursive_merge(

                        target[key],

                        value,

                    )

                else:

                    target[key] = value

        with self._lock:

            recursive_merge(

                self._configuration,

                values,

            )


# ==========================================================
# Environment Overrides
# ==========================================================

    def apply_environment_overrides(self) -> None:

        prefix = "BR_"

        overrides: dict[str, Any] = {}

        for key, value in os.environ.items():

            if key.startswith(prefix):

                config_key = (

                    key.removeprefix(prefix)

                    .lower()

                )

                overrides[config_key] = value

        if overrides:

            self.merge(overrides)


# ==========================================================
# Runtime Override
# ==========================================================

    def override(
        self,
        key: str,
        value: Any,
    ) -> None:

        with self._lock:

            self._runtime[key] = value


# ==========================================================
# Remove Override
# ==========================================================

    def remove_override(
        self,
        key: str,
    ) -> None:

        with self._lock:

            self._runtime.pop(

                key,

                None,

            )


# ==========================================================
# Export Configuration
# ==========================================================

    def export(
        self,
    ) -> dict[str, Any]:

        with self._lock:

            return {

                **self._configuration

            }


# ==========================================================
# Import Configuration
# ==========================================================

    def import_configuration(
        self,
        configuration: dict[str, Any],
    ) -> None:

        with self._lock:

            self._configuration = configuration

            self.save()


# ==========================================================
# Configuration Version
# ==========================================================

    def configuration_version(
        self,
    ) -> str:

        return self.settings.version


# ==========================================================
# Last Reload
# ==========================================================

    @property
    def last_reload(
        self,
    ) -> datetime | None:

        return self._last_loaded


# ==========================================================
# Hot Reload
# ==========================================================

    def hot_reload(
        self,
    ) -> bool:

        if not self.settings.auto_reload:

            return False

        self.reload()

        return True


# ==========================================================
# Secret Exists
# ==========================================================

    def has_secret(
        self,
        name: str,
    ) -> bool:

        return self.get(

            f"secret:{name}"

        ) is not None


# ==========================================================
# Remove Secret
# ==========================================================

    def remove_secret(
        self,
        name: str,
    ) -> None:

        with self._lock:

            self._configuration.pop(

                f"secret:{name}",

                None,

            )

            self.save()


# ==========================================================
# Secret Rotation
# ==========================================================

    def rotate_secret(
        self,
        name: str,
        new_value: str,
    ) -> None:

        self.set_secret(

            name,

            new_value,

        )
        
        # ==========================================================
# Company Configuration
# ==========================================================

    def set_company_configuration(
        self,
        company_id: str,
        configuration: dict[str, Any],
    ) -> None:

        with self._lock:

            self._companies[company_id] = configuration


    def company_configuration(
        self,
        company_id: str,
    ) -> dict[str, Any]:

        return self._companies.get(
            company_id,
            {},
        )


# ==========================================================
# Company Configuration Merge
# ==========================================================

    def effective_configuration(
        self,
        company_id: str | None = None,
    ) -> dict[str, Any]:

        configuration = self.export()

        if company_id:

            configuration.update(

                self.company_configuration(
                    company_id
                )

            )

        configuration.update(self._runtime)

        return configuration


# ==========================================================
# White Label Configuration
# ==========================================================

    def set_branding(
        self,
        company_id: str,
        branding: dict[str, Any],
    ) -> None:

        company = self._companies.setdefault(
            company_id,
            {},
        )

        company["branding"] = branding


    def branding(
        self,
        company_id: str,
    ) -> dict[str, Any]:

        return (

            self.company_configuration(
                company_id
            )

            .get("branding", {})

        )


# ==========================================================
# Feature Flags
# ==========================================================

    def enable_feature(
        self,
        company_id: str,
        feature: str,
    ) -> None:

        company = self._companies.setdefault(
            company_id,
            {},
        )

        features = company.setdefault(
            "features",
            {},
        )

        features[feature] = True


    def disable_feature(
        self,
        company_id: str,
        feature: str,
    ) -> None:

        company = self._companies.setdefault(
            company_id,
            {},
        )

        features = company.setdefault(
            "features",
            {},
        )

        features[feature] = False


    def feature_enabled(
        self,
        company_id: str,
        feature: str,
        default: bool = False,
    ) -> bool:

        return (

            self.company_configuration(
                company_id
            )

            .get("features", {})

            .get(feature, default)

        )


# ==========================================================
# AI Provider Configuration
# ==========================================================

    def set_ai_provider(
        self,
        company_id: str,
        provider: str,
        configuration: dict[str, Any],
    ) -> None:

        company = self._companies.setdefault(
            company_id,
            {},
        )

        providers = company.setdefault(
            "ai_providers",
            {},
        )

        providers[provider] = configuration


    def ai_provider(
        self,
        company_id: str,
        provider: str,
    ) -> dict[str, Any]:

        return (

            self.company_configuration(
                company_id
            )

            .get("ai_providers", {})

            .get(provider, {})

        )


# ==========================================================
# SMTP Configuration
# ==========================================================

    def set_smtp(
        self,
        company_id: str,
        configuration: dict[str, Any],
    ) -> None:

        company = self._companies.setdefault(
            company_id,
            {},
        )

        company["smtp"] = configuration


    def smtp(
        self,
        company_id: str,
    ) -> dict[str, Any]:

        return (

            self.company_configuration(
                company_id
            )

            .get("smtp", {})

        )


# ==========================================================
# Storage Configuration
# ==========================================================

    def set_storage(
        self,
        company_id: str,
        configuration: dict[str, Any],
    ) -> None:

        company = self._companies.setdefault(
            company_id,
            {},
        )

        company["storage"] = configuration


    def storage(
        self,
        company_id: str,
    ) -> dict[str, Any]:

        return (

            self.company_configuration(
                company_id
            )

            .get("storage", {})

        )


# ==========================================================
# Tenant Secrets
# ==========================================================

    def set_company_secret(
        self,
        company_id: str,
        name: str,
        value: str,
    ) -> None:

        company = self._companies.setdefault(
            company_id,
            {},
        )

        secrets = company.setdefault(
            "secrets",
            {},
        )

        secrets[name] = self.encrypt(
            value
        )


    def company_secret(
        self,
        company_id: str,
        name: str,
    ) -> str | None:

        encrypted = (

            self.company_configuration(
                company_id
            )

            .get("secrets", {})

            .get(name)

        )

        if encrypted is None:

            return None

        return self.decrypt(
            encrypted
        )


# ==========================================================
# Tenant API Keys
# ==========================================================

    def set_api_key(
        self,
        company_id: str,
        provider: str,
        api_key: str,
    ) -> None:

        self.set_company_secret(

            company_id,

            f"{provider}_api_key",

            api_key,

        )


    def api_key(
        self,
        company_id: str,
        provider: str,
    ) -> str | None:

        return self.company_secret(

            company_id,

            f"{provider}_api_key",

        )


# ==========================================================
# Tenant Metadata
# ==========================================================

    def set_metadata(
        self,
        company_id: str,
        metadata: dict[str, Any],
    ) -> None:

        company = self._companies.setdefault(
            company_id,
            {},
        )

        company["metadata"] = metadata


    def metadata(
        self,
        company_id: str,
    ) -> dict[str, Any]:

        return (

            self.company_configuration(
                company_id
            )

            .get("metadata", {})

        )
        
        # ==========================================================
# Configuration Snapshot
# ==========================================================

    def snapshot(self) -> dict[str, Any]:

        with self._lock:

            return {
                "timestamp": self.now().isoformat(),
                "environment": self.settings.environment.value,
                "version": self.settings.version,
                "configuration": self.export(),
                "runtime": dict(self._runtime),
                "companies": dict(self._companies),
            }


# ==========================================================
# Restore Snapshot
# ==========================================================

    def restore_snapshot(
        self,
        snapshot: dict[str, Any],
    ) -> None:

        with self._lock:

            self._configuration = snapshot.get(
                "configuration",
                {},
            )

            self._runtime = snapshot.get(
                "runtime",
                {},
            )

            self._companies = snapshot.get(
                "companies",
                {},
            )

            self.save()


# ==========================================================
# Backup
# ==========================================================

    def backup(
        self,
        directory: Path | None = None,
    ) -> Path:

        directory = directory or (
            self.settings.config_directory / "backups"
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        filename = (
            f"config_{self.now():%Y%m%d_%H%M%S}.json"
        )

        path = directory / filename

        path.write_text(
            json.dumps(
                self.snapshot(),
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return path


# ==========================================================
# Restore Backup
# ==========================================================

    def restore_backup(
        self,
        backup_file: Path,
    ) -> None:

        data = json.loads(
            backup_file.read_text(
                encoding="utf-8",
            )
        )

        self.restore_snapshot(data)


# ==========================================================
# Configuration Statistics
# ==========================================================

    def statistics(self) -> dict[str, Any]:

        return {

            "configuration_keys": len(
                self._configuration
            ),

            "runtime_keys": len(
                self._runtime
            ),

            "companies": len(
                self._companies
            ),

            "last_reload": (
                self._last_loaded.isoformat()
                if self._last_loaded
                else None
            ),

            "environment": self.settings.environment.value,

            "version": self.settings.version,

        }


# ==========================================================
# Diagnostics
# ==========================================================

    def diagnostics(self) -> dict[str, Any]:

        report = {

            "healthy": True,

            "errors": [],

            "warnings": [],

            "statistics": self.statistics(),

        }

        try:

            self.validate()

        except Exception as exc:

            report["healthy"] = False

            report["errors"].append(
                str(exc)
            )

        if not self.config_path.exists():

            report["warnings"].append(
                "Configuration file does not exist."
            )

        return report


# ==========================================================
# Health Check
# ==========================================================

    def health(self) -> dict[str, Any]:

        diagnostics = self.diagnostics()

        return {

            "status": (
                "healthy"
                if diagnostics["healthy"]
                else "unhealthy"
            ),

            "checked_at": self.now().isoformat(),

            **diagnostics,

        }


# ==========================================================
# Audit Event
# ==========================================================

    def audit_event(
        self,
        action: str,
        actor: str = "system",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return {

            "timestamp": self.now().isoformat(),

            "actor": actor,

            "action": action,

            "details": details or {},

        }


# ==========================================================
# Validation Report
# ==========================================================

    def validation_report(self) -> dict[str, Any]:

        report = {

            "valid": True,

            "messages": [],

        }

        try:

            self.validate()

        except Exception as exc:

            report["valid"] = False

            report["messages"].append(
                str(exc)
            )

        return report


# ==========================================================
# Runtime Metrics
# ==========================================================

    def runtime_metrics(self) -> dict[str, Any]:

        return {

            "runtime_entries": len(
                self._runtime
            ),

            "tenant_count": len(
                self._companies
            ),

            "memory_configuration": len(
                json.dumps(
                    self._configuration
                )
            ),

            "memory_runtime": len(
                json.dumps(
                    self._runtime
                )
            ),

        }


# ==========================================================
# Maintenance
# ==========================================================

    def cleanup_runtime(self) -> None:

        with self._lock:

            self._runtime.clear()


    def clear_company_cache(
        self,
        company_id: str,
    ) -> None:

        with self._lock:

            self._companies.pop(
                company_id,
                None,
            )


    def clear_all_companies(self) -> None:

        with self._lock:

            self._companies.clear()
            
            # ==========================================================
# Context Manager
# ==========================================================

    def __enter__(self) -> "ConfigurationService":

        return self


    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:

        self.shutdown()


# ==========================================================
# Startup
# ==========================================================

    def startup(self) -> None:

        with self._lock:

            self.validate()

            self.apply_environment_overrides()

            self._last_loaded = self.now()


# ==========================================================
# Shutdown
# ==========================================================

    def shutdown(self) -> None:

        with self._lock:

            self.save()

            self.cleanup_runtime()


# ==========================================================
# Reload From Disk
# ==========================================================

    def reload_from_disk(self) -> None:

        self.reload()


# ==========================================================
# Reset Runtime
# ==========================================================

    def reset_runtime(self) -> None:

        with self._lock:

            self._runtime.clear()


# ==========================================================
# Reset Configuration
# ==========================================================

    def reset_configuration(self) -> None:

        with self._lock:

            self._configuration.clear()

            self.save()


# ==========================================================
# Company Exists
# ==========================================================

    def company_exists(
        self,
        company_id: str,
    ) -> bool:

        return company_id in self._companies


# ==========================================================
# Company List
# ==========================================================

    def companies(
        self,
    ) -> list[str]:

        return sorted(self._companies.keys())


# ==========================================================
# Remove Company
# ==========================================================

    def remove_company(
        self,
        company_id: str,
    ) -> None:

        with self._lock:

            self._companies.pop(
                company_id,
                None,
            )


# ==========================================================
# Runtime Keys
# ==========================================================

    def runtime_keys(
        self,
    ) -> list[str]:

        return sorted(self._runtime.keys())


# ==========================================================
# Configuration Keys
# ==========================================================

    def configuration_keys(
        self,
    ) -> list[str]:

        return sorted(self._configuration.keys())


# ==========================================================
# Company Count
# ==========================================================

    @property
    def company_count(
        self,
    ) -> int:

        return len(self._companies)


# ==========================================================
# Runtime Count
# ==========================================================

    @property
    def runtime_count(
        self,
    ) -> int:

        return len(self._runtime)


# ==========================================================
# Configuration Count
# ==========================================================

    @property
    def configuration_count(
        self,
    ) -> int:

        return len(self._configuration)


# ==========================================================
# Singleton
# ==========================================================

_configuration_service: ConfigurationService | None = None

_configuration_lock = threading.Lock()


def get_configuration() -> ConfigurationService:

    global _configuration_service

    if _configuration_service is None:

        with _configuration_lock:

            if _configuration_service is None:

                _configuration_service = ConfigurationService()

    return _configuration_service


def reload_configuration() -> ConfigurationService:

    configuration = get_configuration()

    configuration.reload()

    return configuration


def shutdown_configuration() -> None:

    global _configuration_service

    if _configuration_service is not None:

        _configuration_service.shutdown()

        _configuration_service = None


def configuration_health() -> dict[str, Any]:

    return get_configuration().health()


def configuration_statistics() -> dict[str, Any]:

    return get_configuration().statistics()


def configuration_snapshot() -> dict[str, Any]:

    return get_configuration().snapshot()


# ==========================================================
# FastAPI Helpers
# ==========================================================

async def startup_configuration() -> None:

    get_configuration().startup()


async def shutdown_configuration_async() -> None:

    shutdown_configuration()


# ==========================================================
# Public API
# ==========================================================

__all__ = [

    "Environment",

    "ConfigurationSettings",

    "ConfigurationService",

    "get_configuration",

    "reload_configuration",

    "shutdown_configuration",

    "startup_configuration",

    "shutdown_configuration_async",

    "configuration_health",

    "configuration_statistics",

    "configuration_snapshot",

]