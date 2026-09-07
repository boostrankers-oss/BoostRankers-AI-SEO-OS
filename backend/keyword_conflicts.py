from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Callable, TypeVar
from urllib.parse import quote, urljoin, urlparse
import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, JSON as SAJSON, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Mapped, Session, mapped_column

from api.deps.current_user import get_current_user
from database.database import engine, SessionLocal, get_db
from models.base import BaseModel as ORMBaseModel
from models.client import Client
from models.google_integration import GoogleIntegration
from models.user import User
from services.google_integration_service import get_access_token, get_connection

logger = logging.getLogger(__name__)

T = TypeVar("T")

def _run_db_read_with_recovery(db: Session, operation: Callable[[Session], T]) -> T:
    """Run a short read query and recover once from a stale PostgreSQL connection.

    Supabase/PostgreSQL can close an idle SSL connection while SQLAlchemy still
    has it in the pool. The first query then raises an OperationalError such
    as ``SSL error: unexpected eof while reading``. This feature is isolated
    by retrying the read with a fresh Session after disposing the stale pool.
    It does not change application-wide database configuration or data.
    """
    try:
        return operation(db)
    except OperationalError as exc:
        logger.warning("Keyword Conflicts database read failed; recovering stale connection: %s", exc)
        try:
            db.rollback()
        except Exception:
            logger.debug("Could not rollback failed Keyword Conflicts session", exc_info=True)
        try:
            db.close()
        except Exception:
            logger.debug("Could not close failed Keyword Conflicts session", exc_info=True)

        # Drop pooled connections so the next Session obtains a new SSL
        # connection. ``close=False`` keeps this recovery local to the pool
        # lifecycle and avoids interfering with connections owned elsewhere.
        try:
            engine.dispose(close=False)
        except TypeError:
            # Compatibility with older SQLAlchemy versions.
            engine.dispose()

        fresh = SessionLocal()
        try:
            return operation(fresh)
        finally:
            fresh.close()


router = APIRouter(prefix="/api/keyword-conflicts", tags=["Keyword Conflicts"])

GSC_SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"
GSC_SEARCH_ANALYTICS_URL = "https://www.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in",
    "is", "it", "of", "on", "or", "the", "to", "what", "when", "where", "which",
    "who", "why", "with", "your", "you", "best", "guide", "tips", "top", "near", "local",
}

# ---------------------------------------------------------------------------
# Database models. These are isolated from existing modules and are created
# with checkfirst=True so this feature does not require a risky schema rewrite.
# ---------------------------------------------------------------------------

