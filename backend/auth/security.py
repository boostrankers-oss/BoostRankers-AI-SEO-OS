from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import secrets
import time
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from typing import Any

from cryptography.fernet import Fernet


# ==========================================================
# Security Configuration
# ==========================================================

@dataclass(slots=True)
class SecuritySettings:

    secret_key: str = secrets.token_urlsafe(64)

    encryption_key: bytes = Fernet.generate_key()

    request_ttl: int = 300

    max_clock_skew: int = 30

    brute_force_threshold: int = 10

    brute_force_window: int = 900

    bot_score_threshold: float = 0.80


DEFAULT_SETTINGS = SecuritySettings()


# ==========================================================
# Security Service
# ==========================================================

class SecurityService:

    def __init__(
        self,
        settings: SecuritySettings | None = None,
    ):

        self.settings = settings or DEFAULT_SETTINGS

        self.fernet = Fernet(
            self.settings.encryption_key
        )

        self.failed_attempts: dict[str, list[float]] = {}

        self.blocked_ips: set[str] = set()

        self.trusted_ips: set[str] = set()

        self.security_events: list[dict[str, Any]] = []

        self.signing_secret = (
            self.settings.secret_key.encode()
        )


# ==========================================================
# Current UTC
# ==========================================================

    @staticmethod
    def now() -> datetime:

        return datetime.now(UTC)


# ==========================================================
# Unix Timestamp
# ==========================================================

    @staticmethod
    def unix() -> int:

        return int(time.time())


# ==========================================================
# Secure Random
# ==========================================================

    @staticmethod
    def random_token(
        length: int = 32,
    ) -> str:

        return secrets.token_urlsafe(length)


# ==========================================================
# Request Signature
# ==========================================================

    def sign_request(
        self,
        payload: bytes,
        timestamp: int,
    ) -> str:

        message = payload + str(timestamp).encode()

        digest = hmac.new(
            self.signing_secret,
            message,
            hashlib.sha256,
        ).digest()

        return base64.urlsafe_b64encode(
            digest
        ).decode()


# ==========================================================
# Verify Signature
# ==========================================================

    def verify_signature(
        self,
        payload: bytes,
        timestamp: int,
        signature: str,
    ) -> bool:

        if abs(
            self.unix() - timestamp
        ) > self.settings.request_ttl:

            return False

        expected = self.sign_request(
            payload,
            timestamp,
        )

        return hmac.compare_digest(
            expected,
            signature,
        )


# ==========================================================
# Encryption
# ==========================================================

    def encrypt(
        self,
        value: str,
    ) -> str:

        return self.fernet.encrypt(
            value.encode()
        ).decode()


    def decrypt(
        self,
        value: str,
    ) -> str:

        return self.fernet.decrypt(
            value.encode()
        ).decode()


# ==========================================================
# Secure Hash
# ==========================================================

    @staticmethod
    def sha256(
        value: str,
    ) -> str:

        return hashlib.sha256(
            value.encode()
        ).hexdigest()


# ==========================================================
# Security Event
# ==========================================================

    def event(
        self,
        event_type: str,
        **details: Any,
    ) -> None:

        self.security_events.append(

            {

                "type": event_type,

                "timestamp": self.now(),

                "details": details,

            }

        )


# ==========================================================
# IP Validation
# ==========================================================

    @staticmethod
    def valid_ip(
        ip: str,
    ) -> bool:

        try:

            ipaddress.ip_address(ip)

            return True

        except ValueError:

            return False
            
            # ==========================================================
# Failed Login Tracking
# ==========================================================

    def register_failed_attempt(
        self,
        ip: str,
    ) -> None:

        now = time.time()

        attempts = self.failed_attempts.setdefault(
            ip,
            [],
        )

        attempts.append(now)

        window = self.settings.brute_force_window

        attempts[:] = [

            t

            for t in attempts

            if now - t <= window

        ]

        if len(attempts) >= self.settings.brute_force_threshold:

            self.block_ip(ip)

            self.event(

                "brute_force_detected",

                ip=ip,

                attempts=len(attempts),

            )


# ==========================================================
# Successful Login
# ==========================================================

    def register_successful_attempt(
        self,
        ip: str,
    ) -> None:

        self.failed_attempts.pop(
            ip,
            None,
        )


