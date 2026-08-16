from __future__ import annotations

import base64
import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from models.google_integration import GoogleIntegration


# ============================================================
# Environment
# ============================================================

# Local development:
# Load the project-root .env explicitly.
#
# Production:
# Render provides environment variables directly, so this call
# simply leaves those values intact.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GSC_SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"
GSC_SEARCH_ANALYTICS_URL = "https://www.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query"
GA_ACCOUNT_SUMMARIES_URL = "https://analyticsadmin.googleapis.com/v1beta/accountSummaries"
GA_RUN_REPORT_URL = "https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"

PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "search_console": {
        "label": "Google Search Console",
        "scopes": [
            "openid",
            "email",
            "https://www.googleapis.com/auth/webmasters.readonly",
        ],
    },
    "analytics": {
        "label": "Google Analytics 4",
        "scopes": [
            "openid",
            "email",
            "https://www.googleapis.com/auth/analytics.readonly",
        ],
    },
}


def _settings() -> dict[str, str]:
    return {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "").strip(),
        "redirect_uri": os.getenv(
            "GOOGLE_OAUTH_REDIRECT_URI",
            "http://localhost:8000/api/google/oauth/callback",
        ).strip(),
        "secret_key": os.getenv("SECRET_KEY", "").strip(),
        "algorithm": os.getenv("ALGORITHM", "HS256").strip() or "HS256",
        "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:5173")
        .strip()
        .rstrip("/"),
    }


def _require_google_config() -> dict[str, str]:
    config = _settings()
    missing = [
        key
        for key in ("client_id", "client_secret", "secret_key")
        if not config[key]
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on the backend.",
        )
    return config


def _fernet_key() -> bytes:
    secret = _settings()["secret_key"].encode("utf-8")
    digest = hashlib.sha256(secret).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_token(value: str) -> str:
    from cryptography.fernet import Fernet

    return Fernet(_fernet_key()).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_token(value: str) -> str:
    from cryptography.fernet import Fernet, InvalidToken

    try:
        return Fernet(_fernet_key()).decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored Google credentials cannot be decrypted. Reconnect Google.",
        ) from exc


def _sign_state(*, user_id: str, company_id: str, provider: str) -> str:
    config = _require_google_config()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "company_id": company_id,
        "provider": provider,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "nonce": base64.urlsafe_b64encode(os.urandom(24)).decode("ascii").rstrip("="),
    }
    return jwt.encode(payload, config["secret_key"], algorithm=config["algorithm"])


def _verify_state(state: str) -> dict[str, Any]:
    config = _require_google_config()
    try:
        payload = jwt.decode(
            state,
            config["secret_key"],
            algorithms=[config["algorithm"]],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired Google OAuth state.",
        ) from exc

    provider = payload.get("provider")
    if provider not in PROVIDER_CONFIG:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Google OAuth provider.",
        )

    return payload


def build_authorization_url(*, user_id: str, company_id: str, provider: str) -> str:
    config = _require_google_config()
    provider_config = PROVIDER_CONFIG.get(provider)
    if not provider_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported Google provider.",
        )

    state = _sign_state(
        user_id=user_id,
        company_id=company_id,
        provider=provider,
    )

    query = urlencode(
        {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "scope": " ".join(provider_config["scopes"]),
            "state": state,
        }
    )
    return f"{GOOGLE_AUTH_URL}?{query}"


async def exchange_code(code: str) -> dict[str, Any]:
    config = _require_google_config()

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "redirect_uri": config["redirect_uri"],
                "grant_type": "authorization_code",
            },
        )

    if response.status_code >= 400:
        detail = "Google OAuth token exchange failed."
        try:
            detail = response.json().get("error_description") or response.json().get("error") or detail
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    return response.json()