class KeywordConflictScan(ORMBaseModel):
    __tablename__ = "keyword_conflict_scans"

    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pages_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    focus_keywords_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflicts_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repeated_focus_keywords: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stuffing_warnings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gsc_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    measurement_property: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    date_start: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_end: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    pages_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gsc_status_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    focus_status_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    gsc_rows_measured: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gsc_shared_queries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gsc_candidate_pairs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wordpress_posts_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wordpress_pages_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wordpress_content_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wordpress_status_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class KeywordConflict(ORMBaseModel):
    __tablename__ = "keyword_conflicts"

    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("keyword_conflict_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    normalized_keyword: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    primary_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    competing_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    conflict_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="low", index=True)
    intent_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    content_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    gsc_overlap: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    ranking_displacement: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    recommendation: Mapped[str] = mapped_column(String(80), nullable=False, default="Review separately")
    evidence: Mapped[dict[str, Any]] = mapped_column(SAJSON, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_keyword_conflicts_scan_score", "scan_id", "conflict_score"),
        Index("ix_keyword_conflicts_company_keyword", "company_id", "normalized_keyword"),
    )


class KeywordConflictPage(ORMBaseModel):
    __tablename__ = "keyword_conflict_pages"

    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("keyword_conflict_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    title: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    h1: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    canonical: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    focus_keyword: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    keyword_frequency: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    stuffing_risk: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    gsc_primary_query: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    gsc_query_impressions: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    gsc_query_clicks: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    gsc_query_position: Mapped[float | None] = mapped_column(Float, nullable=True)
    page_type: Mapped[str] = mapped_column(String(30), nullable=False, default="page")
    evidence: Mapped[dict[str, Any]] = mapped_column(SAJSON, nullable=False, default=dict)

    __table_args__ = (Index("ix_keyword_conflict_pages_scan_url", "scan_id", "url"),)


class KeywordConflictQuery(ORMBaseModel):
    __tablename__ = "keyword_conflict_queries"

    conflict_id: Mapped[str] = mapped_column(String(36), ForeignKey("keyword_conflicts.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    query: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    primary_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    competing_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    primary_clicks: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    primary_impressions: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    primary_position: Mapped[float | None] = mapped_column(Float, nullable=True)
    competing_clicks: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    competing_impressions: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    competing_position: Mapped[float | None] = mapped_column(Float, nullable=True)
    url_switch_signal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


# ---------------------------------------------------------------------------
# API schemas
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    client_id: str
    days: int = Field(default=90, ge=28, le=90)
    max_pages: int = Field(default=150, ge=10, le=300)
    include_gsc: bool = True
    wordpress_site: HttpUrl | None = None
    wordpress_username: str | None = Field(default=None, max_length=255)
    wordpress_application_password: str | None = Field(default=None, max_length=255)

    @field_validator("wordpress_username", "wordpress_application_password")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        return value.strip() if value else None


class StatusUpdate(BaseModel):
    status: str = Field(pattern="^(open|reviewed|resolved|ignored)$")


class ResolveWithClaudeRequest(BaseModel):
    wordpress_site: HttpUrl | None = None
    wordpress_username: str | None = Field(default=None, max_length=255)
    wordpress_application_password: str | None = Field(default=None, max_length=255)

    @field_validator("wordpress_username", "wordpress_application_password")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        return value.strip() if value else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _company_id(user: User) -> str:
    company_id = getattr(user, "company_id", None)
    if not company_id:
        raise HTTPException(status_code=403, detail="Your account is not attached to a company.")
    return str(company_id)


def _normalize(text: str | None) -> str:
    value = (text or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split()).strip()


def _tokens(text: str | None) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in STOPWORDS
    }


def _similarity(a: str | None, b: str | None) -> float:
    aa, bb = _tokens(a), _tokens(b)
    if not aa or not bb:
        return 0.0
    jaccard = len(aa & bb) / max(1, len(aa | bb))
    sequence = SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()
    return round((jaccard * 0.7) + (sequence * 0.3), 4)


def _safe_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Client website is not a valid HTTP/HTTPS URL.")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/') or '/'}"


def _canonical_url_key(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(str(url).strip())
        if not parsed.netloc:
            return ""
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/")
        return f"{parsed.scheme.lower()}://{host}{path}" + (f"?{parsed.query}" if parsed.query else "")
    except Exception:
        return _normalize(url)


def _same_domain(a: str, b: str) -> bool:
    return urlparse(a).netloc.lower().lstrip("www.") == urlparse(b).netloc.lower().lstrip("www.")


def _page_type(url: str, title: str, h1: str) -> str:
    path = urlparse(url).path.lower()
    combined = f"{path} {title} {h1}".lower()
    if "/blog/" in path or "/post/" in path or "blog" in combined or "article" in combined:
        return "post"
    return "page"


def _keyword_frequency(body: str, keyword: str) -> float:
    normalized_body = _normalize(body)
    normalized_kw = _normalize(keyword)
    if not normalized_body or not normalized_kw:
        return 0.0
    words = normalized_body.split()
    kw_words = normalized_kw.split()
    if len(kw_words) > len(words):
        return 0.0
    count = sum(1 for i in range(len(words) - len(kw_words) + 1) if words[i:i + len(kw_words)] == kw_words)
    return round((count / max(1, len(words))) * 100, 4)


def _stuffing_risk(frequency: float, word_count: int) -> float:
    # This is a heuristic signal, not a Google penalty detector.
    if word_count < 250:
        return 100.0 if frequency >= 2.5 else (60.0 if frequency >= 1.5 else 0.0)
    if frequency >= 4:
        return 100.0
    if frequency >= 2.5:
        return 80.0
    if frequency >= 1.8:
        return 55.0
    if frequency >= 1.2:
        return 25.0
    return 0.0


def _risk(score: float) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _recommendation(evidence: dict[str, Any]) -> str:
    if evidence.get("canonical_conflict"):
        return "Canonical review"
    if evidence.get("exact_focus_keyword") and evidence.get("gsc_overlap"):
        return "Consolidate or differentiate"
    if evidence.get("url_switch_signal"):
        return "Review search intent"
    if evidence.get("content_similarity", 0) >= 0.65:
        return "Differentiate content"
    if evidence.get("gsc_overlap"):
        return "Retarget intent"
    return "Review separately"


def _serialize_scan(row: KeywordConflictScan) -> dict[str, Any]:
    return {
        "id": row.id,
        "client_id": row.client_id,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "pages_scanned": row.pages_scanned,
        "focus_keywords_found": row.focus_keywords_found,
        "conflicts_found": row.conflicts_found,
        "repeated_focus_keywords": row.repeated_focus_keywords,
        "stuffing_warnings": row.stuffing_warnings,
        "gsc_connected": row.gsc_connected,
        "measurement_property": row.measurement_property,
        "date_start": row.date_start,
        "date_end": row.date_end,
        "error_message": row.error_message,
        "progress_message": row.progress_message,
        "pages_discovered": row.pages_discovered,
        "last_activity_at": row.last_activity_at.isoformat() if row.last_activity_at else None,
        "gsc_status_message": row.gsc_status_message,
        "focus_status_message": row.focus_status_message,
        "gsc_rows_measured": row.gsc_rows_measured,
        "gsc_shared_queries": row.gsc_shared_queries,
        "gsc_candidate_pairs": row.gsc_candidate_pairs,
        "wordpress_posts_found": getattr(row, "wordpress_posts_found", 0),
        "wordpress_pages_found": getattr(row, "wordpress_pages_found", 0),
        "wordpress_content_scanned": getattr(row, "wordpress_content_scanned", 0),
        "wordpress_status_message": getattr(row, "wordpress_status_message", None),
    }


def _serialize_conflict(row: KeywordConflict) -> dict[str, Any]:
    return {
        "id": row.id,
        "scan_id": row.scan_id,
        "client_id": row.client_id,
        "keyword": row.keyword,
        "normalized_keyword": row.normalized_keyword,
        "primary_url": row.primary_url,
        "competing_url": row.competing_url,
        "conflict_score": round(row.conflict_score, 1),
        "risk_level": row.risk_level,
        "intent_similarity": round(row.intent_similarity, 3),
        "content_similarity": round(row.content_similarity, 3),
        "gsc_overlap": round(row.gsc_overlap, 3),
        "ranking_displacement": round(row.ranking_displacement, 3),
        "status": row.status,
        "recommendation": row.recommendation,
        "evidence": row.evidence or {},
    }


async def _fetch_text(client: httpx.AsyncClient, url: str, headers: dict[str, str] | None = None) -> tuple[str, int, str]:
    try:
        response = await client.get(url, headers=headers, follow_redirects=True)
        return response.text, response.status_code, str(response.url)
    except Exception as exc:
        logger.warning("Keyword conflict fetch failed for %s: %s", url, exc)
        return "", 0, url


async def _sitemap_urls(http: httpx.AsyncClient, base_url: str, limit: int) -> list[str]:
    candidates = [
        urljoin(base_url.rstrip("/") + "/", "sitemap.xml"),
        urljoin(base_url.rstrip("/") + "/", "wp-sitemap.xml"),
    ]
    seen: set[str] = set()
    output: list[str] = []

    async def parse_sitemap(url: str, depth: int = 0) -> None:
        if depth > 2 or len(output) >= limit or url in seen:
            return
        seen.add(url)
        try:
            response = await http.get(url, follow_redirects=True)
            if response.status_code >= 400:
                return
            root = ET.fromstring(response.text)
        except Exception:
            return
        tag = root.tag.lower()
        locs = [element.text.strip() for element in root.iter() if element.tag.lower().endswith("loc") and element.text]
        if tag.endswith("sitemapindex"):
            for loc in locs[:50]:
                if len(output) >= limit:
                    break
                await parse_sitemap(loc, depth + 1)
        else:
            for loc in locs:
                if len(output) >= limit:
                    break
                if _same_domain(base_url, loc) and loc not in output:
                    output.append(loc.split("#", 1)[0])

    http = httpx.AsyncClient(timeout=25, headers={"User-Agent": "BoostRankers-KeywordConflictScanner/1.0"})
    try:
        for candidate in candidates:
            await parse_sitemap(candidate)
            if output:
                break
    finally:
        await http.aclose()
    return output[:limit]


async def _crawl_site(base_url: str, max_pages: int, progress_callback: Any = None) -> list[dict[str, Any]]:
    # Use a single AsyncClient for the crawl to avoid opening hundreds of sockets.
    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "BoostRankers-KeywordConflictScanner/1.0"},
        limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
    ) as http:
        sitemap_candidates = [urljoin(base_url.rstrip("/") + "/", "sitemap.xml"), urljoin(base_url.rstrip("/") + "/", "wp-sitemap.xml")]
        urls: list[str] = []
        seen_sitemaps: set[str] = set()

        async def collect_sitemap(url: str, depth: int = 0) -> None:
            if depth > 2 or len(urls) >= max_pages or url in seen_sitemaps:
                return
            seen_sitemaps.add(url)
            try:
                r = await http.get(url)
                if r.status_code >= 400:
                    return
                root = ET.fromstring(r.text)
            except Exception:
                return
            locs = [e.text.strip() for e in root.iter() if e.tag.lower().endswith("loc") and e.text]
            if root.tag.lower().endswith("sitemapindex"):
                for loc in locs[:50]:
                    await collect_sitemap(loc, depth + 1)
                    if len(urls) >= max_pages:
                        return
            else:
                for loc in locs:
                    clean = loc.split("#", 1)[0]
                    if _same_domain(base_url, clean) and clean not in urls:
                        urls.append(clean)
                        if len(urls) >= max_pages:
                            return

        for candidate in sitemap_candidates:
            await collect_sitemap(candidate)
            if urls:
                break

        if not urls:
            urls = [base_url]

        queue = list(urls[:max_pages])
        queued = set(queue)
        pages: list[dict[str, Any]] = []
        index = 0
        semaphore = asyncio.Semaphore(8)

        async def fetch_page(url: str) -> dict[str, Any] | None:
            async with semaphore:
                try:
                    response = await http.get(url)
                    if response.status_code >= 400 or "text/html" not in response.headers.get("content-type", "text/html"):
                        return None
                    soup = BeautifulSoup(response.text, "html.parser")
                    for tag in soup(["script", "style", "noscript", "svg"]):
                        tag.decompose()
                    title = soup.title.get_text(" ", strip=True) if soup.title else ""
                    description_tag = soup.find("meta", attrs={"name": "description"})
                    description = str(description_tag.get("content", "")) if description_tag else ""
                    h1s = [x.get_text(" ", strip=True) for x in soup.find_all("h1")][:5]
                    h2s = [x.get_text(" ", strip=True) for x in soup.find_all("h2")][:20]
                    canonical_tag = soup.find("link", attrs={"rel": lambda v: "canonical" in v if isinstance(v, list) else v == "canonical"})
                    canonical = str(canonical_tag.get("href", "")).strip() if canonical_tag else ""
                    canonical = urljoin(str(response.url), canonical) if canonical else ""
                    body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
                    body = body[:180000]
                    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9'-]{2,}\b", body.lower())
                    anchors = [a.get_text(" ", strip=True) for a in soup.find_all("a", href=True)][:300]
                    links = []
                    for a in soup.find_all("a", href=True)[:300]:
                        href = str(a.get("href", "")).strip()
                        absolute = urljoin(str(response.url), href).split("#", 1)[0]
                        if _same_domain(base_url, absolute):
                            links.append(absolute)
                    return {
                        "url": str(response.url).split("#", 1)[0],
                        "status_code": response.status_code,
                        "title": title,
                        "description": description,
                        "h1": h1s[0] if h1s else "",
                        "h1s": h1s,
                        "h2s": h2s,
                        "canonical": canonical,
                        "body": body,
                        "word_count": len(words),
                        "anchors": anchors,
                        "links": links,
                        "page_type": _page_type(str(response.url), title, h1s[0] if h1s else ""),
                    }
                except Exception as exc:
                    logger.debug("crawl page failed %s: %s", url, exc)
                    return None

        # Crawl in small concurrent batches. We also discover internal URLs if
        # sitemap coverage is incomplete, but never exceed max_pages.
        while index < len(queue) and len(pages) < max_pages:
            batch = queue[index:index + 8]
            index += 8
            results = await asyncio.gather(*(fetch_page(url) for url in batch))
            for page in results:
                if not page:
                    continue
                pages.append(page)
                for link in page["links"]:
                    if len(queue) >= max_pages:
                        break
                    if link not in queued and _same_domain(base_url, link):
                        queued.add(link)
                        queue.append(link)
            if progress_callback is not None:
                try:
                    result = progress_callback(len(pages), len(queue))
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    logger.debug("Keyword conflict progress update failed", exc_info=True)
        return pages[:max_pages]


async def _wordpress_content_inventory(
    site: str,
    username: str | None,
    password: str | None,
    max_items_per_type: int = 2000,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, int], str]:
    """Build a real WordPress Posts + Pages inventory for conflict analysis.

    This is deliberately independent of the normal website crawl limit. A blog post
    must not disappear from conflict detection simply because the sitemap crawler
    reached its ``max_pages`` limit on service/location pages first.

    Only published native WordPress posts/pages are included. The returned focus map
    contains only verified Yoast/Boost Rankers SEO Bridge values; titles/content are
    never promoted to focus keywords.
    """
    if not site:
        return [], {}, {"posts": 0, "pages": 0}, "WordPress site was not supplied."

    site = site.rstrip("/")
    username = username.strip() if username else None
    password = password.strip() if password else None
    if bool(username) != bool(password):
        return [], {}, {"posts": 0, "pages": 0}, "WordPress access requires both a username and WordPress Application Password."

    authenticated = bool(username and password)
    auth = (username, password) if authenticated else None
    headers = {"User-Agent": "BoostRankers-KeywordConflictScanner/2.0"}
    inventory: list[dict[str, Any]] = []
    focus_map: dict[str, str] = {}
    counts = {"posts": 0, "pages": 0}
    diagnostics: list[str] = []

    def html_to_page(item: dict[str, Any], content_type: str, focus: str | None) -> dict[str, Any] | None:
        link = str(item.get("link") or "").split("#", 1)[0]
        if not link:
            return None
        title_obj = item.get("title") if isinstance(item.get("title"), dict) else {}
        content_obj = item.get("content") if isinstance(item.get("content"), dict) else {}
        excerpt_obj = item.get("excerpt") if isinstance(item.get("excerpt"), dict) else {}
        title = str(title_obj.get("rendered") or "").strip()
        html = str(content_obj.get("raw") or content_obj.get("rendered") or "")
        excerpt = str(excerpt_obj.get("rendered") or excerpt_obj.get("raw") or "")
        soup = BeautifulSoup(html, "html.parser")
        h1s = [x.get_text(" ", strip=True) for x in soup.find_all("h1")][:5]
        h2s = [x.get_text(" ", strip=True) for x in soup.find_all("h2")][:20]
        body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:180000]
        words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9'-]{2,}\b", body.lower())
        anchors = [a.get_text(" ", strip=True) for a in soup.find_all("a", href=True)][:300]
        links: list[str] = []
        for a in soup.find_all("a", href=True)[:300]:
            absolute = urljoin(link, str(a.get("href", "")).strip()).split("#", 1)[0]
            if absolute and _same_domain(site, absolute):
                links.append(absolute)
        canonical = ""
        canonical_tag = soup.find("link", attrs={"rel": lambda v: "canonical" in v if isinstance(v, list) else v == "canonical"})
        if canonical_tag:
            canonical = urljoin(link, str(canonical_tag.get("href", "")).strip())
        if not canonical:
            # WordPress permalink is the safest available canonical fallback when
            # the REST response does not expose a head/canonical field.
            canonical = link
        return {
            "url": link,
            "status_code": 200,
            "title": title,
            "description": excerpt,
            "h1": h1s[0] if h1s else "",
            "h1s": h1s,
            "h2s": h2s,
            "canonical": canonical,
            "body": body,
            "word_count": len(words),
            "anchors": anchors,
            "links": links,
            "page_type": "post" if content_type == "posts" else "page",
            "wordpress_id": int(item["id"]) if item.get("id") is not None else None,
            "wordpress_content_type": content_type,
            "wordpress_source": True,
            "focus_keyword": focus,
        }

    async with httpx.AsyncClient(timeout=45, follow_redirects=True, auth=auth, headers=headers) as http:
        if authenticated:
            try:
                me = await http.get(f"{site}/wp-json/wp/v2/users/me", params={"context": "edit"})
                if me.status_code in (401, 403):
                    return [], {}, counts, "WordPress authentication failed. Check the username and Application Password."
                if me.status_code >= 400:
                    return [], {}, counts, f"WordPress authentication check returned HTTP {me.status_code}."
            except Exception as exc:
                return [], {}, counts, f"WordPress authentication check failed: {exc}"

        for content_type in ("posts", "pages"):
            fetched = 0
            page_num = 1
            truncated = False
            while fetched < max_items_per_type:
                per_page = min(100, max_items_per_type - fetched)
                try:
                    params: dict[str, Any] = {
                        "per_page": per_page,
                        "page": page_num,
                        "status": "publish",
                        "_fields": "id,link,title,content,excerpt,slug,status",
                    }
                    if authenticated:
                        params["context"] = "edit"
                    response = await http.get(f"{site}/wp-json/wp/v2/{content_type}", params=params)
                except Exception as exc:
                    diagnostics.append(f"{content_type}: request failed: {exc}")
                    break
                if response.status_code in (401, 403):
                    diagnostics.append(f"{content_type}: REST access denied (HTTP {response.status_code}).")
                    break
                if response.status_code in (400, 404):
                    break
                if response.status_code >= 400:
                    diagnostics.append(f"{content_type}: REST endpoint returned HTTP {response.status_code}.")
                    break
                try:
                    items = response.json()
                except Exception:
                    diagnostics.append(f"{content_type}: REST endpoint returned invalid JSON.")
                    break
                if not isinstance(items, list) or not items:
                    break

                for item in items:
                    if not isinstance(item, dict) or not item.get("id") or not item.get("link"):
                        continue
                    link = str(item.get("link") or "").split("#", 1)[0]
                    focus: str | None = None
                    # The SEO Bridge is the verified source for Yoast focus keyword.
                    try:
                        meta = await http.get(f"{site}/wp-json/boost-rankers/v1/seo-meta/{int(item['id'])}")
                        if meta.status_code not in (401, 403, 404) and meta.status_code < 400:
                            meta_payload = meta.json()
                            candidate = (
                                meta_payload.get("focus_keyword")
                                or meta_payload.get("focuskw")
                                or meta_payload.get("_yoast_wpseo_focuskw")
                            )
                            if isinstance(candidate, str) and candidate.strip():
                                focus = " ".join(candidate.split())
                    except Exception:
                        pass
                    page = html_to_page(item, content_type, focus)
                    if not page:
                        continue
                    inventory.append(page)
                    fetched += 1
                    counts[content_type] += 1
                    if focus:
                        focus_map[link] = focus
                        focus_map[_canonical_url_key(link)] = focus
                    if fetched >= max_items_per_type:
                        truncated = True
                        break
                total_pages = int(response.headers.get("X-WP-TotalPages", "0") or 0)
                if len(items) < per_page or (total_pages and page_num >= total_pages) or fetched >= max_items_per_type:
                    break
                page_num += 1
            if truncated:
                diagnostics.append(f"{content_type}: inventory capped at {max_items_per_type} published items for scan safety.")

    if not inventory:
        return [], {}, counts, "No published WordPress posts/pages were returned by the REST API."
    source = "authenticated WordPress/Yoast" if authenticated else "public WordPress REST/Yoast"
    message = f"Verified {counts['posts']} published post(s) and {counts['pages']} published page(s) from {source}."
    if focus_map:
        message += " Verified Yoast/Boost Rankers focus-keyword metadata was returned for WordPress content."
    if diagnostics:
        message += " " + " ".join(diagnostics)
    return inventory, focus_map, counts, message