# ==========================================================
# Brute Force Detection
# ==========================================================

    def is_bruteforce(
        self,
        ip: str,
    ) -> bool:

        attempts = self.failed_attempts.get(
            ip,
            [],
        )

        return (

            len(attempts)

            >=

            self.settings.brute_force_threshold

        )


# ==========================================================
# Blocklist
# ==========================================================

    def block_ip(
        self,
        ip: str,
    ) -> None:

        self.blocked_ips.add(ip)

        self.event(

            "ip_blocked",

            ip=ip,

        )


    def unblock_ip(
        self,
        ip: str,
    ) -> None:

        self.blocked_ips.discard(ip)


    def is_blocked(
        self,
        ip: str,
    ) -> bool:

        return ip in self.blocked_ips


# ==========================================================
# Trusted IPs
# ==========================================================

    def trust_ip(
        self,
        ip: str,
    ) -> None:

        self.trusted_ips.add(ip)


    def untrust_ip(
        self,
        ip: str,
    ) -> None:

        self.trusted_ips.discard(ip)


    def is_trusted(
        self,
        ip: str,
    ) -> bool:

        return ip in self.trusted_ips


# ==========================================================
# CIDR Validation
# ==========================================================

    @staticmethod
    def ip_in_network(
        ip: str,
        cidr: str,
    ) -> bool:

        return (

            ipaddress.ip_address(ip)

            in

            ipaddress.ip_network(

                cidr,

                strict=False,

            )

        )


# ==========================================================
# User-Agent Inspection
# ==========================================================

    def user_agent_score(
        self,
        user_agent: str | None,
    ) -> float:

        if not user_agent:

            return 1.0

        ua = user_agent.lower()

        suspicious = (

            "curl",

            "wget",

            "python",

            "httpclient",

            "scrapy",

            "selenium",

            "phantom",

            "headless",

            "bot",

        )

        score = 0.0

        for keyword in suspicious:

            if keyword in ua:

                score += 0.15

        return min(score, 1.0)


# ==========================================================
# Bot Detection
# ==========================================================

    def is_bot(
        self,
        user_agent: str | None,
    ) -> bool:

        return (

            self.user_agent_score(user_agent)

            >=

            self.settings.bot_score_threshold

        )


# ==========================================================
# Request Risk Score
# ==========================================================

    def request_risk_score(
        self,
        ip: str,
        user_agent: str | None,
    ) -> float:

        score = 0.0

        if self.is_blocked(ip):

            score += 0.60

        if self.is_bruteforce(ip):

            score += 0.30

        score += self.user_agent_score(

            user_agent

        )

        return min(score, 1.0)


# ==========================================================
# High Risk Request
# ==========================================================

    def high_risk_request(
        self,
        ip: str,
        user_agent: str | None,
    ) -> bool:

        return (

            self.request_risk_score(

                ip,

                user_agent,

            )

            >=

            0.80

        )


# ==========================================================
# Security Incident
# ==========================================================

    def incident(
        self,
        ip: str,
        reason: str,
        **metadata: Any,
    ) -> None:

        self.event(

            "security_incident",

            ip=ip,

            reason=reason,

            **metadata,

        )
        
        # ==========================================================
# SQL Injection Detection
# ==========================================================

    SQLI_PATTERNS = (

        "union select",
        "select * from",
        "drop table",
        "insert into",
        "delete from",
        "update ",
        "truncate",
        "--",
        "/*",
        "*/",
        "xp_cmdshell",
        "information_schema",
        "sleep(",
        "benchmark(",
        "or 1=1",
        "' or '",
        "\" or \"",
    )

    def detect_sql_injection(
        self,
        value: str,
    ) -> bool:

        text = value.lower()

        return any(

            pattern in text

            for pattern in self.SQLI_PATTERNS

        )


# ==========================================================
# Cross Site Scripting
# ==========================================================

    XSS_PATTERNS = (

        "<script",

        "</script>",

        "javascript:",

        "onerror=",

        "onload=",

        "onclick=",

        "onmouseover=",

        "document.cookie",

        "window.location",

        "alert(",

        "<iframe",

        "<svg",

        "<img",

    )

    def detect_xss(
        self,
        value: str,
    ) -> bool:

        text = value.lower()

        return any(

            pattern in text

            for pattern in self.XSS_PATTERNS

        )


