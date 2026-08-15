from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from config import settings


def _fernet() -> Fernet:
    secret = str(settings.SECRET_KEY).encode("utf-8")

    digest = hashlib.sha256(secret).digest()

    key = base64.urlsafe_b64encode(digest)

    return Fernet(key)


def encrypt_secret(value: str) -> str:
    value = value.strip()

    if not value:
        raise ValueError("Secret value cannot be empty.")

    return _fernet().encrypt(
        value.encode("utf-8")
    ).decode("utf-8")


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(
            value.encode("utf-8")
        ).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Stored secret could not be decrypted."
        ) from exc