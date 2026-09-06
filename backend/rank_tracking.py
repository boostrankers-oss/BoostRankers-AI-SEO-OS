from __future__ import annotations

import math
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from database.database import engine
from database.session import get_db
from models.base import BaseModel as ORMBaseModel
from models.client import Client
from models.google_integration import GoogleIntegration
from models.user import User
from api.deps.current_user import get_current_user
from services.google_integration_service import get_access_token, get_connection

GSC_SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"
GSC_SEARCH_ANALYTICS_URL = "https://www.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query"

router = APIRouter(prefix="/api/rank-tracking", tags=["Rank Tracking"])


class RankTrackingKeyword(ORMBaseModel):
    __tablename__ = "rank_tracking_keywords"

    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    keyword: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    target_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    search_engine: Mapped[str] = mapped_column(String(50), nullable=False, default="google")
    country: Mapped[str] = mapped_column(String(10), nullable=False, default="global")
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="en")
    device: Mapped[str] = mapped_column(String(20), nullable=False, default="all")
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    __table_args__ = (Index("ix_rank_tracking_keywords_company_keyword", "company_id", "keyword"),)


class RankTrackingSnapshot(ORMBaseModel):
    __tablename__ = "rank_tracking_snapshots"

    keyword_id: Mapped[str] = mapped_column(String(36), ForeignKey("rank_tracking_keywords.id", ondelete="CASCADE"), nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True)
    position: Mapped[float | None] = mapped_column(Float, nullable=True)
    ranking_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    clicks: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    impressions: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    ctr: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="google_search_console")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ok")
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (Index("ix_rank_tracking_snapshots_keyword_checked", "keyword_id", "checked_at"),)


class KeywordCreate(BaseModel):
    keyword: str = Field(min_length=1, max_length=500)
    client_id: str | None = None
    target_url: str | None = Field(default=None, max_length=2000)
    search_engine: str = Field(default="google", max_length=50)
    country: str = Field(default="global", max_length=10)
    location: str | None = Field(default=None, max_length=255)
    language: str = Field(default="en", max_length=20)
    device: str = Field(default="all", max_length=20)
    frequency: str = Field(default="daily", max_length=20)

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: str) -> str:
        value = " ".join(value.split()).strip()
        if not value:
            raise ValueError("Keyword cannot be empty")
        return value


class KeywordUpdate(BaseModel):
    keyword: str | None = Field(default=None, min_length=1, max_length=500)
    client_id: str | None = None
    target_url: str | None = Field(default=None, max_length=2000)
    search_engine: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default=None, max_length=10)
    location: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, max_length=20)
    device: str | None = Field(default=None, max_length=20)
    frequency: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class RefreshRequest(BaseModel):
    keyword_ids: list[str] = Field(default_factory=list, max_length=100)


def _company_id(current_user: User) -> str:
    if not current_user.company_id:
        raise HTTPException(status_code=403, detail="A company account is required for rank tracking.")
    return str(current_user.company_id)


def _serialize_keyword(db: Session, row: RankTrackingKeyword) -> dict[str, Any]:
    snapshots = (
        db.query(RankTrackingSnapshot)
        .filter(RankTrackingSnapshot.keyword_id == row.id)
        .order_by(RankTrackingSnapshot.checked_at.desc())
        .limit(2)
        .all()
    )
    latest = snapshots[0] if snapshots else None
    previous = snapshots[1] if len(snapshots) > 1 else None
    position = latest.position if latest else None
    previous_position = previous.position if previous else None
    change = round(previous_position - position, 2) if position is not None and previous_position is not None else None
    client = db.get(Client, row.client_id) if row.client_id else None
    return {
        "id": row.id,
        "company_id": row.company_id,
        "client_id": row.client_id,
        "client_name": getattr(client, "business_name", None),
        "keyword": row.keyword,
        "target_url": row.target_url,
        "search_engine": row.search_engine,
        "country": row.country,
        "location": row.location,
        "language": row.language,
        "device": row.device,
        "frequency": row.frequency,
        "is_active": row.is_active,
        "current_position": position,
        "previous_position": previous_position,
        "change": change,
        "ranking_url": latest.ranking_url if latest else None,
        "last_checked_at": latest.checked_at.isoformat() if latest else None,
        "status": latest.status if latest else "not_checked",
        "last_error": latest.error_message if latest and latest.error_message else None,
    }