# ==========================================================
# Command Injection
# ==========================================================

    COMMAND_PATTERNS = (

        "&&",

        "||",

        ";",

        "|",

        "`",

        "$(",

        "curl ",

        "wget ",

        "powershell",

        "cmd.exe",

        "/bin/bash",

        "/bin/sh",

        "nc ",

        "netcat",

    )

    def detect_command_injection(
        self,
        value: str,
    ) -> bool:

        text = value.lower()

        return any(

            pattern in text

            for pattern in self.COMMAND_PATTERNS

        )


# ==========================================================
# Path Traversal
# ==========================================================

    PATH_PATTERNS = (

        "../",

        "..\\",

        "%2e%2e",

        "/etc/passwd",

        "\\windows\\",

        "system32",

        "/proc/",

        "/root/",

    )

    def detect_path_traversal(
        self,
        value: str,
    ) -> bool:

        text = value.lower()

        return any(

            pattern in text

            for pattern in self.PATH_PATTERNS

        )


# ==========================================================
# SSRF Detection
# ==========================================================

    SSRF_PATTERNS = (

        "127.0.0.1",

        "localhost",

        "0.0.0.0",

        "::1",

        "169.254.",

        "metadata.google",

        "metadata.azure",

        "metadata.aws",

        "file://",

        "gopher://",

        "ftp://",

    )

    def detect_ssrf(
        self,
        value: str,
    ) -> bool:

        text = value.lower()

        return any(

            pattern in text

            for pattern in self.SSRF_PATTERNS

        )


# ==========================================================
# Secret Leakage Detection
# ==========================================================

    SECRET_PATTERNS = (

        "sk-",

        "ghp_",

        "gho_",

        "aws_access_key",

        "aws_secret_access_key",

        "private_key",

        "-----begin",

        "bearer ",

        "authorization:",

        "api_key",

        "secret_key",

    )

    def detect_secret(
        self,
        value: str,
    ) -> bool:

        text = value.lower()

        return any(

            pattern in text

            for pattern in self.SECRET_PATTERNS

        )


# ==========================================================
# Dangerous File Upload
# ==========================================================

    DANGEROUS_EXTENSIONS = {

        ".php",

        ".exe",

        ".dll",

        ".bat",

        ".cmd",

        ".sh",

        ".ps1",

        ".jar",

        ".com",

        ".scr",

        ".msi",

    }

    def dangerous_upload(
        self,
        filename: str,
    ) -> bool:

        filename = filename.lower()

        return any(

            filename.endswith(ext)

            for ext in self.DANGEROUS_EXTENSIONS

        )


# ==========================================================
# Payload Analysis
# ==========================================================

    def analyse_payload(
        self,
        payload: str,
    ) -> dict[str, bool]:

        return {

            "sql_injection":

                self.detect_sql_injection(payload),

            "xss":

                self.detect_xss(payload),

            "command_injection":

                self.detect_command_injection(payload),

            "path_traversal":

                self.detect_path_traversal(payload),

            "ssrf":

                self.detect_ssrf(payload),

            "secret":

                self.detect_secret(payload),

        }


# ==========================================================
# Threat Score
# ==========================================================

    def threat_score(
        self,
        payload: str,
    ) -> float:

        analysis = self.analyse_payload(

            payload

        )

        score = (

            sum(

                analysis.values()

            )

            /

            len(analysis)

        )

        return round(

            score,

            2,

        )


# ==========================================================
# Malicious Payload
# ==========================================================

    def malicious_payload(
        self,
        payload: str,
    ) -> bool:

        return (

            self.threat_score(

                payload

            )

            >=

            0.30

        )


# ==========================================================
# API Abuse Detection
# ==========================================================

    def api_abuse(
        self,
        payload: str,
        user_agent: str | None = None,
    ) -> bool:

        if self.malicious_payload(

            payload

        ):

            return True

        if self.is_bot(

            user_agent

        ):

            return True

        return False
        
        # ==========================================================