async def refresh_access_token(connection: GoogleIntegration, db: Session) -> str:
    refresh_token = decrypt_token(connection.refresh_token_encrypted)
    config = _require_google_config()

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

    if response.status_code >= 400:
        detail = "Google authorization has expired or been revoked. Please reconnect."
        try:
            body = response.json()
            if body.get("error") == "invalid_grant":
                detail = "Google authorization has expired or been revoked. Please reconnect."
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

    token = response.json()
    connection.access_token_encrypted = encrypt_token(token["access_token"])
    connection.expires_at = datetime.now(UTC) + timedelta(seconds=int(token.get("expires_in", 3600)))
    connection.token_type = token.get("token_type", connection.token_type or "Bearer")
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return token["access_token"]


async def get_access_token(connection: GoogleIntegration, db: Session) -> str:
    if not connection.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google connection is disabled.")

    if connection.expires_at is None or connection.expires_at <= datetime.now(UTC) + timedelta(minutes=1):
        return await refresh_access_token(connection, db)

    return decrypt_token(connection.access_token_encrypted)


async def _google_get(
    url: str,
    access_token: str,
    db: Session,
    connection: GoogleIntegration,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )

    if response.status_code == 401:
        access_token = await refresh_access_token(connection, db)
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )

    if response.status_code >= 400:
        detail = "Google API request failed."
        try:
            body = response.json()
            detail = body.get("error", {}).get("message") or detail
        except Exception:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)

    return response.json()


async def _google_post(
    url: str,
    access_token: str,
    body: dict[str, Any],
    db: Session,
    connection: GoogleIntegration,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )

    if response.status_code == 401:
        access_token = await refresh_access_token(connection, db)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json=body,
            )

    if response.status_code >= 400:
        detail = "Google API request failed."
        try:
            payload = response.json()
            detail = payload.get("error", {}).get("message") or detail
        except Exception:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)

    return response.json()


async def get_userinfo(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if response.status_code >= 400:
        return {}
    return response.json()


async def save_connection(
    db: Session,
    *,
    user_id: str,
    company_id: str,
    provider: str,
    token: dict[str, Any],
) -> GoogleIntegration:
    access_token = token.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Google did not return an access token.")

    existing = (
        db.query(GoogleIntegration)
        .filter(
            GoogleIntegration.company_id == company_id,
            GoogleIntegration.provider == provider,
        )
        .first()
    )

    userinfo = await get_userinfo(access_token)
    refresh_token = token.get("refresh_token")

    if existing is None and not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Google did not return a refresh token. Reconnect and approve offline access.",
        )

    if existing is None:
        existing = GoogleIntegration(
            company_id=company_id,
            user_id=user_id,
            provider=provider,
            access_token_encrypted=encrypt_token(access_token),
            refresh_token_encrypted=encrypt_token(refresh_token),
            token_type=token.get("token_type", "Bearer"),
            scope=token.get("scope"),
            expires_at=datetime.now(UTC) + timedelta(seconds=int(token.get("expires_in", 3600))),
            account_email=userinfo.get("email"),
            is_active=True,
        )
        db.add(existing)
    else:
        existing.user_id = user_id
        existing.access_token_encrypted = encrypt_token(access_token)
        if refresh_token:
            existing.refresh_token_encrypted = encrypt_token(refresh_token)
        existing.token_type = token.get("token_type", existing.token_type or "Bearer")
        existing.scope = token.get("scope") or existing.scope
        existing.expires_at = datetime.now(UTC) + timedelta(seconds=int(token.get("expires_in", 3600)))
        existing.account_email = userinfo.get("email") or existing.account_email
        existing.is_active = True
        db.add(existing)

    db.commit()
    db.refresh(existing)
    return existing


def get_connection(db: Session, company_id: str, provider: str) -> GoogleIntegration | None:
    return (
        db.query(GoogleIntegration)
        .filter(
            GoogleIntegration.company_id == company_id,
            GoogleIntegration.provider == provider,
            GoogleIntegration.is_active.is_(True),
        )
        .first()
    )


async def list_search_console_properties(connection: GoogleIntegration, db: Session) -> list[dict[str, Any]]:
    token = await get_access_token(connection, db)
    payload = await _google_get(GSC_SITES_URL, token, db, connection)
    return [
        {
            "id": item.get("siteUrl"),
            "name": item.get("siteUrl"),
            "permission_level": item.get("permissionLevel"),
        }
        for item in payload.get("siteEntry", [])
        if item.get("siteUrl")
    ]


