from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from anthropic import (
    APIConnectionError,
    APIStatusError,
    AsyncAnthropic,
    AuthenticationError,
    RateLimitError,
)

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps.current_user import get_current_company
from config import settings
from database.database import get_db
from models.company import Company
from services.secret_service import decrypt_secret, encrypt_secret


router = APIRouter(
    prefix="/settings/ai",
    tags=["AI Settings"],
)


class AnthropicSaveRequest(BaseModel):
    api_key: str = Field(
        min_length=20,
        max_length=500,
    )


class AnthropicStatusResponse(BaseModel):
    provider: str
    configured: bool
    enabled: bool
    status: str
    masked_key: str | None = None
    last_checked_at: datetime | None = None


def _mask_key(key: str | None) -> str | None:
    if not key:
        return None

    key = key.strip()

    if len(key) <= 10:
        return "••••••••"

    return f"{key[:7]}••••••••{key[-4:]}"


def _configured_model() -> str | None:
    """
    Read the configured model if one exists.

    No obsolete hard-coded model is forced here.
    """
    value = getattr(settings, "ANTHROPIC_MODEL", None)

    if value is None:
        return None

    value = str(value).strip()

    return value or None


async def _resolve_model(
    client: AsyncAnthropic,
) -> str:
    """
    Resolve a currently available Anthropic model.

    Preference:
    1. ANTHROPIC_MODEL if that model is currently available.
    2. Current Sonnet model.
    3. Any currently available Sonnet model.
    4. Any available model supporting the Messages API.
    """

    configured = _configured_model()

    try:
        response = await client.models.list(limit=100)

        models = list(response.data)

        if not models:
            raise RuntimeError(
                "Anthropic returned no available models."
            )

        model_ids = [
            str(model.id)
            for model in models
            if getattr(model, "id", None)
        ]

        if configured and configured in model_ids:
            return configured

        preferred = "claude-sonnet-5"

        if preferred in model_ids:
            return preferred

        sonnet_models = [
            model_id
            for model_id in model_ids
            if "sonnet" in model_id.lower()
        ]

        if sonnet_models:
            return sonnet_models[0]

        return model_ids[0]

    except Exception:
        # If model listing itself isn't available, use the current
        # documented default rather than the obsolete 2024 model.
        return configured or "claude-sonnet-5"


def _extract_anthropic_error(exc: APIStatusError) -> str:
    """
    Extract Anthropic's actual error message instead of returning
    only 'HTTP 400'.
    """

    body: Any = getattr(exc, "body", None)

    if isinstance(body, dict):
        error = body.get("error")

        if isinstance(error, dict):
            message = error.get("message")

            if message:
                return str(message)

        message = body.get("message")

        if message:
            return str(message)

    text = str(exc)

    return text or f"Anthropic returned HTTP {exc.status_code}."


async def _test_anthropic(
    api_key: str,
) -> tuple[str, str]:
    """
    Validate the Anthropic API key and perform a minimal
    Messages API request.

    Returns:
        (provider_status, user_message)
    """

    client = AsyncAnthropic(
        api_key=api_key,
    )

    try:
        model = await _resolve_model(client)

        await client.messages.create(
            model=model,
            max_tokens=8,
            messages=[
                {
                    "role": "user",
                    "content": "Reply with exactly: OK",
                }
            ],
        )

        return (
            "valid",
            "Anthropic AI is connected and ready.",
        )

    except AuthenticationError:
        return (
            "invalid_api_key",
            (
                "Anthropic rejected the API key. "
                "Please verify the key in Anthropic Console."
            ),
        )

    except RateLimitError:
        return (
            "rate_limited",
            (
                "Anthropic usage quota or rate limit was reached. "
                "Please check Anthropic usage and billing."
            ),
        )

    except APIConnectionError:
        return (
            "provider_unavailable",
            (
                "Could not connect to Anthropic. "
                "Please check the connection and try again."
            ),
        )

    except APIStatusError as exc:
        provider_message = _extract_anthropic_error(exc)
        status_code = getattr(exc, "status_code", None)

        normalized_message = provider_message.lower()

        billing_markers = (
            "credit balance is too low",
            "insufficient credits",
            "purchase credits",
            "plans & billing",
            "upgrade or purchase credits",
            "billing",
        )

        if any(
            marker in normalized_message
            for marker in billing_markers
        ):
            return (
                "billing_required",
                (
                    "Anthropic AI is unavailable because your "
                    "Anthropic credit balance is too low. "
                    "Please go to Anthropic Plans & Billing and "
                    "add credits or upgrade your plan, then try again."
                ),
            )

        if status_code == 402:
            return (
                "billing_required",
                (
                    "Anthropic billing is required. "
                    "Please add funds or update your Anthropic billing."
                ),
            )

        if status_code == 403:
            return (
                "forbidden",
                (
                    "Anthropic rejected the request because the "
                    "account or API key does not have permission."
                ),
            )

        if status_code == 429:
            return (
                "rate_limited",
                (
                    "Anthropic usage quota or rate limit was reached."
                ),
            )

        if status_code == 400:
            return (
                "provider_request_error",
                (
                    "Anthropic rejected the request: "
                    f"{provider_message}"
                ),
            )

        return (
            "provider_error",
            (
                f"Anthropic returned HTTP {status_code}: "
                f"{provider_message}"
            ),
        )

    except Exception as exc:
        return (
            "provider_error",
            f"Anthropic connection test failed: {exc}",
        )