# IP Reputation
# ==========================================================

    def ip_reputation(
        self,
        ip: str,
    ) -> dict[str, Any]:

        reputation = 100

        if self.is_blocked(ip):
            reputation -= 80

        if self.is_bruteforce(ip):
            reputation -= 40

        if self.is_trusted(ip):
            reputation += 20

        reputation = max(0, min(100, reputation))

        return {

            "ip": ip,

            "score": reputation,

            "trusted": self.is_trusted(ip),

            "blocked": self.is_blocked(ip),

        }


# ==========================================================
# Geographic Risk
# ==========================================================

    def geo_risk(
        self,
        country: str | None,
    ) -> float:

        if not country:

            return 0.50

        high_risk = {

            "unknown",

            "anonymous",

            "tor",

        }

        if country.lower() in high_risk:

            return 0.90

        return 0.10


# ==========================================================
# Device Fingerprint
# ==========================================================

    def device_fingerprint(
        self,
        ip: str,
        user_agent: str,
    ) -> str:

        return hashlib.sha256(

            f"{ip}:{user_agent}".encode()

        ).hexdigest()


# ==========================================================
# Device Risk
# ==========================================================

    def device_risk(
        self,
        fingerprint: str,
        known_devices: set[str],
    ) -> float:

        if fingerprint in known_devices:

            return 0.05

        return 0.70


# ==========================================================
# Session Hijacking Detection
# ==========================================================

    def detect_session_hijack(
        self,
        previous_ip: str,
        current_ip: str,
        previous_agent: str,
        current_agent: str,
    ) -> bool:

        if previous_ip != current_ip:

            return True

        if previous_agent != current_agent:

            return True

        return False


# ==========================================================
# Behaviour Analysis
# ==========================================================

    def behaviour_score(
        self,
        requests_per_minute: int,
        failed_logins: int,
    ) -> float:

        score = 0.0

        if requests_per_minute > 100:

            score += 0.40

        elif requests_per_minute > 50:

            score += 0.20

        score += min(

            failed_logins * 0.05,

            0.50,

        )

        return min(score, 1.0)


# ==========================================================
# Request Correlation
# ==========================================================

    def correlate_request(
        self,
        request_id: str,
        user_id: str | None,
        ip: str,
    ) -> dict[str, Any]:

        return {

            "request_id": request_id,

            "user_id": user_id,

            "ip": ip,

            "timestamp": self.now(),

        }


# ==========================================================
# Threat Intelligence Hook
# ==========================================================

    def threat_intelligence(
        self,
        ip: str,
    ) -> dict[str, Any]:

        return {

            "ip": ip,

            "known_malicious": self.is_blocked(ip),

            "confidence": 1.0 if self.is_blocked(ip) else 0.0,

            "source": "internal",

        }


# ==========================================================
# Security Alert
# ==========================================================

    def alert(
        self,
        severity: str,
        message: str,
        **details: Any,
    ) -> None:

        self.event(

            "security_alert",

            severity=severity,

            message=message,

            **details,

        )


# ==========================================================
# Automatic Response
# ==========================================================

    def automatic_response(
        self,
        ip: str,
        risk_score: float,
    ) -> str:

        if risk_score >= 0.90:

            self.block_ip(ip)

            return "blocked"

        if risk_score >= 0.70:

            return "challenge"

        if risk_score >= 0.40:

            return "monitor"

        return "allow"


# ==========================================================
# Security Dashboard
# ==========================================================

    def dashboard(
        self,
    ) -> dict[str, Any]:

        return {

            "blocked_ips": len(self.blocked_ips),

            "trusted_ips": len(self.trusted_ips),

            "failed_login_sources": len(self.failed_attempts),

            "security_events": len(self.security_events),

            "high_risk_ips": sum(

                1

                for ip in self.blocked_ips

                if self.is_blocked(ip)

            ),

        }


# ==========================================================
# Security Summary
# ==========================================================

    def summary(
        self,
    ) -> dict[str, Any]:

        return {

            "dashboard": self.dashboard(),

            "events": len(self.security_events),

            "blocked": len(self.blocked_ips),

            "trusted": len(self.trusted_ips),

            "timestamp": self.now(),

        }
        
        # ==========================================================