async def _gsc_data(db: Session, company_id: str, site_url: str, days: int) -> tuple[bool, str | None, dict[str, dict[str, dict[str, float | None]]], str | None, str | None, str]:
    connection = get_connection(db, company_id, "search_console")
    if connection is None:
        return False, None, {}, None, None, "No active Google Search Console connection exists for this company. Connect Search Console in Google Integration."

    names = ("selected_property", "selected_search_console_property", "search_console_property", "property", "site_url")
    selected = None
    for name in names:
        value = getattr(connection, name, None)
        if isinstance(value, str) and value.strip():
            selected = value.strip()
            break
    for container_name in ("settings", "metadata", "config", "provider_data"):
        container = getattr(connection, container_name, None)
        if isinstance(container, dict) and not selected:
            for name in names:
                value = container.get(name)
                if isinstance(value, str) and value.strip():
                    selected = value.strip()
                    break

    try:
        token = await get_access_token(connection, db)
    except HTTPException as exc:
        return False, selected, {}, None, None, f"Google Search Console authorization is unavailable: {exc.detail}"
    except Exception as exc:
        logger.exception("GSC token acquisition failed")
        return False, selected, {}, None, None, f"Google Search Console token could not be obtained: {exc}"

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=60) as http:
        try:
            sites_response = await http.get(GSC_SITES_URL, headers=headers)
            if sites_response.status_code == 401:
                token = await get_access_token(connection, db)
                headers = {"Authorization": f"Bearer {token}"}
                sites_response = await http.get(GSC_SITES_URL, headers=headers)
            if sites_response.status_code >= 400:
                try:
                    detail = sites_response.json().get("error", {}).get("message")
                except Exception:
                    detail = None
                return False, selected, {}, None, None, detail or f"Search Console property lookup failed (HTTP {sites_response.status_code})."

            sites = [str(x.get("siteUrl")) for x in sites_response.json().get("siteEntry", []) if x.get("siteUrl")]
            client_key = _canonical_url_key(site_url)
            candidates = ([selected] if selected else []) + [x for x in sites if x != selected]
            matched = next((x for x in candidates if _canonical_url_key(x) == client_key), None)
            if not matched:
                host = urlparse(site_url).netloc.lower().lstrip("www.")
                matched = next((x for x in candidates if x.lower().startswith("sc-domain:") and x.split(":", 1)[1].lower().lstrip("www.") == host), None)
            if not matched:
                return False, selected, {}, None, None, f"No Search Console property matching {site_url} was found for the connected Google account."
            selected = matched

            end = datetime.now(UTC).date() - timedelta(days=3)
            start = end - timedelta(days=days - 1)
            encoded = quote(selected, safe="")
            url = GSC_SEARCH_ANALYTICS_URL.format(site_url=encoded)
            payload = {"startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": ["query", "page"], "rowLimit": 25000, "dataState": "all"}
            response = await http.post(url, headers=headers, json=payload)
            if response.status_code == 401:
                token = await get_access_token(connection, db)
                response = await http.post(url, headers={"Authorization": f"Bearer {token}"}, json=payload)
            if response.status_code >= 400:
                try:
                    message = response.json().get("error", {}).get("message")
                except Exception:
                    message = None
                return False, selected, {}, start.isoformat(), end.isoformat(), message or f"Search Analytics request failed (HTTP {response.status_code})."

            rows: dict[str, dict[str, dict[str, float | None]]] = defaultdict(dict)
            for row in response.json().get("rows", []):
                keys = row.get("keys") or []
                if len(keys) < 2:
                    continue
                query, page = str(keys[0]), str(keys[1])
                rows[query][page] = {"clicks": float(row.get("clicks", 0) or 0), "impressions": float(row.get("impressions", 0) or 0), "ctr": float(row.get("ctr", 0) or 0), "position": float(row.get("position")) if row.get("position") is not None else None}
            count = sum(len(v) for v in rows.values())
            if count == 0:
                return True, selected, rows, start.isoformat(), end.isoformat(), f"Search Console is connected to {selected}, but no query/page rows were returned for {start.isoformat()} through {end.isoformat()}."
            return True, selected, rows, start.isoformat(), end.isoformat(), f"Search Console connected: {count} query/page rows measured from {start.isoformat()} through {end.isoformat()}."
        except HTTPException as exc:
            return False, selected, {}, None, None, f"Google Search Console request failed: {exc.detail}"
        except Exception as exc:
            logger.exception("GSC conflict scan failed")
            return False, selected, {}, None, None, f"Google Search Console request failed: {exc}"


async def _run_scan(db: Session, scan: KeywordConflictScan, client: Client, payload: ScanRequest) -> None:
    scan.status = "running"
    scan.started_at = datetime.now(UTC)
    scan.last_activity_at = scan.started_at
    scan.progress_message = f"Starting crawl (up to {payload.max_pages} pages)…"
    db.commit()
    try:
        base_url = _safe_url(str(getattr(client, "website", "")))

        async def report_crawl_progress(pages_scanned: int, pages_discovered: int) -> None:
            # Keep a heartbeat during the crawl so a legitimate long crawl is
            # never mistaken for an abandoned scan.
            scan.pages_scanned = pages_scanned
            scan.pages_discovered = min(pages_discovered, payload.max_pages)
            scan.last_activity_at = datetime.now(UTC)
            scan.progress_message = f"Crawling website: {pages_scanned} pages scanned, {min(pages_discovered, payload.max_pages)} discovered…"
            db.commit()

        crawled_pages = await _crawl_site(base_url, payload.max_pages, report_crawl_progress)
        scan.pages_scanned = len(crawled_pages)
        scan.pages_discovered = max(len(crawled_pages), min(getattr(scan, "pages_discovered", 0) or 0, payload.max_pages))
        scan.last_activity_at = datetime.now(UTC)
        scan.progress_message = f"Crawl complete: {len(crawled_pages)} HTML URLs collected. Building WordPress Posts + Pages inventory…"
        db.commit()

        # IMPORTANT: WordPress Posts + Pages are inventoried independently of the
        # sitemap crawl limit. This prevents blog posts from being missed simply
        # because the crawler consumed max_pages on service/location URLs.
        focus_site = str(payload.wordpress_site).rstrip("/") if payload.wordpress_site else base_url
        wp_inventory, focus_map, wp_counts, wp_status_message = await _wordpress_content_inventory(
            focus_site,
            payload.wordpress_username,
            payload.wordpress_application_password,
            max_items_per_type=2000,
        )
        scan.wordpress_posts_found = wp_counts.get("posts", 0)
        scan.wordpress_pages_found = wp_counts.get("pages", 0)
        scan.wordpress_content_scanned = len(wp_inventory)
        scan.wordpress_status_message = wp_status_message
        scan.focus_status_message = wp_status_message

        # Merge WordPress content with crawler evidence. WP content is authoritative
        # for native posts/pages; non-WP/extra crawled URLs remain available as well.
        crawl_by_key = {_canonical_url_key(p["url"]): p for p in crawled_pages}
        merged: dict[str, dict[str, Any]] = {}
        for wp_page in wp_inventory:
            key = _canonical_url_key(wp_page["url"])
            crawl_page = crawl_by_key.get(key)
            if crawl_page:
                wp_page["canonical"] = crawl_page.get("canonical") or wp_page.get("canonical")
                wp_page["status_code"] = crawl_page.get("status_code", 200)
                wp_page["crawl_verified"] = True
            merged[key] = wp_page
        for crawl_page in crawled_pages:
            merged.setdefault(_canonical_url_key(crawl_page["url"]), crawl_page)
        pages = list(merged.values())

        scan.pages_scanned = len(pages)
        scan.pages_discovered = max(scan.pages_discovered or 0, len(pages))
        scan.last_activity_at = datetime.now(UTC)
        scan.progress_message = f"Content inventory complete: {wp_counts.get('posts', 0)} posts + {wp_counts.get('pages', 0)} pages + {len(crawled_pages)} crawled URLs. Checking Search Console…"
        db.commit()


        gsc_connected = False
        property_url = None
        gsc_rows: dict[str, dict[str, dict[str, float | None]]] = {}
        date_start = date_end = None
        if payload.include_gsc:
            gsc_connected, property_url, gsc_rows, date_start, date_end, gsc_status_message = await _gsc_data(db, scan.company_id, base_url, payload.days)

        scan.gsc_connected = gsc_connected
        scan.measurement_property = property_url
        scan.date_start = date_start
        scan.date_end = date_end
        scan.gsc_status_message = gsc_status_message if payload.include_gsc else "Google Search Console evidence was not requested for this scan."
        if payload.include_gsc and gsc_connected:
            measured_rows = sum(len(url_rows) for url_rows in gsc_rows.values())
            scan.gsc_rows_measured = measured_rows
            scan.gsc_status_message = f"{gsc_status_message} Matched {measured_rows} measured query/page rows to crawled pages."
        scan.last_activity_at = datetime.now(UTC)
        scan.progress_message = "Search Console check complete. Computing conflict signals…"
        db.commit()

        # Page-level evidence.
        gsc_rows_measured = sum(len(url_rows) for url_rows in gsc_rows.values())
        page_by_url: dict[str, dict[str, Any]] = {}
        focus_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        stuffing_count = 0
        for page in pages:
            url = page["url"]
            focus = (
                focus_map.get(url)
                or focus_map.get(url.rstrip("/"))
                or focus_map.get(_canonical_url_key(url))
            )
            freq = _keyword_frequency(page["body"], focus or "")
            stuffing = _stuffing_risk(freq, page["word_count"])
            if stuffing >= 55:
                stuffing_count += 1
            evidence = {
                "source": "crawler_verified",
                "status_code": page["status_code"],
                "title": page["title"],
                "h1": page["h1"],
                "canonical": page["canonical"],
                "word_count": page["word_count"],
                "focus_keyword_source": "wordpress_yoast" if url in focus_map or url.rstrip("/") in focus_map else ("rank_tracker_fallback" if focus else None),
                "content_type": page.get("page_type", "page"),
                "wordpress_source": bool(page.get("wordpress_source")),
                "wordpress_id": page.get("wordpress_id"),
                "wordpress_content_type": page.get("wordpress_content_type"),
                "crawl_verified": bool(page.get("crawl_verified")),
            }
            row = KeywordConflictPage(
                scan_id=scan.id,
                company_id=scan.company_id,
                client_id=scan.client_id,
                url=url,
                title=page["title"][:1000],
                h1=page["h1"][:1000],
                canonical=page["canonical"][:2000],
                word_count=page["word_count"],
                focus_keyword=focus[:500] if focus else None,
                keyword_frequency=freq,
                stuffing_risk=stuffing,
                gsc_primary_query=None,
                gsc_query_impressions=0,
                gsc_query_clicks=0,
                gsc_query_position=None,
                page_type=page["page_type"],
                evidence=evidence,
            )
            db.add(row)
            page["focus_keyword"] = focus
            page["keyword_frequency"] = freq
            page["stuffing_risk"] = stuffing
            page_by_url[url] = page
            page_by_url[_canonical_url_key(url)] = page
            if focus:
                focus_groups[_normalize(focus)].append(page)
        db.commit()

        # GSC query -> URL groups provide the strongest non-causal cannibalization signal.
        query_url_groups: dict[str, list[str]] = {}
        normalized_gsc_rows: dict[str, dict[str, dict[str, float | None]]] = defaultdict(dict)
        for query, url_rows in gsc_rows.items():
            for gsc_url, metrics in url_rows.items():
                page = page_by_url.get(gsc_url) or page_by_url.get(_canonical_url_key(gsc_url))
                if page:
                    normalized_gsc_rows[query][page["url"]] = metrics
        gsc_rows = normalized_gsc_rows

        # Attach the strongest measured Search Console query to each crawled page.
        # This is explicitly GSC-derived evidence, not a WordPress/Yoast focus keyword.
        for url, page in list(page_by_url.items()):
            if not url or url != page.get("url"):
                continue
            candidates_for_page = []
            for query, url_rows in gsc_rows.items():
                metrics = url_rows.get(page["url"])
                if metrics and float(metrics.get("impressions", 0) or 0) > 0:
                    candidates_for_page.append((
                        float(metrics.get("impressions", 0) or 0),
                        float(metrics.get("clicks", 0) or 0),
                        query,
                        metrics,
                    ))
            if candidates_for_page:
                _, _, top_query, top_metrics = max(candidates_for_page, key=lambda x: (x[0], x[1]))
                page["gsc_primary_query"] = top_query
                page["gsc_query_impressions"] = float(top_metrics.get("impressions", 0) or 0)
                page["gsc_query_clicks"] = float(top_metrics.get("clicks", 0) or 0)
                page["gsc_query_position"] = top_metrics.get("position")

        # Load the persisted page-evidence rows before updating their derived
        # keyword metrics.  The previous implementation referenced page_rows
        # before it was initialized, which caused:
        #   cannot access local variable 'page_rows' where it is not associated with a value
        # Keep this query here so the scan can continue into conflict analysis.
        page_rows = db.query(KeywordConflictPage).filter(KeywordConflictPage.scan_id == scan.id).all()
        page_rows_by_url = {row.url: row for row in page_rows}

        # Recalculate page-level over-optimization using verified focus keywords
        # first, then a measured GSC primary query when no focus keyword exists.
        # This keeps the stuffing detector useful without mislabeling GSC queries as Yoast focus keywords.
        stuffing_count = 0
        for page in pages:
            target_keyword = page.get("focus_keyword") or page.get("gsc_primary_query") or ""
            freq = _keyword_frequency(page["body"], target_keyword)
            stuffing = _stuffing_risk(freq, page["word_count"])
            page["keyword_frequency"] = freq
            page["stuffing_risk"] = stuffing
            if stuffing >= 55:
                stuffing_count += 1
            row = page_rows_by_url.get(page["url"])
            if row:
                row.keyword_frequency = freq
                row.stuffing_risk = stuffing
                row.evidence = {
                    **(row.evidence or {}),
                    "keyword_frequency_basis": "verified_focus_keyword" if page.get("focus_keyword") else ("gsc_primary_query" if page.get("gsc_primary_query") else None),
                }

        for query, url_rows in gsc_rows.items():
            usable = [
                u for u, metrics in url_rows.items()
                if float(metrics.get("impressions", 0) or 0) > 0 and u in page_by_url
            ]
            if len(usable) >= 2:
                query_url_groups[query] = usable

        # Persist GSC-derived top-query evidence on the corresponding page rows.
        page_lookup = {row.url: row for row in page_rows}
        for page in pages:
            row = page_lookup.get(page["url"])
            if row:
                row.gsc_primary_query = page.get("gsc_primary_query")
                row.gsc_query_impressions = float(page.get("gsc_query_impressions", 0) or 0)
                row.gsc_query_clicks = float(page.get("gsc_query_clicks", 0) or 0)
                row.gsc_query_position = page.get("gsc_query_position")
                if row.evidence is None:
                    row.evidence = {}
                row.evidence = {**row.evidence, "gsc_primary_query": page.get("gsc_primary_query")}

        gsc_shared_query_count = len(query_url_groups)
        candidate_pairs: set[tuple[str, str]] = set()
        for pages_for_keyword in focus_groups.values():
            for i in range(len(pages_for_keyword)):
                for j in range(i + 1, len(pages_for_keyword)):
                    a, b = pages_for_keyword[i]["url"], pages_for_keyword[j]["url"]
                    candidate_pairs.add(tuple(sorted((a, b))))
        for urls in query_url_groups.values():
            for i in range(len(urls)):
                for j in range(i + 1, len(urls)):
                    candidate_pairs.add(tuple(sorted((urls[i], urls[j]))))

        # Add semantically similar title/H1 pairs without doing a full O(n²) scan.
        ranked_pages = sorted(pages, key=lambda p: (len(_tokens(p["title"] + " " + p["h1"])), p["word_count"]), reverse=True)
        for i, a in enumerate(ranked_pages):
            for b in ranked_pages[i + 1:i + 31]:
                if _similarity(a["title"] + " " + a["h1"], b["title"] + " " + b["h1"]) >= 0.42:
                    candidate_pairs.add(tuple(sorted((a["url"], b["url"]))))

        conflicts = 0
        for url_a, url_b in candidate_pairs:
            a, b = page_by_url.get(url_a), page_by_url.get(url_b)
            if not a or not b:
                continue
            kw_a = a.get("focus_keyword") or ""
            kw_b = b.get("focus_keyword") or ""
            kw_similarity = _similarity(kw_a, kw_b)
            exact_focus = bool(kw_a and kw_b and _normalize(kw_a) == _normalize(kw_b))
            title_similarity = _similarity(a["title"] + " " + a["h1"], b["title"] + " " + b["h1"])
            content_similarity = _similarity(a["body"][:60000], b["body"][:60000])

            shared_queries: list[dict[str, Any]] = []
            total_shared_impressions = 0.0
            for query, url_rows in gsc_rows.items():
                ma, mb = url_rows.get(url_a), url_rows.get(url_b)
                if not ma or not mb:
                    continue
                if float(ma.get("impressions", 0) or 0) <= 0 and float(mb.get("impressions", 0) or 0) <= 0:
                    continue
                shared = {
                    "query": query,
                    "primary": ma,
                    "competing": mb,
                }
                shared_queries.append(shared)
                total_shared_impressions += float(ma.get("impressions", 0) or 0) + float(mb.get("impressions", 0) or 0)
            shared_queries.sort(key=lambda x: (float(x["primary"].get("impressions", 0) or 0) + float(x["competing"].get("impressions", 0) or 0)), reverse=True)
            # Normalize shared-query overlap so 1-5+ measured shared queries
            # produce a useful signal without treating every overlap as a conflict.
            gsc_overlap = min(1.0, len(shared_queries) / 5.0)
            combined_shared_impressions = sum(
                float(x["primary"].get("impressions", 0) or 0) +
                float(x["competing"].get("impressions", 0) or 0)
                for x in shared_queries
            )
            close_ranking_queries = sum(
                1 for x in shared_queries
                if x["primary"].get("position") is not None
                and x["competing"].get("position") is not None
                and max(float(x["primary"]["position"]), float(x["competing"]["position"])) <= 30
                and abs(float(x["primary"]["position"]) - float(x["competing"]["position"])) <= 10
            )
            gsc_signal = bool(
                len(shared_queries) >= 2
                or (len(shared_queries) >= 1 and combined_shared_impressions >= 20)
                or close_ranking_queries >= 1
            )

            # URL alternation signal: both URLs have meaningful impressions and
            # neither is clearly dominant for several shared queries.
            switch_count = 0
            for item in shared_queries[:30]:
                pa, pb = item["primary"].get("position"), item["competing"].get("position")
                if pa and pb and abs(float(pa) - float(pb)) <= 5:
                    switch_count += 1
            ranking_displacement = min(1.0, switch_count / 5.0)
            canonical_conflict = _normalize(a.get("canonical")) == _normalize(url_b) or _normalize(b.get("canonical")) == _normalize(url_a)
            anchor_overlap = _similarity(" ".join(a.get("anchors", [])), " ".join(b.get("anchors", [])))

            score = 0.0
            if exact_focus:
                score += 30
            elif kw_similarity >= 0.65:
                score += 18
            elif kw_similarity >= 0.45:
                score += 10
            if title_similarity >= 0.65:
                score += 15
            elif title_similarity >= 0.45:
                score += 8
            if content_similarity >= 0.70:
                score += 20
            elif content_similarity >= 0.50:
                score += 12
            if gsc_overlap:
                score += min(25, gsc_overlap * 25)
            if gsc_signal:
                score += 10
            if len(shared_queries) >= 3:
                score += 8
            if close_ranking_queries >= 1:
                score += 5
            if ranking_displacement:
                score += min(10, ranking_displacement * 10)
            if canonical_conflict:
                score += 15
            if anchor_overlap >= 0.60:
                score += 5

            # Avoid noise: a pair needs meaningful evidence from at least one
            # strong signal before being shown as a conflict.
            strong = exact_focus or gsc_signal or content_similarity >= 0.65 or title_similarity >= 0.70 or canonical_conflict
            if not strong or score < 25:
                continue

            primary, competing = a, b
            # Prefer the URL with stronger GSC visibility as the primary page.
            if shared_queries:
                def visibility(purl: str) -> float:
                    return sum(float(x.get(purl, {}).get("impressions", 0) or 0) for x in gsc_rows.values())
                if visibility(url_b) > visibility(url_a):
                    primary, competing = b, a
            keyword = kw_a or kw_b or (shared_queries[0]["query"] if shared_queries else "")
            evidence = {
                "evidence_class": "derived_metric",
                "exact_focus_keyword": exact_focus,
                "focus_keyword_primary": primary.get("focus_keyword"),
                "focus_keyword_competing": competing.get("focus_keyword"),
                "primary_content_type": primary.get("page_type", "page"),
                "competing_content_type": competing.get("page_type", "page"),
                "primary_wordpress_id": primary.get("wordpress_id"),
                "competing_wordpress_id": competing.get("wordpress_id"),
                "primary_wordpress_source": bool(primary.get("wordpress_source")),
                "competing_wordpress_source": bool(competing.get("wordpress_source")),
                "title_similarity": round(title_similarity, 3),
                "content_similarity": round(content_similarity, 3),
                "keyword_similarity": round(kw_similarity, 3),
                "gsc_overlap": round(gsc_overlap, 3),
                "ranking_displacement": round(ranking_displacement, 3),
                "url_switch_signal": ranking_displacement > 0,
                "canonical_conflict": canonical_conflict,
                "anchor_similarity": round(anchor_overlap, 3),
                "shared_queries": shared_queries[:20],
                "interpretation": "Potential ranking conflict; this does not prove that one URL caused another URL to lose rankings.",
            }
            recommendation = _recommendation({**evidence, "content_similarity": content_similarity, "gsc_overlap": gsc_overlap})
            conflict = KeywordConflict(
                scan_id=scan.id,
                company_id=scan.company_id,
                client_id=scan.client_id,
                keyword=keyword[:500] or "Unassigned query overlap",
                normalized_keyword=_normalize(keyword)[:500] or "unassigned-query-overlap",
                primary_url=primary["url"],
                competing_url=competing["url"],
                conflict_score=min(100.0, round(score, 1)),
                risk_level=_risk(score),
                intent_similarity=max(kw_similarity, title_similarity),
                content_similarity=content_similarity,
                gsc_overlap=gsc_overlap,
                ranking_displacement=ranking_displacement,
                recommendation=recommendation,
                evidence=evidence,
            )
            db.add(conflict)
            db.flush()
            for shared in shared_queries[:20]:
                ma, mb = shared["primary"], shared["competing"]
                # Save metrics against the stored primary/competing ordering.
                pm = gsc_rows[shared["query"]].get(primary["url"], {})
                cm = gsc_rows[shared["query"]].get(competing["url"], {})
                db.add(KeywordConflictQuery(
                    conflict_id=conflict.id,
                    company_id=scan.company_id,
                    query=shared["query"][:1000],
                    primary_url=primary["url"],
                    competing_url=competing["url"],
                    primary_clicks=float(pm.get("clicks", 0) or 0),
                    primary_impressions=float(pm.get("impressions", 0) or 0),
                    primary_position=pm.get("position"),
                    competing_clicks=float(cm.get("clicks", 0) or 0),
                    competing_impressions=float(cm.get("impressions", 0) or 0),
                    competing_position=cm.get("position"),
                    url_switch_signal=ranking_displacement > 0,
                ))
            conflicts += 1
        db.commit()

        scan.pages_scanned = len(pages)
        scan.wordpress_content_scanned = scan.wordpress_posts_found + scan.wordpress_pages_found
        scan.focus_keywords_found = sum(1 for p in pages if p.get("focus_keyword"))
        scan.repeated_focus_keywords = sum(1 for group in focus_groups.values() if len(group) > 1)
        scan.stuffing_warnings = stuffing_count
        scan.conflicts_found = conflicts
        scan.gsc_rows_measured = gsc_rows_measured
        scan.gsc_shared_queries = gsc_shared_query_count
        scan.gsc_candidate_pairs = len(candidate_pairs)
        scan.status = "completed"
        scan.completed_at = datetime.now(UTC)
        scan.last_activity_at = scan.completed_at
        scan.progress_message = "Scan completed successfully."
        db.commit()
    except Exception as exc:
        logger.exception("Keyword conflict scan failed")
        db.rollback()
        scan.status = "failed"
        scan.error_message = str(exc)[:2000]
        scan.progress_message = "Scan failed. See the error details."
        scan.last_activity_at = datetime.now(UTC)
        scan.completed_at = datetime.now(UTC)
        db.add(scan)
        db.commit()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.on_event("startup")
def ensure_keyword_conflict_tables() -> None:
    KeywordConflictScan.__table__.create(bind=engine, checkfirst=True)
    KeywordConflict.__table__.create(bind=engine, checkfirst=True)
    KeywordConflictPage.__table__.create(bind=engine, checkfirst=True)
    KeywordConflictQuery.__table__.create(bind=engine, checkfirst=True)
    # IMPORTANT: Do not execute ALTER TABLE ... IF NOT EXISTS blindly on every
    # application startup. PostgreSQL still needs an ACCESS EXCLUSIVE lock for
    # ALTER TABLE even when the column already exists. On Supabase/managed
    # PostgreSQL this can block behind another transaction and hit the database
    # statement_timeout, preventing the whole FastAPI application from starting.
    #
    # We first inspect information_schema (read-only), and only issue ALTER TABLE
    # for columns that are genuinely missing. Each missing-column migration is
    # isolated so one locked optional migration cannot take down the application.
    column_migrations = (
        ("keyword_conflict_scans", "progress_message", "VARCHAR(1000)"),
        ("keyword_conflict_scans", "pages_discovered", "INTEGER NOT NULL DEFAULT 0"),
        ("keyword_conflict_scans", "last_activity_at", "TIMESTAMPTZ"),
        ("keyword_conflict_scans", "gsc_status_message", "VARCHAR(2000)"),
        ("keyword_conflict_scans", "focus_status_message", "VARCHAR(2000)"),
        ("keyword_conflict_scans", "gsc_rows_measured", "INTEGER NOT NULL DEFAULT 0"),
        ("keyword_conflict_scans", "gsc_shared_queries", "INTEGER NOT NULL DEFAULT 0"),
        ("keyword_conflict_scans", "gsc_candidate_pairs", "INTEGER NOT NULL DEFAULT 0"),
        ("keyword_conflict_scans", "wordpress_posts_found", "INTEGER NOT NULL DEFAULT 0"),
        ("keyword_conflict_scans", "wordpress_pages_found", "INTEGER NOT NULL DEFAULT 0"),
        ("keyword_conflict_scans", "wordpress_content_scanned", "INTEGER NOT NULL DEFAULT 0"),
        ("keyword_conflict_scans", "wordpress_status_message", "VARCHAR(2000)"),
        ("keyword_conflict_pages", "gsc_primary_query", "VARCHAR(1000)"),
        ("keyword_conflict_pages", "gsc_query_impressions", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
        ("keyword_conflict_pages", "gsc_query_clicks", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
        ("keyword_conflict_pages", "gsc_query_position", "DOUBLE PRECISION"),
    )

    try:
        with engine.connect() as connection:
            existing = set(
                connection.execute(
                    text(
                        """
                        SELECT table_name, column_name
                        FROM information_schema.columns
                        WHERE table_schema = current_schema()
                          AND table_name IN ('keyword_conflict_scans', 'keyword_conflict_pages')
                        """
                    )
                ).fetchall()
            )
    except Exception:
        # Schema discovery must never prevent the application from starting.
        logger.exception("Keyword Conflict schema inspection failed; continuing startup.")
        existing = set()

    for table_name, column_name, column_definition in column_migrations:
        if (table_name, column_name) in existing:
            continue

        # A missing column is an installation/migration concern, not a reason to
        # crash the entire API. Use a short lock timeout so startup remains
        # responsive when another transaction currently holds the table lock.
        try:
            with engine.begin() as connection:
                connection.execute(text("SET LOCAL lock_timeout = '3000ms'"))
                connection.execute(
                    text(
                        f'ALTER TABLE "{table_name}" '
                        f'ADD COLUMN "{column_name}" {column_definition}'
                    )
                )
        except OperationalError as exc:
            logger.warning(
                "Could not add optional Keyword Conflict column %s.%s during startup: %s. "
                "The application will continue; retry the migration on the next restart.",
                table_name,
                column_name,
                exc,
            )
        except Exception:
            logger.exception(
                "Unexpected error adding Keyword Conflict column %s.%s; continuing startup.",
                table_name,
                column_name,
            )


@router.get("/overview")
def overview(client_id: str | None = Query(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)

    def _read(session: Session) -> dict[str, Any]:
        query = session.query(KeywordConflictScan).filter(
            KeywordConflictScan.company_id == company_id,
            KeywordConflictScan.deleted_at.is_(None),
        )
        if client_id:
            query = query.filter(KeywordConflictScan.client_id == client_id)
        latest = query.order_by(KeywordConflictScan.created_at.desc()).first()
        if not latest:
            return {"has_scan": False, "scan": None, "metrics": {"conflicts": 0, "high_risk": 0, "repeated_focus_keywords": 0, "stuffing_warnings": 0}}
        high = session.query(KeywordConflict).filter(
            KeywordConflict.scan_id == latest.id,
            KeywordConflict.risk_level == "high",
            KeywordConflict.deleted_at.is_(None),
        ).count()
        return {
            "has_scan": True,
            "scan": _serialize_scan(latest),
            "metrics": {
                "conflicts": latest.conflicts_found,
                "high_risk": high,
                "repeated_focus_keywords": latest.repeated_focus_keywords,
                "stuffing_warnings": latest.stuffing_warnings,
            },
        }

    return _run_db_read_with_recovery(db, _read)


@router.get("")
def list_conflicts(client_id: str | None = Query(None), risk: str | None = Query(None), status_filter: str | None = Query(None, alias="status"), scan_id: str | None = Query(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)

    def _read(session: Session) -> dict[str, Any]:
        q = session.query(KeywordConflict).filter(
            KeywordConflict.company_id == company_id,
            KeywordConflict.deleted_at.is_(None),
        )
        if client_id:
            q = q.filter(KeywordConflict.client_id == client_id)
        if risk:
            q = q.filter(KeywordConflict.risk_level == risk)
        if status_filter:
            q = q.filter(KeywordConflict.status == status_filter)
        if scan_id:
            q = q.filter(KeywordConflict.scan_id == scan_id)
        else:
            latest_scan = (
                session.query(KeywordConflictScan.id)
                .filter(
                    KeywordConflictScan.company_id == company_id,
                    KeywordConflictScan.deleted_at.is_(None),
                    *([KeywordConflictScan.client_id == client_id] if client_id else []),
                )
                .order_by(KeywordConflictScan.created_at.desc())
                .first()
            )
            if latest_scan:
                q = q.filter(KeywordConflict.scan_id == latest_scan[0])
        rows = q.order_by(KeywordConflict.conflict_score.desc(), KeywordConflict.created_at.desc()).limit(500).all()
        return {"conflicts": [_serialize_conflict(row) for row in rows]}

    return _run_db_read_with_recovery(db, _read)

@router.get("/pages")
def list_pages(client_id: str | None = Query(None), scan_id: str | None = Query(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)

    def _read(session: Session) -> dict[str, Any]:
        q = session.query(KeywordConflictPage).filter(KeywordConflictPage.company_id == company_id, KeywordConflictPage.deleted_at.is_(None))
        if client_id:
            q = q.filter(KeywordConflictPage.client_id == client_id)
        if scan_id:
            q = q.filter(KeywordConflictPage.scan_id == scan_id)
        else:
            latest_scan = (
                session.query(KeywordConflictScan.id)
                .filter(
                    KeywordConflictScan.company_id == company_id,
                    KeywordConflictScan.deleted_at.is_(None),
                    *([KeywordConflictScan.client_id == client_id] if client_id else []),
                )
                .order_by(KeywordConflictScan.created_at.desc())
                .first()
            )
            if latest_scan:
                q = q.filter(KeywordConflictPage.scan_id == latest_scan[0])
        rows = q.order_by(KeywordConflictPage.stuffing_risk.desc(), KeywordConflictPage.created_at.desc()).limit(1000).all()
        return {"pages": [{
            "id": x.id, "url": x.url, "title": x.title, "h1": x.h1, "canonical": x.canonical,
            "word_count": x.word_count, "focus_keyword": x.focus_keyword, "keyword_frequency": x.keyword_frequency,
            "stuffing_risk": x.stuffing_risk, "gsc_primary_query": x.gsc_primary_query,
            "gsc_query_impressions": x.gsc_query_impressions, "gsc_query_clicks": x.gsc_query_clicks,
            "gsc_query_position": x.gsc_query_position, "page_type": x.page_type, "evidence": x.evidence,
        } for x in rows]}

    return _run_db_read_with_recovery(db, _read)

@router.get("/scans")
def list_scans(client_id: str | None = Query(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)

    def _read(session: Session) -> dict[str, Any]:
        q = session.query(KeywordConflictScan).filter(KeywordConflictScan.company_id == company_id, KeywordConflictScan.deleted_at.is_(None))
        if client_id:
            q = q.filter(KeywordConflictScan.client_id == client_id)
        rows = q.order_by(KeywordConflictScan.created_at.desc()).limit(50).all()
        return {"scans": [_serialize_scan(x) for x in rows]}

    return _run_db_read_with_recovery(db, _read)

@router.get("/{conflict_id}")
def get_conflict(conflict_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)

    def _read(session: Session) -> dict[str, Any]:
        row = session.query(KeywordConflict).filter(
            KeywordConflict.id == conflict_id,
            KeywordConflict.company_id == company_id,
            KeywordConflict.deleted_at.is_(None),
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail="Keyword conflict not found.")
        queries = (
            session.query(KeywordConflictQuery)
            .filter(KeywordConflictQuery.conflict_id == row.id, KeywordConflictQuery.deleted_at.is_(None))
            .order_by(KeywordConflictQuery.primary_impressions.desc())
            .all()
        )
        payload = _serialize_conflict(row)
        payload["queries"] = [{
            "id": q.id, "query": q.query, "primary_url": q.primary_url, "competing_url": q.competing_url,
            "primary_clicks": q.primary_clicks, "primary_impressions": q.primary_impressions,
            "primary_position": q.primary_position, "competing_clicks": q.competing_clicks,
            "competing_impressions": q.competing_impressions, "competing_position": q.competing_position,
            "url_switch_signal": q.url_switch_signal,
        } for q in queries]
        return payload

    return _run_db_read_with_recovery(db, _read)

@router.post("/scan", status_code=status.HTTP_202_ACCEPTED)
async def start_scan(payload: ScanRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)
    client = db.query(Client).filter(Client.id == payload.client_id, Client.company_id == company_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found in your company.")
    if not getattr(client, "website", None):
        raise HTTPException(status_code=400, detail="The selected client does not have a website URL.")

    active_scan = db.query(KeywordConflictScan).filter(
        KeywordConflictScan.company_id == company_id,
        KeywordConflictScan.client_id == client.id,
        KeywordConflictScan.status.in_(["queued", "running"]),
        KeywordConflictScan.deleted_at.is_(None),
    ).first()
    if active_scan:
        last_activity = getattr(active_scan, "last_activity_at", None) or active_scan.started_at
        if last_activity and last_activity < datetime.now(UTC) - timedelta(minutes=30):
            active_scan.status = "failed"
            active_scan.error_message = "Previous scan became inactive and was safely marked failed before starting a new scan."
            active_scan.progress_message = "Previous scan timed out due to inactivity."
            active_scan.completed_at = datetime.now(UTC)
            active_scan.last_activity_at = active_scan.completed_at
            db.add(active_scan)
            db.commit()
            active_scan = None
    if active_scan:
        return {"success": True, "scan": _serialize_scan(active_scan), "message": "A keyword conflict scan is already running for this client."}

    now = datetime.now(UTC)
    scan = KeywordConflictScan(
        company_id=company_id,
        client_id=client.id,
        status="queued",
        created_by=str(current_user.id),
        updated_by=str(current_user.id),
        last_activity_at=now,
        progress_message="Scan queued. Preparing the website crawl…",
        pages_scanned=0,
        pages_discovered=0,
        gsc_status_message="Google Search Console check pending…" if payload.include_gsc else "Google Search Console evidence was not requested for this scan.",
        focus_status_message="Focus-keyword evidence check queued automatically…",
        gsc_rows_measured=0,
        gsc_shared_queries=0,
        gsc_candidate_pairs=0,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    # Background task is deliberately local and bounded. It avoids holding the
    # request's DB session during crawling and keeps existing SSE audit sessions untouched.
    asyncio.create_task(_run_scan_background(scan.id, payload, company_id, client.id))
    return {"success": True, "scan": _serialize_scan(scan), "message": "Keyword conflict scan started."}


async def _run_scan_background(scan_id: str, payload: ScanRequest, company_id: str, client_id: str) -> None:
    # A fresh DB session prevents long-running scans from consuming the request pool.
    db = SessionLocal()
    try:
        scan = db.query(KeywordConflictScan).filter(KeywordConflictScan.id == scan_id, KeywordConflictScan.company_id == company_id).first()
        client = db.query(Client).filter(Client.id == client_id, Client.company_id == company_id).first()
        if not scan or not client:
            return
        await _run_scan(db, scan, client, payload)
    finally:
        try:
            db.close()
        except Exception:
            logger.warning("Keyword conflict scan DB session cleanup failed", exc_info=True)


async def _wordpress_find_page_by_url(
    site: str,
    target_url: str,
    username: str,
    password: str,
) -> dict[str, Any] | None:
    """Find the real published WordPress post/page without relying on a large REST scan.

    Resolution is performed against the authenticated WordPress REST API. We first try
    the exact URL slug (fast path), then use a small bounded fallback scan. This avoids
    long ``per_page=100`` responses that can trigger httpx ReadTimeout on slower/shared
    WordPress hosting. The public URL is still verified before a page is returned.
    """
    site = site.rstrip("/")
    target_key = _canonical_url_key(target_url)
    parsed = urlparse(target_url)
    path_parts = [part for part in parsed.path.split("/") if part]
    slug = path_parts[-1] if path_parts else ""
    # WordPress slugs are normally URL-decoded in the REST API; try both forms.
    slug_candidates = []
    for candidate in (slug, quote(slug, safe="")):
        if candidate and candidate not in slug_candidates:
            slug_candidates.append(candidate)

    auth = (username, password)
    headers = {
        "User-Agent": "BoostRankers-KeywordConflictResolver/2.1",
        "Accept": "application/json",
    }
    timeout = httpx.Timeout(60.0, connect=15.0, read=45.0, write=15.0, pool=15.0)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, auth=auth, headers=headers) as http:
        try:
            me = await http.get(
                f"{site}/wp-json/wp/v2/users/me",
                params={"context": "edit", "_fields": "id"},
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail="WordPress authentication timed out. The WordPress REST API did not respond within 45 seconds. Check that /wp-json/wp/v2 is accessible and try again.",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Could not connect to WordPress REST API: {exc}",
            ) from exc

        if me.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="WordPress authentication failed. Check the username and Application Password.")
        if me.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"WordPress authentication check returned HTTP {me.status_code}.")

        fields = "id,link,title,content,excerpt,slug,status"

        # Fast path: ask WordPress for the exact slug instead of downloading hundreds
        # of posts/pages. Canonical URL verification below prevents false positives.
        if slug_candidates:
            for content_type in ("posts", "pages"):
                for slug_value in slug_candidates:
                    try:
                        response = await http.get(
                            f"{site}/wp-json/wp/v2/{content_type}",
                            params={
                                "slug": slug_value,
                                "per_page": 10,
                                "status": "publish",
                                "context": "edit",
                                "_fields": fields,
                            },
                        )
                    except httpx.TimeoutException as exc:
                        raise HTTPException(
                            status_code=504,
                            detail=f"WordPress {content_type} lookup timed out while resolving the URL. Try again or verify that the WordPress REST API is responsive.",
                        ) from exc
                    except httpx.RequestError as exc:
                        raise HTTPException(
                            status_code=502,
                            detail=f"Could not connect to the WordPress {content_type} endpoint: {exc}",
                        ) from exc

                    if response.status_code in (400, 404):
                        continue
                    if response.status_code in (401, 403):
                        raise HTTPException(status_code=403, detail=f"WordPress denied authenticated access to {content_type}.")
                    if response.status_code >= 500:
                        raise HTTPException(status_code=502, detail=f"WordPress {content_type} lookup failed with HTTP {response.status_code}.")
                    if response.status_code >= 400:
                        continue

                    try:
                        items = response.json()
                    except ValueError as exc:
                        raise HTTPException(status_code=502, detail=f"WordPress returned invalid JSON for the {content_type} lookup.") from exc

                    if not isinstance(items, list):
                        continue
                    for item in items:
                        link = str(item.get("link") or "")
                        if link and _canonical_url_key(link) == target_key:
                            return {**item, "content_type": content_type}

        # Bounded fallback for installations whose REST API does not support slug
        # filtering correctly. Keep responses deliberately small.
        for content_type in ("posts", "pages"):
            for page_num in range(1, 6):
                try:
                    response = await http.get(
                        f"{site}/wp-json/wp/v2/{content_type}",
                        params={
                            "per_page": 20,
                            "page": page_num,
                            "status": "publish",
                            "context": "edit",
                            "_fields": fields,
                        },
                    )
                except httpx.TimeoutException as exc:
                    raise HTTPException(
                        status_code=504,
                        detail=f"WordPress {content_type} fallback lookup timed out. The REST API is responding too slowly to safely resolve this page.",
                    ) from exc
                except httpx.RequestError as exc:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Could not connect to the WordPress {content_type} endpoint: {exc}",
                    ) from exc

                if response.status_code in (400, 404):
                    break
                if response.status_code in (401, 403):
                    raise HTTPException(status_code=403, detail=f"WordPress denied authenticated access to {content_type}.")
                if response.status_code >= 500:
                    raise HTTPException(status_code=502, detail=f"WordPress {content_type} lookup failed with HTTP {response.status_code}.")
                if response.status_code >= 400:
                    break

                try:
                    items = response.json()
                except ValueError as exc:
                    raise HTTPException(status_code=502, detail=f"WordPress returned invalid JSON for the {content_type} fallback lookup.") from exc

                if not isinstance(items, list) or not items:
                    break
                for item in items:
                    link = str(item.get("link") or "")
                    if link and _canonical_url_key(link) == target_key:
                        return {**item, "content_type": content_type}
                if len(items) < 20:
                    break

    return None


def _extract_claude_text(response: Any) -> str:
    return "".join(block.text for block in getattr(response, "content", []) if hasattr(block, "text")).strip()


def _parse_claude_json(text_value: str) -> dict[str, Any]:
    raw = text_value.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise ValueError("Claude did not return valid JSON for the website resolution plan.")
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Claude returned an invalid website resolution plan.")
    return payload


def _normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _strip_html_for_match(value: str) -> str:
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


def _text_nodes_in_document(soup: BeautifulSoup) -> list[Any]:
    nodes = []
    for node in soup.find_all(string=True):
        if node.parent and node.parent.name in {"script", "style", "noscript"}:
            continue
        if str(node).strip():
            nodes.append(node)
    return nodes


def _normalized_node_text(value: str) -> str:
    return _normalize_ws(value)


def _apply_cross_node_text_replacement(soup: BeautifulSoup, find_text: str, replace_text: str) -> bool:
    """Replace one unique visible-text span even when WordPress split it across tags.

    Only text nodes are changed. Existing links, images, embeds and surrounding markup
    are preserved. The replacement is accepted only when the normalized visible text
    occurs exactly once in the document and its start/end are attributable to text nodes.
    """
    target = _normalize_ws(_strip_html_for_match(find_text))
    if not target:
        return False
    nodes = _text_nodes_in_document(soup)
    if not nodes:
        return False

    # Build a searchable normalized document while retaining a mapping back to nodes.
    # Whitespace runs are represented by a single space, matching _normalize_ws().
    pieces = []
    spans = []
    cursor = 0
    previous_had_text = False
    for node in nodes:
        raw = str(node)
        norm = _normalize_ws(raw)
        if not norm:
            continue
        if pieces:
            pieces.append(" ")
            cursor += 1
        begin = cursor
        pieces.append(norm)
        cursor += len(norm)
        spans.append((begin, cursor, node, norm))
    document = "".join(pieces)
    if document.count(target) != 1:
        return False
    match_start = document.index(target)
    match_end = match_start + len(target)

    covered = [x for x in spans if x[1] > match_start and x[0] < match_end]
    if not covered:
        return False

    # Refuse replacements that would cross an existing anchor/media boundary unless the
    # replacement is wholly inside one text node. This keeps the operation conservative.
    if len(covered) == 1:
        node = covered[0][2]
        original = str(node)
        pattern = re.compile(r"\s+".join(re.escape(part) for part in target.split()))
        if not pattern.search(original):
            return False
        node.replace_with(pattern.sub(replace_text, original, count=1))
        return True

    # For multi-node text, require the nodes to be contiguous in document text and make
    # sure none sits inside an <a>. We replace the matched portions while preserving tags.
    if any(n.parent and n.parent.name == "a" for _, _, n, _ in covered):
        return False

    first = covered[0]
    last = covered[-1]
    first_start = max(0, match_start - first[0])
    last_end = min(len(first[3]), match_end - last[0])
    if first is last:
        return False

    # Map the normalized target onto word tokens so the phrase may begin/end inside a
    # text node. This handles common WordPress markup such as <strong>service</strong>
    # <em>cleaning</em> without flattening or rewriting the surrounding HTML.
    target_tokens = re.findall(r"\S+", target)
    if not target_tokens:
        return False

    token_stream = []
    for node_index, (_, _, node, _) in enumerate(spans):
        for token in re.findall(r"\S+", _normalize_ws(str(node))):
            token_stream.append((token, node_index))

    norm_token = lambda value: re.sub(r"^[^\w]+|[^\w]+$", "", value.casefold())
    wanted = [norm_token(x) for x in target_tokens]
    matches = []
    for i in range(0, len(token_stream) - len(wanted) + 1):
        candidate = [norm_token(token_stream[i + j][0]) for j in range(len(wanted))]
        if candidate == wanted:
            matches.append((i, i + len(wanted) - 1))
    if len(matches) != 1:
        return False

    start_i, end_i = matches[0]
    node_indexes = [token_stream[i][1] for i in range(start_i, end_i + 1)]
    if not node_indexes:
        return False
    unique_indexes = sorted(set(node_indexes))
    matched_nodes = [spans[i][2] for i in unique_indexes]
    if any(n.parent and n.parent.name in {"a", "script", "style", "noscript"} for n in matched_nodes):
        return False

    # Require all participating nodes to belong to the same nearest block element. This
    # prevents a phrase from accidentally crossing paragraphs, list items, or headings.
    block_names = {"p", "li", "td", "th", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "div"}
    def block_parent(node):
        parent = node.parent
        while parent is not None and getattr(parent, "name", None) not in block_names:
            parent = parent.parent
        return parent
    parents = [block_parent(n) for n in matched_nodes]
    if not parents or any(parent is None or parent is not parents[0] for parent in parents):
        return False

    # Build the exact matched visible text per participating node. For the first/last
    # nodes we preserve text outside the match; middle nodes are emptied but their tags
    # remain intact. Empty formatting tags are removed afterwards.
    first_node = matched_nodes[0]
    last_node = matched_nodes[-1]
    first_raw = str(first_node)
    last_raw = str(last_node)

    first_tokens = re.findall(r"\S+", _normalize_ws(first_raw))
    last_tokens = re.findall(r"\S+", _normalize_ws(last_raw))
    first_start_token = 0
    last_end_token = len(last_tokens) - 1
    if unique_indexes[0] == unique_indexes[-1]:
        pattern = re.compile(r"\s+".join(re.escape(part) for part in target.split()))
        if not pattern.search(first_raw):
            return False
        first_node.replace_with(pattern.sub(replace_text, first_raw, count=1))
        return True

    # Conservative boundary rule: when the phrase spans nodes, it must consume the full
    # visible text of the first and last participating nodes. This avoids complex token
    # offset rewriting while still supporting the typical inline-formatting case.
    if _normalize_ws(first_raw) != " ".join(first_tokens) or _normalize_ws(last_raw) != " ".join(last_tokens):
        return False
    if token_stream[start_i][1] != unique_indexes[0] or token_stream[end_i][1] != unique_indexes[-1]:
        return False
    if len(first_tokens) != sum(1 for i in range(start_i, end_i + 1) if token_stream[i][1] == unique_indexes[0]):
        return False
    if len(last_tokens) != sum(1 for i in range(start_i, end_i + 1) if token_stream[i][1] == unique_indexes[-1]):
        return False

    first_node.replace_with(replace_text)
    for node in matched_nodes[1:]:
        node.extract()
    return True


def _apply_safe_replacements(html: str, replacements: list[dict[str, Any]]) -> tuple[str, int, list[str]]:
    """Apply Claude edits safely against the current live WordPress HTML.

    Handles exact HTML, unique single text nodes, and conservative text split across
    adjacent inline nodes. Never guesses when the same phrase occurs more than once.
    """
    updated = html
    applied = 0
    skipped: list[str] = []
    for item in replacements:
        find_text = str(item.get("find") or "").strip()
        replace_text = str(item.get("replace") or "").strip()
        if not find_text or not replace_text:
            skipped.append("incomplete replacement")
            continue

        if updated.count(find_text) == 1:
            updated = updated.replace(find_text, replace_text, 1)
            applied += 1
            continue

        visible_find = _normalize_ws(_strip_html_for_match(find_text))
        if not visible_find:
            skipped.append("empty content match")
            continue

        soup = BeautifulSoup(updated, "html.parser")
        # First try a single text node.
        nodes = _text_nodes_in_document(soup)
        single_matches = []
        pattern = re.compile(r"\s+".join(re.escape(part) for part in visible_find.split()))
        for node in nodes:
            if visible_find in _normalize_ws(str(node)):
                single_matches.append(node)
        if len(single_matches) == 1:
            node = single_matches[0]
            original = str(node)
            if re.search(r"<[^>]+>", replace_text):
                fragment = BeautifulSoup(replace_text, "html.parser")
                if _normalize_ws(original) != visible_find or not fragment.contents:
                    skipped.append("unsafe HTML replacement")
                    continue
                node.replace_with(*list(fragment.contents))
            else:
                if not pattern.search(original):
                    skipped.append("replacement text did not match live text node")
                    continue
                node.replace_with(pattern.sub(replace_text, original, count=1))
            updated = str(soup)
            applied += 1
            continue

        # Then handle a unique phrase split across inline text nodes.
        if re.search(r"<[^>]+>", replace_text):
            skipped.append("HTML replacement spanning multiple text nodes")
            continue
        if not _apply_cross_node_text_replacement(soup, visible_find, replace_text):
            skipped.append(f"could not uniquely match: {visible_find[:120]}")
            continue
        updated = str(soup)
        applied += 1

    return updated, applied, skipped


def _apply_service_page_link(html: str, service_url: str, anchor_text: str | None) -> tuple[str, bool]:
    """Add one contextual internal link to the verified primary service page.

    The URL is never supplied by Claude; it is the already-verified conflict primary URL.
    Only an existing visible phrase can become the anchor, and only once.
    """
    anchor = _normalize_ws(anchor_text or "")
    if not anchor or not service_url:
        return html, False
    soup = BeautifulSoup(html, "html.parser")
    target_key = _canonical_url_key(service_url)
    for link in soup.find_all("a", href=True):
        if _canonical_url_key(str(link.get("href"))) == target_key:
            return html, False
    matches = []
    for node in soup.find_all(string=True):
        if node.parent and node.parent.name in {"a", "script", "style", "noscript"}:
            continue
        if anchor in _normalize_ws(str(node)):
            matches.append(node)
    if len(matches) != 1:
        return html, False
    node = matches[0]
    original = str(node)
    pattern = re.compile(r"\s+".join(re.escape(part) for part in anchor.split()))
    match = pattern.search(original)
    if not match:
        return html, False
    before, matched, after = original[:match.start()], original[match.start():match.end()], original[match.end():]
    a = soup.new_tag("a", href=service_url)
    a.string = matched
    pieces = []
    if before:
        pieces.append(BeautifulSoup(before, "html.parser"))
    pieces.append(a)
    if after:
        pieces.append(BeautifulSoup(after, "html.parser"))
    node.replace_with(*pieces)
    return str(soup), True


@router.post("/{conflict_id}/resolve")
async def resolve_conflict_with_claude(
    conflict_id: str,
    payload: ResolveWithClaudeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Use Claude to create a minimal, evidence-based WordPress content fix and publish it.

    Only exact text replacements and a title update are applied. Claude cannot invent URLs,
    redirect/delete pages, change canonicals, or fabricate GSC evidence. Destructive actions
    such as consolidation or canonical changes are returned as manual-review actions instead.
    """
    company_id = _company_id(current_user)
    row = db.query(KeywordConflict).filter(
        KeywordConflict.id == conflict_id,
        KeywordConflict.company_id == company_id,
        KeywordConflict.deleted_at.is_(None),
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Keyword conflict not found.")

    site = str(payload.wordpress_site).rstrip("/") if payload.wordpress_site else ""
    username = payload.wordpress_username or ""
    password = payload.wordpress_application_password or ""
    if not site or not username or not password:
        raise HTTPException(
            status_code=400,
            detail="To resolve this conflict directly on WordPress, provide the WordPress site, username, and Application Password in the scan configuration.",
        )

    evidence = row.evidence or {}
    try:
        from models.company import Company
        from config import settings
        from services.secret_service import decrypt_secret
        from anthropic import AsyncAnthropic

        company = db.query(Company).filter(Company.id == company_id).first()
        encrypted = getattr(company, "anthropic_api_key_encrypted", None) if company else None
        api_key = decrypt_secret(encrypted) if encrypted else getattr(settings, "ANTHROPIC_API_KEY", None)
        if not api_key:
            raise HTTPException(status_code=503, detail="Claude AI is not configured.")

        primary = await _wordpress_find_page_by_url(site, row.primary_url, username, password)
        competing = await _wordpress_find_page_by_url(site, row.competing_url, username, password)
        if not primary or not competing:
            raise HTTPException(status_code=404, detail="One or both conflict URLs could not be found as published WordPress posts/pages using the supplied credentials.")

        primary_content = primary.get("content") or {}
        competing_content = competing.get("content") or {}
        primary_html = str(primary_content.get("raw") or primary_content.get("rendered") or "")
        competing_html = str(competing_content.get("raw") or competing_content.get("rendered") or "")
        if not competing_html:
            raise HTTPException(status_code=422, detail="The competing WordPress page has no editable content returned by the REST API.")

        primary_text = BeautifulSoup(primary_html, "html.parser").get_text(" ", strip=True)
        competing_text = BeautifulSoup(competing_html, "html.parser").get_text(" ", strip=True)
        shared_queries = evidence.get("shared_queries") or []

        model = getattr(settings, "ANTHROPIC_MODEL", None) or "claude-sonnet-4-6"
        ai = AsyncAnthropic(api_key=api_key)
        prompt = f"""You are an SEO remediation agent operating inside Boost Rankers AI SEO OS.

You have measured evidence that two real URLs may compete. Your job is to create a SAFE, MINIMAL differentiation patch for the COMPETING WordPress page.

Never claim a Google penalty or causal ranking loss. Do not invent GSC metrics, URLs, facts, services, locations, prices, or credentials. Do not recommend deletion, 301 redirects, canonical changes, or consolidation as an automatic action. Those require manual review.

Only return JSON with this schema:
{{
  "action": "differentiate_content" | "manual_review",
  "reason": string,
  "new_title": string,
  "replacements": [{{"find": string, "replace": string}}]
}}

Rules for differentiate_content:
- Make 1-4 minimal replacements in the existing competing content.
- Each `find` MUST be copied verbatim from the COMPETING CONTENT TEXT below (plain visible text, not HTML tags).
- Prefer a short, distinctive phrase (roughly 4-12 words) that appears as one visible sentence/phrase; do not intentionally span paragraphs, list items, links, or unrelated HTML blocks.
- Keep replacements focused on search-intent differentiation, not a total rewrite.
- Preserve existing links, image URLs, media, citations, factual claims, and business information.
- `replace` should normally be plain visible text. Do not invent URLs or HTML attributes.
- Return `service_link_anchor` as ONE existing visible phrase from the competing content that can naturally link to the PRIMARY service page. It must not be invented.
- Keep the primary service page as the authoritative target for the conflict keyword; differentiate the competing post/page instead of moving the target keyword to the competing URL.
- Use the service-link anchor at most once and only when it reads naturally.
- You may replace a heading plus its paragraph(s) with equivalent HTML that better targets a distinct intent.
- The new title must be truthful and clearly distinguish the competing page from the primary page.
- Do not stuff keywords.
- If safe differentiation cannot be done from the supplied evidence, return manual_review with an empty replacements array.

PRIMARY URL: {row.primary_url}
PRIMARY VERIFIED FOCUS KEYWORD: {evidence.get('focus_keyword_primary') or 'Not verified'}
PRIMARY TITLE: {primary.get('title', {}).get('rendered', '')}
PRIMARY CONTENT TEXT:
{primary_text[:12000]}

COMPETING URL: {row.competing_url}
COMPETING TITLE: {competing.get('title', {}).get('rendered', '')}
COMPETING HTML:
{competing_html[:30000]}

COMPETING CONTENT TEXT:
{competing_text[:12000]}

MEASURED CONFLICT EVIDENCE:
{json.dumps({
    'keyword': row.keyword,
    'conflict_score': row.conflict_score,
    'risk_level': row.risk_level,
    'recommendation': row.recommendation,
    'gsc_overlap': row.gsc_overlap,
    'intent_similarity': row.intent_similarity,
    'content_similarity': row.content_similarity,
    'ranking_displacement': row.ranking_displacement,
    'shared_queries': shared_queries[:10],
    'canonical_conflict': evidence.get('canonical_conflict'),
}, ensure_ascii=False, default=str)[:12000]}
"""

        response = await ai.messages.create(model=model, max_tokens=2200, messages=[{"role": "user", "content": prompt}])
        plan = _parse_claude_json(_extract_claude_text(response))
        action = str(plan.get("action") or "manual_review")
        reason = str(plan.get("reason") or "")

        if action != "differentiate_content":
            row.status = "reviewed"
            row.updated_by = str(current_user.id)
            row.evidence = {
                **evidence,
                "website_resolution": {
                    "status": "manual_review_required",
                    "reason": reason or "Claude determined that an automatic website change would be unsafe.",
                    "target_url": row.competing_url,
                    "model": model,
                },
            }
            db.commit()
            return {
                "success": False,
                "applied": False,
                "message": reason or "Claude determined that this conflict requires manual review.",
                "conflict": _serialize_conflict(row),
            }

        replacements = plan.get("replacements")
        if not isinstance(replacements, list) or not replacements:
            raise ValueError("Claude did not return any safe content replacements.")
        # Claude suggestions are advisory. A single non-match must never turn the
        # whole Resolve operation into a 502. WordPress can normalize markup and Claude
        # can select a phrase that is visible to a human but split across DOM nodes.
        # The replacement helper therefore returns safely skipped edits; we only publish
        # when at least one independently verified change (content, title, or contextual
        # service-page link) is available.
        new_content, applied, skipped_replacements = _apply_safe_replacements(competing_html, replacements[:4])

        # Strengthen the verified PRIMARY service page without changing its content.
        # The primary URL comes from measured conflict evidence, never from Claude.
        service_anchor = str(plan.get("service_link_anchor") or "").strip()
        new_content, service_link_applied = _apply_service_page_link(new_content, row.primary_url, service_anchor)
        new_title = str(plan.get("new_title") or "").strip()
        if not new_title:
            raise ValueError("Claude did not return a new page title.")

        current_title = str(competing.get("title", {}).get("raw") or competing.get("title", {}).get("rendered") or "").strip()
        title_changed = bool(new_title and _normalize_ws(new_title) != _normalize_ws(current_title))

        # Do not publish a no-op. If Claude returned unusable content anchors and also
        # failed to provide a meaningful title/link change, keep the conflict open for
        # manual review instead of guessing at live WordPress content.
        if applied == 0 and not service_link_applied and not title_changed:
            row.status = "reviewed"
            row.updated_by = str(current_user.id)
            row.evidence = {
                **evidence,
                "website_resolution": {
                    "status": "manual_review_required",
                    "reason": "Claude returned edits that could not be safely matched to the current WordPress content, and no independent title or service-page link change was available.",
                    "target_url": row.competing_url,
                    "model": model,
                    "skipped_replacements": skipped_replacements,
                },
            }
            db.commit()
            return {
                "success": False,
                "applied": False,
                "message": "No safe live-content match was found, so WordPress was not changed. The conflict remains available for manual review.",
                "conflict": _serialize_conflict(row),
            }

        content_type = str(competing.get("content_type"))
        post_id = int(competing["id"])
        async with httpx.AsyncClient(timeout=45, follow_redirects=True, auth=(username, password), headers={"User-Agent": "BoostRankers-KeywordConflictResolver/1.0"}) as http:
            update = await http.post(
                f"{site}/wp-json/wp/v2/{content_type}/{post_id}",
                params={"context": "edit"},
                json={"title": new_title, "content": new_content},
            )
            if update.status_code in (401, 403):
                raise HTTPException(status_code=403, detail="WordPress rejected the authenticated update. The page was not changed.")
            if update.status_code >= 400:
                detail = update.text[:1000]
                raise HTTPException(status_code=502, detail=f"WordPress update failed with HTTP {update.status_code}: {detail}")

            updated_payload = update.json()
            verified_url = str(updated_payload.get("link") or row.competing_url)

        row.status = "resolved"
        row.updated_by = str(current_user.id)
        row.evidence = {
            **evidence,
            "website_resolution": {
                "status": "applied",
                "action": "differentiate_content",
                "target_url": verified_url,
                "wordpress_content_type": content_type,
                "wordpress_post_id": post_id,
                "new_title": new_title,
                "replacements_applied": applied,
                "skipped_replacements": skipped_replacements,
                "service_page_link_applied": service_link_applied,
                "service_page_target": row.primary_url,
                "reason": reason,
                "model": model,
                "applied_at": datetime.now(UTC).isoformat(),
            },
        }
        db.commit()
        db.refresh(row)
        return {
            "success": True,
            "applied": True,
            "message": f"Claude differentiated the competing WordPress content and published {applied} targeted content change(s){' plus one contextual link to the primary service page' if service_link_applied else ''}.",
            "conflict": _serialize_conflict(row),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Claude WordPress conflict resolution failed")
        raise HTTPException(status_code=502, detail=f"Claude WordPress resolution failed: {exc}") from exc


@router.patch("/{conflict_id}/status")
def update_status(conflict_id: str, payload: StatusUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)
    row = db.query(KeywordConflict).filter(KeywordConflict.id == conflict_id, KeywordConflict.company_id == company_id, KeywordConflict.deleted_at.is_(None)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Keyword conflict not found.")
    row.status = payload.status
    row.updated_by = str(current_user.id)
    db.commit()
    db.refresh(row)
    return {"success": True, "conflict": _serialize_conflict(row)}


@router.post("/{conflict_id}/analyze")
async def analyze_conflict(conflict_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Optional Claude interpretation. Measurements remain deterministic and stored separately."""
    company_id = _company_id(current_user)
    row = db.query(KeywordConflict).filter(KeywordConflict.id == conflict_id, KeywordConflict.company_id == company_id, KeywordConflict.deleted_at.is_(None)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Keyword conflict not found.")
    try:
        from models.company import Company
        from config import settings
        from services.secret_service import decrypt_secret
        from anthropic import AsyncAnthropic
        company = db.query(Company).filter(Company.id == company_id).first()
        encrypted = getattr(company, "anthropic_api_key_encrypted", None) if company else None
        api_key = decrypt_secret(encrypted) if encrypted else getattr(settings, "ANTHROPIC_API_KEY", None)
        if not api_key:
            raise HTTPException(status_code=503, detail="Claude AI is not configured. The measured conflict evidence is still available.")
        model = getattr(settings, "ANTHROPIC_MODEL", None) or "claude-sonnet-4-6"
        ai = AsyncAnthropic(api_key=api_key)
        prompt = f"""You are reviewing an SEO keyword conflict. Use only the measured evidence below.
Do not claim that Google penalized a page or that one URL caused another URL to lose rankings.
Return concise practical guidance: diagnosis, why it matters, and recommended action.

Keyword: {row.keyword}
Primary URL: {row.primary_url}
Competing URL: {row.competing_url}
Conflict score: {row.conflict_score}
Risk: {row.risk_level}
Evidence: {json.dumps(row.evidence, ensure_ascii=False, default=str)[:16000]}
"""
        response = await ai.messages.create(model=model, max_tokens=700, messages=[{"role": "user", "content": prompt}])
        text = "".join(block.text for block in response.content if hasattr(block, "text")).strip()
        row.evidence = {**(row.evidence or {}), "ai_analysis": text, "ai_analysis_source": "Claude interpretation of measured evidence"}
        db.commit()
        return {"success": True, "analysis": text, "conflict": _serialize_conflict(row)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Claude conflict analysis failed")
        raise HTTPException(status_code=502, detail=f"Claude analysis failed: {exc}") from exc