def _get_keyword(db: Session, company_id: str, keyword_id: str) -> RankTrackingKeyword:
    row = db.query(RankTrackingKeyword).filter(
        RankTrackingKeyword.id == keyword_id,
        RankTrackingKeyword.company_id == company_id,
        RankTrackingKeyword.deleted_at.is_(None),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Tracked keyword not found.")
    return row


def _date_window(days: int = 90) -> tuple[str, str]:
    # GSC data can lag by a few days. Exclude the most recent 3 days.
    end = date.today() - timedelta(days=3)
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def _property_from_connection(connection: GoogleIntegration) -> str | None:
    names = (
        "selected_property",
        "selected_search_console_property",
        "search_console_property",
        "property",
        "site_url",
    )
    for name in names:
        value = getattr(connection, name, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    # Some versions keep provider settings in a JSON/dict field.
    for container_name in ("settings", "metadata", "config", "provider_data"):
        container = getattr(connection, container_name, None)
        if isinstance(container, dict):
            for name in names:
                value = container.get(name)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


async def _list_gsc_sites(connection: GoogleIntegration, db: Session) -> list[str]:
    import httpx

    token = await get_access_token(connection, db)
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(GSC_SITES_URL, headers=headers)
        if response.status_code == 401:
            token = await get_access_token(connection, db)
            headers["Authorization"] = f"Bearer {token}"
            response = await client.get(GSC_SITES_URL, headers=headers)
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {}).get("message") or "Unable to read Google Search Console properties."
        except Exception:
            detail = "Unable to read Google Search Console properties."
        raise HTTPException(status_code=response.status_code, detail=detail)
    return [str(item.get("siteUrl")) for item in response.json().get("siteEntry", []) if item.get("siteUrl")]


async def _resolve_gsc_property(connection: GoogleIntegration, db: Session) -> tuple[str, list[str]]:
    selected = _property_from_connection(connection)
    sites = await _list_gsc_sites(connection, db)
    if selected and selected in sites:
        return selected, sites
    if selected and not sites:
        return selected, [selected]
    if sites:
        # Fall back to the first property the connected Google account can actually access.
        return sites[0], sites
    raise HTTPException(status_code=400, detail="The connected Google account has no accessible Search Console properties.")


def _normalize_country(value: str | None) -> list[str]:
    if not value or value.lower() == "global":
        return []
    raw = value.strip().lower()
    aliases = {"au": "aus", "us": "usa", "uk": "gbr", "ca": "can", "nz": "nzl", "in": "ind"}
    return list(dict.fromkeys([raw, aliases.get(raw, raw)]))


def _normalize_device(value: str | None) -> str | None:
    if not value or value.lower() == "all":
        return None
    raw = value.strip().lower()
    return raw if raw in {"desktop", "mobile", "tablet"} else None


async def _gsc_request(connection: GoogleIntegration, db: Session, site_url: str, body: dict[str, Any]) -> list[dict[str, Any]]:
    import httpx

    token = await get_access_token(connection, db)
    url = GSC_SEARCH_ANALYTICS_URL.format(site_url=quote(site_url, safe=""))
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, headers={"Authorization": f"Bearer {token}"}, json=body)
        if response.status_code == 401:
            token = await get_access_token(connection, db)
            response = await client.post(url, headers={"Authorization": f"Bearer {token}"}, json=body)
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {}).get("message") or "Google Search Console request failed."
        except Exception:
            detail = "Google Search Console request failed."
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json().get("rows", [])


async def _query_gsc_keyword(
    connection: GoogleIntegration,
    db: Session,
    *,
    site_url: str,
    keyword: str,
    start_date: str,
    end_date: str,
    country: str = "global",
    device: str = "all",
    target_url: str | None = None,
) -> dict[str, Any]:
    base = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["query", "page"],
        "rowLimit": 25000,
        "dataState": "all",
    }
    normalized_keyword = " ".join(keyword.casefold().split())
    country_values = _normalize_country(country)
    device_value = _normalize_device(device)

    def make_filters(use_country: str | None, use_device: str | None, exact: bool = True) -> list[dict[str, str]]:
        filters: list[dict[str, str]] = [{"dimension": "query", "operator": "equals" if exact else "contains", "expression": keyword}]
        if use_country:
            filters.append({"dimension": "country", "operator": "equals", "expression": use_country})
        if use_device:
            filters.append({"dimension": "device", "operator": "equals", "expression": use_device})
        return filters

    attempts: list[list[dict[str, str]]] = []
    if country_values:
        for c in country_values:
            attempts.append(make_filters(c, device_value))
    else:
        attempts.append(make_filters(None, device_value))
    # If filters are too restrictive or the country code was entered differently, retry without them.
    attempts.append(make_filters(None, None))

    rows: list[dict[str, Any]] = []
    for filters in attempts:
        rows = await _gsc_request(connection, db, site_url, {**base, "dimensionFilterGroups": [{"filters": filters}]})
        if rows:
            break

    # Last-resort query inventory: GSC can return a keyword with different casing/spacing than the UI input.
    if not rows:
        inventory = await _gsc_request(
            connection,
            db,
            site_url,
            {**base, "dimensions": ["query", "page"], "rowLimit": 25000},
        )
        rows = [
            item for item in inventory
            if normalized_keyword == " ".join(str((item.get("keys") or [""])[0]).casefold().split())
        ]

    if not rows:
        return {
            "position": None,
            "ranking_url": None,
            "clicks": 0.0,
            "impressions": 0.0,
            "ctr": 0.0,
            "matched_rows": 0,
            "message": f"No Search Console data for this query from {start_date} to {end_date}.",
        }

    if target_url:
        target_norm = target_url.rstrip("/").casefold()
        matching = [r for r in rows if str((r.get("keys") or [None, None])[1] or "").rstrip("/").casefold() == target_norm]
        if matching:
            rows = matching

    best = min(rows, key=lambda item: float(item.get("position", math.inf)))
    total_clicks = sum(float(item.get("clicks", 0)) for item in rows)
    total_impressions = sum(float(item.get("impressions", 0)) for item in rows)
    return {
        "position": round(float(best.get("position", 0)), 2),
        "ranking_url": (best.get("keys") or [None, None])[1],
        "clicks": total_clicks,
        "impressions": total_impressions,
        "ctr": total_clicks / total_impressions if total_impressions else 0.0,
        "matched_rows": len(rows),
        "message": f"Matched {len(rows)} Search Console result row(s).",
    }


async def _refresh_keyword(db: Session, row: RankTrackingKeyword, company_id: str) -> dict[str, Any]:
    connection = get_connection(db, company_id, "search_console")
    if connection is None:
        raise HTTPException(status_code=400, detail="Google Search Console is not connected. Connect it in Google Integration first.")

    site_url, available_sites = await _resolve_gsc_property(connection, db)
    start_date, end_date = _date_window(90)
    try:
        data = await _query_gsc_keyword(
            connection, db, site_url=site_url, keyword=row.keyword,
            start_date=start_date, end_date=end_date, country=row.country,
            device=row.device, target_url=row.target_url,
        )
        snapshot = RankTrackingSnapshot(
            keyword_id=row.id, checked_at=datetime.now(UTC), position=data["position"],
            ranking_url=data["ranking_url"], clicks=data["clicks"], impressions=data["impressions"],
            ctr=data["ctr"], source="google_search_console", status="ok",
            error_message=None if data["position"] is not None else data["message"],
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        result = _serialize_keyword(db, row)
        result["measurement_property"] = site_url
        result["available_properties"] = available_sites
        result["date_range"] = {"start": start_date, "end": end_date}
        result["measurement_message"] = data["message"]
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        snapshot = RankTrackingSnapshot(
            keyword_id=row.id, checked_at=datetime.now(UTC), source="google_search_console",
            status="error", error_message=str(exc)[:1000],
        )
        db.add(snapshot)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Rank check failed: {exc}") from exc


@router.get("/status")
async def rank_tracking_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)
    connection = get_connection(db, company_id, "search_console")
    if connection is None:
        return {"google_search_console_connected": False, "selected_property": None, "measurement": "Google Search Console average position"}
    selected = _property_from_connection(connection)
    try:
        sites = await _list_gsc_sites(connection, db)
    except Exception as exc:
        return {
            "google_search_console_connected": True,
            "selected_property": selected,
            "measurement": "Google Search Console average position",
            "property_error": str(getattr(exc, "detail", exc)),
        }
    return {
        "google_search_console_connected": True,
        "selected_property": selected if selected in sites else (sites[0] if sites else None),
        "available_properties": sites,
        "measurement": "Google Search Console average position",
    }


@router.get("/keywords")
def list_keywords(active_only: bool = Query(False), client_id: str | None = Query(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    company_id = _company_id(current_user)
    query = db.query(RankTrackingKeyword).filter(RankTrackingKeyword.company_id == company_id, RankTrackingKeyword.deleted_at.is_(None))
    if active_only:
        query = query.filter(RankTrackingKeyword.is_active.is_(True))
    if client_id:
        query = query.filter(RankTrackingKeyword.client_id == client_id)
    return [_serialize_keyword(db, row) for row in query.order_by(RankTrackingKeyword.created_at.desc()).all()]


@router.post("/keywords", status_code=status.HTTP_201_CREATED)
def create_keyword(payload: KeywordCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)
    if payload.client_id:
        client = db.query(Client).filter(Client.id == payload.client_id, Client.company_id == company_id).first()
        if client is None:
            raise HTTPException(status_code=404, detail="Client not found in your company.")
    existing = db.query(RankTrackingKeyword).filter(
        RankTrackingKeyword.company_id == company_id,
        func.lower(RankTrackingKeyword.keyword) == payload.keyword.lower(),
        RankTrackingKeyword.client_id == payload.client_id,
        RankTrackingKeyword.deleted_at.is_(None),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="This keyword is already being tracked.")
    row = RankTrackingKeyword(
        company_id=company_id, client_id=payload.client_id, keyword=payload.keyword,
        target_url=payload.target_url, search_engine=payload.search_engine, country=payload.country,
        location=payload.location, language=payload.language, device=payload.device,
        frequency=payload.frequency, is_active=True, created_by=str(current_user.id), updated_by=str(current_user.id),
    )
    db.add(row); db.commit(); db.refresh(row)
    return _serialize_keyword(db, row)


@router.put("/keywords/{keyword_id}")
def update_keyword(keyword_id: str, payload: KeywordUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)
    row = _get_keyword(db, company_id, keyword_id)
    values = payload.model_dump(exclude_unset=True)
    if "client_id" in values and values["client_id"]:
        client = db.query(Client).filter(Client.id == values["client_id"], Client.company_id == company_id).first()
        if client is None:
            raise HTTPException(status_code=404, detail="Client not found in your company.")
    for key, value in values.items():
        if key == "keyword" and isinstance(value, str):
            value = " ".join(value.split()).strip()
        setattr(row, key, value)
    row.updated_by = str(current_user.id); db.commit(); db.refresh(row)
    return _serialize_keyword(db, row)


@router.delete("/keywords/{keyword_id}")
def delete_keyword(keyword_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, bool]:
    company_id = _company_id(current_user); row = _get_keyword(db, company_id, keyword_id)
    row.deleted_at = datetime.now(UTC); row.is_active = False; row.updated_by = str(current_user.id)
    db.commit(); return {"success": True}


@router.get("/overview")
def overview(client_id: str | None = Query(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)
    query = db.query(RankTrackingKeyword).filter(
        RankTrackingKeyword.company_id == company_id,
        RankTrackingKeyword.deleted_at.is_(None),
        RankTrackingKeyword.is_active.is_(True),
    )
    if client_id:
        query = query.filter(RankTrackingKeyword.client_id == client_id)
    items = [_serialize_keyword(db, row) for row in query.all()]
    positions = [float(item["current_position"]) for item in items if item["current_position"] is not None]
    changes = [float(item["change"]) for item in items if item["change"] is not None]
    return {
        "tracked_keywords": len(items), "top_3": sum(p <= 3 for p in positions),
        "top_10": sum(p <= 10 for p in positions), "top_20": sum(p <= 20 for p in positions),
        "improved": sum(c > 0 for c in changes), "declined": sum(c < 0 for c in changes),
        "not_ranking": sum(item["current_position"] is None for item in items),
        "average_position": round(sum(positions) / len(positions), 2) if positions else None,
    }


@router.post("/refresh")
async def refresh_keywords(payload: RefreshRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)
    query = db.query(RankTrackingKeyword).filter(
        RankTrackingKeyword.company_id == company_id,
        RankTrackingKeyword.deleted_at.is_(None),
        RankTrackingKeyword.is_active.is_(True),
    )
    if payload.keyword_ids:
        query = query.filter(RankTrackingKeyword.id.in_(payload.keyword_ids))
    rows = query.order_by(RankTrackingKeyword.created_at.asc()).limit(100).all()
    results: list[dict[str, Any]] = []; errors: list[dict[str, str]] = []
    for row in rows:
        try:
            results.append(await _refresh_keyword(db, row, company_id))
        except HTTPException as exc:
            errors.append({"keyword_id": row.id, "keyword": row.keyword, "error": str(exc.detail)})
    return {"updated": len(results), "items": results, "errors": errors}


@router.post("/keywords/{keyword_id}/refresh")
async def refresh_one_keyword(keyword_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user); row = _get_keyword(db, company_id, keyword_id)
    return await _refresh_keyword(db, row, company_id)


@router.get("/keywords/{keyword_id}/history")
def keyword_history(keyword_id: str, limit: int = Query(90, ge=1, le=365), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user); row = _get_keyword(db, company_id, keyword_id)
    snapshots = db.query(RankTrackingSnapshot).filter(RankTrackingSnapshot.keyword_id == row.id).order_by(RankTrackingSnapshot.checked_at.desc()).limit(limit).all()
    snapshots.reverse()
    return {"keyword": _serialize_keyword(db, row), "history": [{
        "id": item.id, "checked_at": item.checked_at.isoformat(), "position": item.position,
        "ranking_url": item.ranking_url, "clicks": item.clicks, "impressions": item.impressions,
        "ctr": item.ctr, "source": item.source, "status": item.status, "error_message": item.error_message,
    } for item in snapshots]}


@router.on_event("startup")
def ensure_rank_tracking_tables() -> None:
    RankTrackingKeyword.__table__.create(bind=engine, checkfirst=True)
    RankTrackingSnapshot.__table__.create(bind=engine, checkfirst=True)