# Health
# ==========================================================

    def health(
        self,
    ) -> dict[str, Any]:

        return {

            "service": "SecurityService",

            "status": "healthy",

            "blocked_ips": len(self.blocked_ips),

            "trusted_ips": len(self.trusted_ips),

            "failed_attempt_sources": len(self.failed_attempts),

            "security_events": len(self.security_events),

        }


# ==========================================================
# Statistics
# ==========================================================

    def statistics(
        self,
    ) -> dict[str, Any]:

        return {

            "blocked_ips": len(self.blocked_ips),

            "trusted_ips": len(self.trusted_ips),

            "failed_attempts": sum(

                len(v)

                for v in self.failed_attempts.values()

            ),

            "security_events": len(

                self.security_events

            ),

        }


# ==========================================================
# Security Report
# ==========================================================

    def security_report(
        self,
    ) -> dict[str, Any]:

        return {

            "request_signing": True,

            "fernet_encryption": True,

            "brute_force_protection": True,

            "bot_detection": True,

            "sql_injection_detection": True,

            "xss_detection": True,

            "command_injection_detection": True,

            "path_traversal_detection": True,

            "ssrf_detection": True,

            "secret_detection": True,

            "device_fingerprinting": True,

            "ip_reputation": True,

            "automatic_response": True,

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

            "dashboard":

                self.dashboard(),

            "summary":

                self.summary(),

            "security":

                self.security_report(),

        }


# ==========================================================
# Cleanup
# ==========================================================

    def cleanup(
        self,
    ) -> dict[str, Any]:

        now = time.time()

        window = self.settings.brute_force_window

        removed = 0

        for ip in list(self.failed_attempts.keys()):

            attempts = [

                t

                for t in self.failed_attempts[ip]

                if now - t <= window

            ]

            if attempts:

                self.failed_attempts[ip] = attempts

            else:

                del self.failed_attempts[ip]

                removed += 1

        return {

            "expired_entries_removed": removed,

            "remaining_sources": len(

                self.failed_attempts

            ),

        }


# ==========================================================
# Maintenance
# ==========================================================

    def maintenance(
        self,
    ) -> dict[str, Any]:

        cleanup = self.cleanup()

        return {

            "cleanup": cleanup,

            "status": "completed",

            "timestamp": self.now(),

        }


# ==========================================================
# Configuration Validation
# ==========================================================

def validate_security_settings(
    settings: SecuritySettings,
) -> bool:

    if settings.request_ttl <= 0:

        raise ValueError(

            "request_ttl must be positive."

        )

    if settings.brute_force_threshold <= 0:

        raise ValueError(

            "Invalid brute force threshold."

        )

    if settings.brute_force_window <= 0:

        raise ValueError(

            "Invalid brute force window."

        )

    if not settings.secret_key:

        raise ValueError(

            "secret_key is required."

        )

    return True


# ==========================================================
# Singleton
# ==========================================================

_security_service: SecurityService | None = None


def initialize_security(
    settings: SecuritySettings | None = None,
) -> SecurityService:

    global _security_service

    if settings:

        validate_security_settings(

            settings

        )

    _security_service = SecurityService(

        settings=settings,

    )

    return _security_service


def get_security_service(
) -> SecurityService:

    if _security_service is None:

        raise RuntimeError(

            "SecurityService has not been initialized."

        )

    return _security_service


# ==========================================================
# Helper Functions
# ==========================================================

def security_health() -> dict[str, Any]:

    return get_security_service().health()


def security_statistics() -> dict[str, Any]:

    return get_security_service().statistics()


def security_report() -> dict[str, Any]:

    return get_security_service().security_report()


def security_diagnostics() -> dict[str, Any]:

    return get_security_service().diagnostics()


def security_maintenance() -> dict[str, Any]:

    return get_security_service().maintenance()


# ==========================================================
# Public Exports
# ==========================================================

__all__ = [

    "SecuritySettings",

    "SecurityService",

    "initialize_security",

    "get_security_service",

    "validate_security_settings",

    "security_health",

    "security_statistics",

    "security_report",

    "security_diagnostics",

    "security_maintenance",

]