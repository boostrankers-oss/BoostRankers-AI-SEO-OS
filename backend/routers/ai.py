from __future__ import annotations

import os

from anthropic import (
    APIConnectionError,
    APIStatusError,
    AsyncAnthropic,
    AuthenticationError,
    RateLimitError,
)
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps.current_user import get_current_company
from database.database import get_db
from models.company import Company
from services.secret_service import decrypt_secret


router = APIRouter(
    prefix="/ai",
    tags=["AI"],
)


class GenerateRequest(BaseModel):
    prompt: str = Field(
        min_length=1,
        max_length=50000,
    )


def _get_model() -> str:
    """
    Resolve the Anthropic model from the environment.

    Uses ANTHROPIC_MODEL when configured, otherwise falls back
    to the current Claude Sonnet model.
    """
    model = os.getenv("ANTHROPIC_MODEL", "").strip()

    return model or "claude-sonnet-4-6"


@router.post("/generate")
async def generate_content(
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    """
    Generate AI content using the company's encrypted Anthropic API key.
    """

    encrypted_key = getattr(
        company,
        "anthropic_api_key_encrypted",
        None,
    )

    if not encrypted_key:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "not_configured",
                "message": (
                    "Anthropic API key is not configured. "
                    "Please add it in Settings."
                ),
            },
        )

    try:
        api_key = decrypt_secret(
            str(encrypted_key).strip()
        ).strip()

    except (ValueError, TypeError):
        raise HTTPException(
            status_code=500,
            detail={
                "code": "secret_decryption_failed",
                "message": (
                    "The stored Anthropic API key could not be decrypted."
                ),
            },
        )

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "empty_api_key",
                "message": (
                    "The stored Anthropic API key is empty. "
                    "Please update it in Settings."
                ),
            },
        )

    model = _get_model()

    client = AsyncAnthropic(
        api_key=api_key,
    )

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": payload.prompt,
                }
            ],
        )

        text_parts: list[str] = []

        for block in response.content:
            if getattr(block, "type", None) == "text":
                text = getattr(block, "text", None)

                if text:
                    text_parts.append(str(text))

        content = "\n".join(text_parts).strip()

        if not content:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "empty_provider_response",
                    "message": (
                        "Anthropic returned an empty response."
                    ),
                },
            )

        return {
            "content": content,
        }

    except AuthenticationError:
        company.anthropic_api_status = "invalid_api_key"
        db.commit()

        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_api_key",
                "message": (
                    "Anthropic rejected the API key. "
                    "Please update the key in Settings."
                ),
            },
        )

    except RateLimitError:
        company.anthropic_api_status = "rate_limited"
        db.commit()

        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "message": (
                    "Anthropic usage quota or rate limit was reached. "
                    "Please check your Anthropic usage and billing."
                ),
            },
        )

    except APIConnectionError:
        company.anthropic_api_status = "provider_unavailable"
        db.commit()

        raise HTTPException(
            status_code=502,
            detail={
                "code": "provider_unavailable",
                "message": (
                    "Anthropic is currently unavailable. "
                    "Please try again later."
                ),
            },
        )

    except APIStatusError as exc:
        status_code = getattr(exc, "status_code", None)

        if status_code == 402:
            company.anthropic_api_status = "billing_required"
            db.commit()

            raise HTTPException(
                status_code=402,
                detail={
                    "code": "billing_required",
                    "message": (
                        "Anthropic billing is required. "
                        "Please add funds or update your Anthropic billing "
                        "and try again."
                    ),
                },
            )

        if status_code == 403:
            company.anthropic_api_status = "forbidden"
            db.commit()

            raise HTTPException(
                status_code=403,
                detail={
                    "code": "forbidden",
                    "message": (
                        "Anthropic rejected this API request. "
                        "Check the API key and account permissions."
                    ),
                },
            )

        if status_code == 404:
            company.anthropic_api_status = "provider_error"
            db.commit()

            raise HTTPException(
                status_code=502,
                detail={
                    "code": "model_not_found",
                    "message": (
                        f"The configured Anthropic model '{model}' "
                        "is unavailable. Please update ANTHROPIC_MODEL."
                    ),
                },
            )

        company.anthropic_api_status = "provider_error"
        db.commit()

        raise HTTPException(
            status_code=502,
            detail={
                "code": "provider_error",
                "message": (
                    "Anthropic returned an unexpected provider error."
                ),
            },
        )

    except HTTPException:
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail={
                "code": "ai_generation_failed",
                "message": (
                    "The AI request could not be completed."
                ),
            },
        )