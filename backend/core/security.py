"""
Production Security Utilities
Boost Rankers AI SEO OS

Features
--------
- Password hashing
- Password verification
- JWT secret helpers
- Secure token generation
- API key generation
- Email verification token
- Password reset token
- Password strength validation
- Constant-time comparison
"""

from __future__ import annotations

import hmac
import re
import secrets
import string
from dataclasses import dataclass

from passlib.context import CryptContext


# ------------------------------------------------------------------
# Password Hashing
# ------------------------------------------------------------------

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt.
    """
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verify password.
    """
    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


# ------------------------------------------------------------------
# Secure Token Generation
# ------------------------------------------------------------------

def generate_secure_token(length: int = 64) -> str:
    """
    Cryptographically secure random token.
    """
    return secrets.token_urlsafe(length)


def generate_email_verification_token() -> str:
    return generate_secure_token(48)


def generate_password_reset_token() -> str:
    return generate_secure_token(48)


# ------------------------------------------------------------------
# API Keys
# ------------------------------------------------------------------

def generate_api_key(prefix: str = "br") -> str:
    """
    Example:

    br_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    """

    return (
        f"{prefix}_"
        f"{secrets.token_urlsafe(32)}"
    )


# ------------------------------------------------------------------
# Password Strength
# ------------------------------------------------------------------

@dataclass(slots=True)
class PasswordValidationResult:
    valid: bool
    score: int
    message: str


PASSWORD_REGEX = {
    "uppercase": r"[A-Z]",
    "lowercase": r"[a-z]",
    "digit": r"[0-9]",
    "special": r"[!@#$%^&*(),.?\":{}|<>_\-+=/\\[\]]",
}


def validate_password_strength(
    password: str,
) -> PasswordValidationResult:
    """
    Returns a score from 0–5.
    """

    score = 0

    if len(password) >= 12:
        score += 1

    if re.search(PASSWORD_REGEX["uppercase"], password):
        score += 1

    if re.search(PASSWORD_REGEX["lowercase"], password):
        score += 1

    if re.search(PASSWORD_REGEX["digit"], password):
        score += 1

    if re.search(PASSWORD_REGEX["special"], password):
        score += 1

    if score < 5:
        return PasswordValidationResult(
            valid=False,
            score=score,
            message=(
                "Password must contain at least "
                "12 characters, uppercase, lowercase, "
                "number and special character."
            ),
        )

    return PasswordValidationResult(
        valid=True,
        score=score,
        message="Strong password",
    )


# ------------------------------------------------------------------
# Constant Time Comparison
# ------------------------------------------------------------------

def constant_time_compare(
    value1: str,
    value2: str,
) -> bool:
    """
    Prevent timing attacks.
    """
    return hmac.compare_digest(
        value1,
        value2,
    )


# ------------------------------------------------------------------
# Random Password
# ------------------------------------------------------------------

def generate_random_password(
    length: int = 16,
) -> str:

    alphabet = (
        string.ascii_letters
        + string.digits
        + "!@#$%^&*()"
    )

    while True:
        password = "".join(
            secrets.choice(alphabet)
            for _ in range(length)
        )

        if validate_password_strength(password).valid:
            return password


# ------------------------------------------------------------------
# OTP
# ------------------------------------------------------------------

def generate_otp(
    digits: int = 6,
) -> str:
    """
    Numeric OTP.
    """

    return "".join(
        secrets.choice(string.digits)
        for _ in range(digits)
    )


# ------------------------------------------------------------------
# Session Identifier
# ------------------------------------------------------------------

def generate_session_id() -> str:
    return secrets.token_hex(32)


# ------------------------------------------------------------------
# Invite Token
# ------------------------------------------------------------------

def generate_invitation_token() -> str:
    return generate_secure_token(48)


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------

def mask_email(email: str) -> str:
    """
    john@example.com

    j***@example.com
    """

    name, domain = email.split("@")

    if len(name) <= 2:
        return "*" * len(name) + "@" + domain

    return (
        name[0]
        + "***@"
        + domain
    )