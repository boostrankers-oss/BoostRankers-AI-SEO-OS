from __future__ import annotations

import os
from datetime import date
from typing import Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps.current_user import get_current_user
from database.session import get_db
from models.google_integration import GoogleIntegration
from models.user import User
from services.google_integration_service import (
    PROVIDER_CONFIG,
    analytics_performance,
    build_authorization_url,
    exchange_code,
    get_connection,
    list_analytics_properties,
    list_search_console_properties,
    revoke_connection,
    save_connection,
    search_console_performance,
    _verify_state,
)


Provider = Literal["search_console", "analytics"]

router = APIRouter(
    prefix="/google",
    tags=["Google Integration"],
)


class PropertySelection(BaseModel):
    property: str


def _company_id(current_user: User) -> str:
    company_id = getattr(current_user, "company_id", None)
    if not company_id:
        raise HTTPException(status_code=403, detail="A company account is required for Google integrations.")
    return str(company_id)


@router.get("/status")
def get_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company_id = _company_id(current_user)
    result = {}

    for provider in PROVIDER_CONFIG:
        connection = get_connection(db, company_id, provider)
        result[provider] = {
            "connected": connection is not None,
            "account_email": connection.account_email if connection else None,
            "selected_property": connection.selected_property if connection else None,
            "updated_at": connection.updated_at.isoformat() if connection and connection.updated_at else None,
        }

    return result


@router.get("/connect/{provider}")
def connect_google(
    provider: Provider,
    current_user: User = Depends(get_current_user),
):
    company_id = _company_id(current_user)
    return {
        "provider": provider,
        "authorization_url": build_authorization_url(
            user_id=str(current_user.id),
            company_id=company_id,
            provider=provider,
        ),
    }


@router.get("/oauth/callback")
async def oauth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").strip().rstrip("/")

    if error:
        query = urlencode(
            {
                "google": "error",
                "error": error_description or error,
            }
        )
        return RedirectResponse(url=f"{frontend_url}/?{query}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing Google OAuth code or state.")

    payload = _verify_state(state)
    provider = payload["provider"]

    if payload.get("exp") is None:
        raise HTTPException(status_code=400, detail="Invalid Google OAuth state.")

    token = await exchange_code(code)
    await save_connection(
        db,
        user_id=str(payload["sub"]),
        company_id=str(payload["company_id"]),
        provider=provider,
        token=token,
    )

    query = urlencode(
        {
            "google": "connected",
            "provider": provider,
        }
    )
    return RedirectResponse(url=f"{frontend_url}/?{query}")


@router.delete("/disconnect/{provider}")
async def disconnect_google(
    provider: Provider,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company_id = _company_id(current_user)
    connection = get_connection(db, company_id, provider)
    if connection is None:
        return {"status": "disconnected", "provider": provider}

    await revoke_connection(db, connection)
    return {"status": "disconnected", "provider": provider}


@router.get("/properties/search-console")
async def search_console_properties(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company_id = _company_id(current_user)
    connection = get_connection(db, company_id, "search_console")
    if connection is None:
        raise HTTPException(status_code=409, detail="Connect Google Search Console first.")
    return {"items": await list_search_console_properties(connection, db)}


@router.get("/properties/analytics")
async def analytics_properties(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company_id = _company_id(current_user)
    connection = get_connection(db, company_id, "analytics")
    if connection is None:
        raise HTTPException(status_code=409, detail="Connect Google Analytics first.")
    return {"items": await list_analytics_properties(connection, db)}


@router.post("/select-property/{provider}")
def select_property(
    provider: Provider,
    payload: PropertySelection,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    company_id = _company_id(current_user)
    connection = get_connection(db, company_id, provider)
    if connection is None:
        raise HTTPException(status_code=409, detail=f"Connect {PROVIDER_CONFIG[provider]['label']} first.")

    if not payload.property.strip():
        raise HTTPException(status_code=422, detail="Property is required.")

    connection.selected_property = payload.property.strip()
    db.add(connection)
    db.commit()
    db.refresh(connection)

    return {"status": "saved", "provider": provider, "property": connection.selected_property}


@router.get("/search-console/performance")
async def search_console_report(
    site_url: str = Query(min_length=1),
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="End date must be on or after start date.")

    company_id = _company_id(current_user)
    connection = get_connection(db, company_id, "search_console")
    if connection is None:
        raise HTTPException(status_code=409, detail="Connect Google Search Console first.")

    return await search_console_performance(
        connection,
        db,
        site_url=site_url,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )


@router.get("/analytics/performance")
async def analytics_report(
    property_id: str = Query(min_length=1),
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="End date must be on or after start date.")

    company_id = _company_id(current_user)
    connection = get_connection(db, company_id, "analytics")
    if connection is None:
        raise HTTPException(status_code=409, detail="Connect Google Analytics first.")

    return await analytics_performance(
        connection,
        db,
        property_id=property_id,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )
