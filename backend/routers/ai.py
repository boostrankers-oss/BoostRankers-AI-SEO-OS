from __future__ import annotations

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
from config import settings
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
    model = getattr(settings, "ANTHROPIC_MODEL", None)

    if model:
        return str(model).strip()

    return "claude-sonnet-4-20250514"


@router.post("/generate")
async def generate_content(
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
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
        api_key = decrypt_secret(encrypted_key)
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "secret_decryption_failed",
                "message": (
                    "The stored Anthropic API key could not be decrypted."
                ),
            },
        )

    client = AsyncAnthropic(
        api_key=api_key,
    )

    try:
        response = await client.messages.create(
            model=_get_model(),
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
                text_parts.append(block.text)

        return {
            "content": "\n".join(text_parts).strip(),
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