async def list_analytics_properties(connection: GoogleIntegration, db: Session) -> list[dict[str, Any]]:
    token = await get_access_token(connection, db)
    items: list[dict[str, Any]] = []
    page_token: str | None = None

    while True:
        params: dict[str, Any] = {"pageSize": 200}
        if page_token:
            params["pageToken"] = page_token
        payload = await _google_get(
            GA_ACCOUNT_SUMMARIES_URL,
            token,
            db,
            connection,
            params=params,
        )
        for account in payload.get("accountSummaries", []):
            for property_item in account.get("propertySummaries", []):
                property_name = property_item.get("property", "")
                property_id = property_name.split("/")[-1] if property_name else ""
                if not property_id:
                    continue
                items.append(
                    {
                        "id": property_id,
                        "name": property_item.get("displayName") or property_name,
                        "property_type": property_item.get("propertyType"),
                    }
                )

        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    return items


async def search_console_performance(
    connection: GoogleIntegration,
    db: Session,
    *,
    site_url: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    token = await get_access_token(connection, db)
    encoded_site = quote(site_url, safe="")
    url = GSC_SEARCH_ANALYTICS_URL.format(site_url=encoded_site)
    payload = await _google_post(
        url,
        token,
        {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["date"],
            "rowLimit": 25000,
            "dataState": "final",
        },
        db,
        connection,
    )

    items = []
    total_clicks = 0.0
    total_impressions = 0.0
    for row in payload.get("rows", []):
        keys = row.get("keys") or []
        clicks = float(row.get("clicks", 0))
        impressions = float(row.get("impressions", 0))
        total_clicks += clicks
        total_impressions += impressions
        items.append(
            {
                "date": keys[0] if keys else "",
                "clicks": clicks,
                "impressions": impressions,
                "ctr": float(row.get("ctr", 0)),
                "position": float(row.get("position", 0)),
            }
        )

    items.sort(key=lambda item: item["date"])
    return {
        "items": items,
        "totals": {
            "clicks": total_clicks,
            "impressions": total_impressions,
        },
    }


async def analytics_performance(
    connection: GoogleIntegration,
    db: Session,
    *,
    property_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    token = await get_access_token(connection, db)
    url = GA_RUN_REPORT_URL.format(property_id=property_id)
    payload = await _google_post(
        url,
        token,
        {
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "dimensions": [{"name": "date"}],
            "metrics": [
                {"name": "totalUsers"},
                {"name": "sessions"},
                {"name": "screenPageViews"},
                {"name": "conversions"},
            ],
            "orderBys": [
                {"dimension": {"dimensionName": "date", "orderType": "NUMERIC_ASCENDING"}}
            ],
            "limit": 1000,
        },
        db,
        connection,
    )

    items = []
    totals = {
        "users": 0.0,
        "sessions": 0.0,
        "pageviews": 0.0,
        "conversions": 0.0,
    }

    for row in payload.get("rows", []):
        dimension_values = row.get("dimensionValues", [])
        metric_values = row.get("metricValues", [])
        values = [float(item.get("value", 0) or 0) for item in metric_values]
        values += [0.0] * (4 - len(values))

        point = {
            "date": dimension_values[0].get("value", "") if dimension_values else "",
            "users": values[0],
            "sessions": values[1],
            "pageviews": values[2],
            "conversions": values[3],
        }
        items.append(point)
        totals["users"] += point["users"]
        totals["sessions"] += point["sessions"]
        totals["pageviews"] += point["pageviews"]
        totals["conversions"] += point["conversions"]

    return {"items": items, "totals": totals}


async def revoke_connection(db: Session, connection: GoogleIntegration) -> None:
    try:
        access_token = decrypt_token(connection.access_token_encrypted)
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(
                GOOGLE_REVOKE_URL,
                params={"token": access_token},
            )
    except Exception:
        pass

    db.delete(connection)
    db.commit()