def _response(
    company: Company,
) -> AnthropicStatusResponse:

    encrypted = getattr(
        company,
        "anthropic_api_key_encrypted",
        None,
    )

    configured = bool(encrypted)

    current_status = (
        getattr(
            company,
            "anthropic_api_status",
            "not_configured",
        )
        if configured
        else "not_configured"
    )

    masked = None

    if encrypted:
        try:
            masked = _mask_key(
                decrypt_secret(encrypted)
            )
        except ValueError:
            current_status = "secret_error"

    return AnthropicStatusResponse(
        provider="anthropic",
        configured=configured,
        enabled=current_status == "valid",
        status=current_status,
        masked_key=masked,
        last_checked_at=getattr(
            company,
            "anthropic_api_last_checked_at",
            None,
        ),
    )


@router.get(
    "/anthropic",
    response_model=AnthropicStatusResponse,
)
def get_anthropic_status(
    company: Company = Depends(get_current_company),
):
    return _response(company)


@router.put(
    "/anthropic",
    response_model=AnthropicStatusResponse,
)

@router.put(
    "/anthropic",
    response_model=AnthropicStatusResponse,
)
async def save_anthropic_key(
    payload: AnthropicSaveRequest,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    api_key = payload.api_key.strip()

    if not api_key.startswith("sk-ant-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_api_key_format",
                "message": (
                    "Please enter a valid Anthropic API key "
                    "starting with sk-ant-."
                ),
            },
        )

    provider_status, provider_message = await _test_anthropic(
        api_key
    )

    now = datetime.now(timezone.utc)

    # Store the key even when Anthropic billing is currently
    # unavailable. The key itself has already been authenticated.
    company.anthropic_api_key_encrypted = encrypt_secret(
        api_key
    )
    company.anthropic_api_status = provider_status
    company.anthropic_api_last_checked_at = now

    db.add(company)
    db.commit()
    db.refresh(company)

    if provider_status == "billing_required":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "billing_required",
                "message": (
                    "Your Anthropic API key is valid, but your "
                    "Anthropic credit balance is too low. "
                    "Please add credits or upgrade your Anthropic "
                    "plan, then click Test Connection."
                ),
            },
        )

    if provider_status == "invalid_api_key":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "invalid_api_key",
                "message": provider_message,
            },
        )

    if provider_status == "rate_limited":
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limited",
                "message": provider_message,
            },
        )

    if provider_status == "forbidden":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "forbidden",
                "message": provider_message,
            },
        )

    if provider_status != "valid":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": provider_status,
                "message": provider_message,
            },
        )

    return _response(company)


@router.post(
    "/anthropic/test",
    response_model=AnthropicStatusResponse,
)
async def test_anthropic_key(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    encrypted = getattr(
        company,
        "anthropic_api_key_encrypted",
        None,
    )

    if not encrypted:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_configured",
                "message": (
                    "Anthropic API key is not configured."
                ),
            },
        )

    try:
        api_key = decrypt_secret(encrypted)
    except ValueError:
        company.anthropic_api_status = "secret_error"

        db.commit()

        raise HTTPException(
            status_code=500,
            detail={
                "code": "secret_error",
                "message": (
                    "The stored Anthropic API key "
                    "could not be decrypted."
                ),
            },
        )

    provider_status, provider_message = await _test_anthropic(
        api_key
    )

    company.anthropic_api_status = provider_status

    company.anthropic_api_last_checked_at = (
        datetime.now(timezone.utc)
    )

    db.add(company)
    db.commit()
    db.refresh(company)

    if provider_status != "valid":
        raise HTTPException(
            status_code=422,
            detail={
                "code": provider_status,
                "message": provider_message,
            },
        )

    return _response(company)
