"""
Boost Rankers AI SEO OS
Page & Post Indexing + Crawling

Isolated feature module.

Important Google behavior:
- Ordinary WordPress URLs are NOT individually submitted through Google's Indexing API.
- For normal pages/posts this module uses:
  1) real HTTP crawling,
  2) robots/noindex/canonical/indexability checks,
  3) WordPress REST discovery,
  4) Google Search Console URL Inspection when the connected OAuth scope permits it,
  5) automatic Search Console sitemap submission for discovery.
- "Submitted" never means "Indexed". Only a verified URL Inspection result can be shown
  as Google's index status.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from database.database import SessionLocal, get_db
from models.client import Client
from models.user import User
from api.deps.current_user import get_current_user
from routers.google_integration import get_connection
from services.google_integration_service import get_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/page-post-indexing", tags=["Page & Post Indexing"])

UTC = timezone.utc
GOOGLE_SITEMAP_ENDPOINT = "https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps/{feed}"
GOOGLE_INSPECTION_ENDPOINT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"

MAX_DISCOVERY_PER_TYPE = 2000
MAX_SCAN_URLS = 1000
HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0, read=25.0, write=15.0, pool=10.0)
USER_AGENT = "BoostRankers-PagePostIndexer/1.0 (+https://boostrankers.com)"


class CrawlRequest(BaseModel):
    client_id: str
    wordpress_site: HttpUrl | None = None
    wordpress_username: str | None = Field(default=None, max_length=255)
    wordpress_application_password: str | None = Field(default=None, max_length=255)
    include_posts: bool = True
    include_pages: bool = True
    max_urls: int = Field(default=500, ge=10, le=1000)
    verify_google_index: bool = True
    submit_sitemap: bool = True

    @field_validator(
        "wordpress_username",
        "wordpress_application_password",
    )
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        return value.strip() if value else None


class SubmitRequest(BaseModel):
    client_id: str
    sitemap_url: HttpUrl | None = None


class InspectRequest(BaseModel):
    client_id: str
    url: HttpUrl


def _company_id(user: User) -> str:
    value = getattr(user, "company_id", None)
    if not value:
        raise HTTPException(status_code=403, detail="Your account is not attached to a company.")
    return str(value)


def _now() -> datetime:
    return datetime.now(UTC)


def _clean_site(value: str) -> str:
    parsed = urlparse(str(value).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Website must be a valid HTTP/HTTPS URL.")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _url_key(value: str) -> str:
    parsed = urlparse(str(value).strip())
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return f"{parsed.scheme.lower()}://{host}{path}" + (f"?{parsed.query}" if parsed.query else "")


def _same_domain(a: str, b: str) -> bool:
    aa = urlparse(a).netloc.lower().lstrip("www.")
    bb = urlparse(b).netloc.lower().lstrip("www.")
    return aa == bb


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()


def _first_tag(html: str, tag: str) -> str | None:
    match = re.search(
        rf"<{tag}\b[^>]*>(.*?)</{tag}>",
        html or "",
        flags=re.I | re.S,
    )
    return _strip_html(match.group(1))[:1000] if match else None


def _meta_content(html: str, name: str) -> str | None:
    patterns = [
        rf'<meta\b[^>]*name=["\']{re.escape(name)}["\'][^>]*content=["\']([^"\']*)["\']',
        rf'<meta\b[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']{re.escape(name)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html or "", flags=re.I | re.S)
        if match:
            return unescape(match.group(1)).strip()
    return None


def _link_canonical(html: str, final_url: str) -> str | None:
    match = re.search(
        r'<link\b[^>]*rel=["\'][^"\']*\bcanonical\b[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
        html or "",
        flags=re.I | re.S,
    )
    if not match:
        match = re.search(
            r'<link\b[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\'][^"\']*\bcanonical\b[^"\']*["\']',
            html or "",
            flags=re.I | re.S,
        )
    return urljoin(final_url, unescape(match.group(1)).strip()) if match else None


def _robots_indexable(robots_meta: str | None) -> tuple[bool, str | None]:
    if not robots_meta:
        return True, None
    directives = {
        item.strip().lower()
        for item in re.split(r"[,;]", robots_meta)
        if item.strip()
    }
    if "noindex" in directives or "none" in directives:
        return False, "noindex"
    return True, None


def _sitemap_candidates(site: str, robots_text: str | None) -> list[str]:
    found: list[str] = []
    for line in (robots_text or "").splitlines():
        if line.lower().startswith("sitemap:"):
            candidate = line.split(":", 1)[1].strip()
            if candidate.startswith(("http://", "https://")):
                found.append(candidate)
    for candidate in (
        f"{site}/wp-sitemap.xml",
        f"{site}/sitemap_index.xml",
        f"{site}/sitemap.xml",
    ):
        if candidate not in found:
            found.append(candidate)
    return found


def _extract_sitemap_locs(xml: str, limit: int = 5000) -> list[str]:
    return [
        unescape(item).strip()
        for item in re.findall(r"<loc>\s*(.*?)\s*</loc>", xml or "", flags=re.I | re.S)[:limit]
        if item.strip()
    ]


def _host_key(value: str) -> str:
    parsed = urlparse(str(value).strip())
    host = (parsed.hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _property_matches_site(property_value: str, site: str) -> bool:
    """
    Prevent submitting a client's sitemap to a different Search Console property.

    Supports URL-prefix properties and sc-domain properties. Protocol and a leading
    www. are ignored for hostname comparison, which is appropriate for ownership
    matching here.
    """
    prop = str(property_value or "").strip()
    site_host = _host_key(site)
    if not prop or not site_host:
        return False

    if prop.lower().startswith("sc-domain:"):
        return _host_key("https://" + prop.split(":", 1)[1]) == site_host

    try:
        parsed = urlparse(prop)
    except Exception:
        return False

    return bool(parsed.hostname) and _host_key(prop) == site_host


async def _probe_sitemap_candidate(
    site: str,
    candidate: str,
    http: httpx.AsyncClient,
    *,
    robots_declared: bool,
) -> dict[str, Any]:
    """
    Verify that a sitemap candidate is real before sending it to Google.

    We deliberately do not treat a merely existing URL as a valid sitemap:
    the response must be successful and contain sitemap <loc> entries.
    """
    candidate = str(candidate).strip()
    if not candidate or not _same_domain(site, candidate):
        return {
            "url": candidate,
            "valid": False,
            "reason": "Sitemap must belong to the client's website.",
        }

    try:
        response = await http.get(candidate)
    except httpx.HTTPError as exc:
        return {
            "url": candidate,
            "valid": False,
            "reason": f"Sitemap request failed: {str(exc)[:300]}",
        }

    if response.status_code >= 400:
        return {
            "url": candidate,
            "valid": False,
            "status_code": response.status_code,
            "reason": f"Sitemap returned HTTP {response.status_code}.",
        }

    xml = response.text or ""
    locs = _extract_sitemap_locs(xml, 5000)
    if not locs:
        return {
            "url": candidate,
            "valid": False,
            "status_code": response.status_code,
            "reason": "Sitemap returned no <loc> entries.",
        }

    lowered = xml.lower()
    if "<sitemapindex" in lowered:
        kind = "sitemap_index"
    elif "<urlset" in lowered:
        kind = "urlset"
    else:
        kind = "xml"

    # A robots.txt declaration is the strongest signal of the site's intended
    # sitemap. Valid URL sets are also preferred over empty/non-sitemap XML.
    score = 100 if robots_declared else 0
    score += 40 if kind == "sitemap_index" else 30 if kind == "urlset" else 10
    score += min(len(locs), 1000) / 1000

    return {
        "url": candidate,
        "valid": True,
        "status_code": response.status_code,
        "kind": kind,
        "loc_count": len(locs),
        "robots_declared": robots_declared,
        "score": score,
    }


async def _discover_submission_sitemap(
    site: str,
    explicit_sitemap_url: str | None = None,
) -> dict[str, Any]:
    """
    Select the actual sitemap for this client instead of blindly submitting
    /wp-sitemap.xml.

    Priority:
      1. An explicitly supplied sitemap, after validation.
      2. A valid sitemap declared by robots.txt.
      3. A valid WordPress/standard sitemap fallback.

    Empty, inaccessible, cross-domain, or non-sitemap candidates are rejected.
    """
    site = _clean_site(site)

    timeout = httpx.Timeout(20.0, connect=8.0, read=15.0, write=10.0, pool=8.0)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/xml,text/xml,text/plain,*/*",
    }

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as http:
        if explicit_sitemap_url:
            explicit = str(explicit_sitemap_url).strip()
            if not _same_domain(site, explicit):
                return {
                    "status": "error",
                    "message": "The supplied sitemap must belong to the selected client website.",
                    "sitemap_url": explicit,
                }

            result = await _probe_sitemap_candidate(
                site,
                explicit,
                http,
                robots_declared=False,
            )
            if not result.get("valid"):
                return {
                    "status": "error",
                    "message": result.get("reason") or "The supplied sitemap could not be validated.",
                    "sitemap_url": explicit,
                }

            return {
                "status": "ok",
                "sitemap_url": explicit,
                "source": "explicit",
                "kind": result.get("kind"),
                "loc_count": result.get("loc_count"),
            }

        robots_declared: list[str] = []
        try:
            robots_response = await http.get(f"{site}/robots.txt")
            if robots_response.status_code < 400:
                for line in robots_response.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        candidate = line.split(":", 1)[1].strip()
                        if candidate.startswith(("http://", "https://")):
                            robots_declared.append(candidate)
        except httpx.HTTPError:
            robots_declared = []

        fallback_candidates = [
            f"{site}/wp-sitemap.xml",
            f"{site}/sitemap_index.xml",
            f"{site}/sitemap.xml",
        ]

        candidates: list[tuple[str, bool]] = []
        seen: set[str] = set()
        for candidate in robots_declared + fallback_candidates:
            candidate = candidate.strip()
            key = candidate.lower()
            if not candidate or key in seen:
                continue
            seen.add(key)
            candidates.append((candidate, candidate in robots_declared))

        results: list[dict[str, Any]] = []
        for candidate, declared in candidates[:10]:
            result = await _probe_sitemap_candidate(
                site,
                candidate,
                http,
                robots_declared=declared,
            )
            if result.get("valid"):
                results.append(result)

        if not results:
            attempted = ", ".join(candidate for candidate, _ in candidates[:10])
            return {
                "status": "not_found",
                "message": (
                    "No valid sitemap was found for this website. "
                    f"Checked: {attempted or 'no sitemap candidates'}."
                ),
            }

        # robots.txt is authoritative when it points to a valid sitemap.
        # Otherwise select the strongest verified sitemap candidate.
        results.sort(
            key=lambda item: (
                1 if item.get("robots_declared") else 0,
                item.get("score", 0),
                item.get("loc_count", 0),
            ),
            reverse=True,
        )
        selected = results[0]

        return {
            "status": "ok",
            "sitemap_url": selected["url"],
            "source": "robots.txt" if selected.get("robots_declared") else "verified_fallback",
            "kind": selected.get("kind"),
            "loc_count": selected.get("loc_count"),
        }


def _parse_index_status(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("inspectionResult") or {}
    index = result.get("indexStatusResult") or {}
    verdict = index.get("verdict")
    coverage = index.get("coverageState")
    robots = index.get("robotsTxtState")
    indexing = index.get("indexingState")
    canonical = index.get("googleCanonical")
    user_canonical = index.get("userCanonical")

    normalized = "unknown"
    if verdict == "PASS":
        normalized = "indexed"
    elif verdict in {"FAIL", "ERROR"}:
        normalized = "not_indexed"

    return {
        "status": normalized,
        "verdict": verdict,
        "coverage_state": coverage,
        "robots_txt_state": robots,
        "indexing_state": indexing,
        "google_canonical": canonical,
        "user_canonical": user_canonical,
        "last_crawl_time": index.get("lastCrawlTime"),
        "page_fetch_state": index.get("pageFetchState"),
        "raw": payload,
    }


def _json(value: Any) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, default=str)


def ensure_page_post_indexing_tables() -> None:
    """
    Creates only new feature tables. It deliberately does not ALTER existing tables
    during application startup, avoiding the statement-timeout problem encountered
    by Keyword Conflicts.
    """
    ddl = """
    CREATE TABLE IF NOT EXISTS page_post_indexing_runs (
        id VARCHAR(36) PRIMARY KEY,
        company_id VARCHAR(36) NOT NULL,
        client_id VARCHAR(36) NOT NULL,
        status VARCHAR(30) NOT NULL DEFAULT 'queued',
        progress_message VARCHAR(1000),
        total_urls INTEGER NOT NULL DEFAULT 0,
        discovered_urls INTEGER NOT NULL DEFAULT 0,
        crawled_urls INTEGER NOT NULL DEFAULT 0,
        indexable_urls INTEGER NOT NULL DEFAULT 0,
        indexed_urls INTEGER NOT NULL DEFAULT 0,
        not_indexed_urls INTEGER NOT NULL DEFAULT 0,
        error_urls INTEGER NOT NULL DEFAULT 0,
        sitemap_submitted BOOLEAN NOT NULL DEFAULT FALSE,
        sitemap_url VARCHAR(2000),
        google_message VARCHAR(2000),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ
    );

    CREATE INDEX IF NOT EXISTS ix_ppi_runs_company_client
        ON page_post_indexing_runs(company_id, client_id, created_at DESC);

    CREATE TABLE IF NOT EXISTS page_post_indexing_items (
        id VARCHAR(36) PRIMARY KEY,
        company_id VARCHAR(36) NOT NULL,
        client_id VARCHAR(36) NOT NULL,
        run_id VARCHAR(36) NOT NULL,
        wordpress_id INTEGER,
        content_type VARCHAR(20) NOT NULL,
        url VARCHAR(2000) NOT NULL,
        final_url VARCHAR(2000),
        title VARCHAR(1000),
        h1 VARCHAR(1000),
        canonical_url VARCHAR(2000),
        http_status INTEGER,
        content_type_header VARCHAR(255),
        robots_meta VARCHAR(1000),
        x_robots_tag VARCHAR(1000),
        indexable BOOLEAN,
        indexability_reason VARCHAR(255),
        sitemap_present BOOLEAN,
        crawl_status VARCHAR(30) NOT NULL DEFAULT 'pending',
        google_index_status VARCHAR(30) NOT NULL DEFAULT 'not_checked',
        google_verdict VARCHAR(100),
        google_coverage_state VARCHAR(1000),
        google_last_crawl_time VARCHAR(100),
        google_canonical VARCHAR(2000),
        user_canonical VARCHAR(2000),
        submitted_at TIMESTAMPTZ,
        crawled_at TIMESTAMPTZ,
        inspected_at TIMESTAMPTZ,
        error_message VARCHAR(2000),
        evidence TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE UNIQUE INDEX IF NOT EXISTS ux_ppi_company_client_url
        ON page_post_indexing_items(company_id, client_id, url);

    CREATE INDEX IF NOT EXISTS ix_ppi_items_run
        ON page_post_indexing_items(run_id);

    CREATE INDEX IF NOT EXISTS ix_ppi_items_status
        ON page_post_indexing_items(company_id, client_id, google_index_status);
    """
    db = SessionLocal()
    try:
        for statement in [item.strip() for item in ddl.split(";") if item.strip()]:
            db.execute(text(statement))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Page/Post Indexing table initialization failed")
        raise
    finally:
        db.close()


def _client_for_company(db: Session, client_id: str, company_id: str) -> Client:
    client = (
        db.query(Client)
        .filter(Client.id == client_id, Client.company_id == company_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found in your company.")
    return client


async def _discover_wp_items(
    site: str,
    *,
    username: str | None,
    password: str | None,
    include_posts: bool,
    include_pages: bool,
    max_urls: int,
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    auth = (username, password) if username and password else None
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    items: list[dict[str, Any]] = []

    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
        headers=headers,
        auth=auth,
    ) as http:
        # Authentication is verified only when credentials were explicitly supplied.
        if auth:
            me = await http.get(f"{site}/wp-json/wp/v2/users/me", params={"context": "edit"})
            if me.status_code in (401, 403):
                raise HTTPException(status_code=401, detail="WordPress authentication failed.")
            if me.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail=f"WordPress authentication check returned HTTP {me.status_code}.",
                )

        per_type = max(1, max_urls // (int(include_posts) + int(include_pages) or 1))

        for content_type, enabled in (("posts", include_posts), ("pages", include_pages)):
            if not enabled:
                continue

            page = 1
            while len(items) < max_urls and page <= 20:
                remaining = max_urls - len(items)
                per_page = min(100, remaining, per_type)
                response = await http.get(
                    f"{site}/wp-json/wp/v2/{content_type}",
                    params={
                        "status": "publish",
                        "per_page": per_page,
                        "page": page,
                        "_fields": "id,link,slug,date,modified,title,status",
                    },
                )

                if response.status_code == 400 and page > 1:
                    break
                if response.status_code >= 400:
                    raise HTTPException(
                        status_code=502,
                        detail=f"WordPress {content_type} discovery returned HTTP {response.status_code}.",
                    )

                try:
                    rows = response.json()
                except ValueError as exc:
                    raise HTTPException(
                        status_code=502,
                        detail=f"WordPress returned invalid JSON for {content_type}.",
                    ) from exc

                if not isinstance(rows, list) or not rows:
                    break

                for row in rows:
                    url = str(row.get("link") or "").strip()
                    if not url:
                        continue
                    items.append(
                        {
                            "wordpress_id": int(row["id"]) if row.get("id") is not None else None,
                            "content_type": "post" if content_type == "posts" else "page",
                            "url": url,
                            "title": _strip_html(
                                (row.get("title") or {}).get("rendered")
                                if isinstance(row.get("title"), dict)
                                else row.get("title")
                            ),
                            "modified": row.get("modified"),
                        }
                    )

                if len(rows) < per_page:
                    break
                page += 1

    return items[:max_urls], None, None


async def _discover_from_sitemap(
    site: str,
    max_urls: int,
) -> tuple[list[dict[str, Any]], str | None]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/xml,text/xml,text/plain,*/*"}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True, headers=headers) as http:
        robots_response = await http.get(f"{site}/robots.txt")
        robots_text = robots_response.text if robots_response.status_code < 400 else ""
        candidates = _sitemap_candidates(site, robots_text)

        seen_sitemaps: set[str] = set()
        queue = list(candidates)
        urls: list[str] = []

        while queue and len(urls) < max_urls and len(seen_sitemaps) < 20:
            sitemap = queue.pop(0)
            if sitemap in seen_sitemaps:
                continue
            seen_sitemaps.add(sitemap)

            try:
                response = await http.get(sitemap)
            except httpx.HTTPError:
                continue
            if response.status_code >= 400:
                continue

            locs = _extract_sitemap_locs(response.text, max_urls * 2)
            for loc in locs:
                if loc.endswith(".xml") or "sitemap" in loc.lower():
                    if loc not in seen_sitemaps and len(queue) < 50:
                        queue.append(loc)
                elif _same_domain(site, loc):
                    urls.append(loc)
                    if len(urls) >= max_urls:
                        break

        unique = list(dict.fromkeys(urls))[:max_urls]
        return (
            [
                {
                    "wordpress_id": None,
                    "content_type": "unknown",
                    "url": url,
                    "title": None,
                    "modified": None,
                }
                for url in unique
            ],
            next(iter(seen_sitemaps), None),
        )


async def _crawl_url(item: dict[str, Any]) -> dict[str, Any]:
    url = item["url"]
    result = {
        **item,
        "final_url": None,
        "http_status": None,
        "content_type_header": None,
        "title": item.get("title"),
        "h1": None,
        "canonical_url": None,
        "robots_meta": None,
        "x_robots_tag": None,
        "indexable": None,
        "indexability_reason": None,
        "crawl_status": "error",
        "error_message": None,
    }

    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*"},
        ) as http:
            response = await http.get(url)
        final_url = str(response.url)
        result["final_url"] = final_url
        result["http_status"] = response.status_code
        result["content_type_header"] = response.headers.get("content-type")

        if response.status_code >= 400:
            result["indexable"] = False
            result["indexability_reason"] = f"http_{response.status_code}"
            result["crawl_status"] = "error"
            result["error_message"] = f"HTTP {response.status_code}"
            return result

        html = response.text
        result["title"] = _first_tag(html, "title") or result["title"]
        result["h1"] = _first_tag(html, "h1")
        result["canonical_url"] = _link_canonical(html, final_url)
        result["robots_meta"] = _meta_content(html, "robots")
        result["x_robots_tag"] = response.headers.get("x-robots-tag")

        meta_indexable, meta_reason = _robots_indexable(result["robots_meta"])
        x_indexable, x_reason = _robots_indexable(result["x_robots_tag"])

        if not meta_indexable:
            result["indexable"] = False
            result["indexability_reason"] = meta_reason
        elif not x_indexable:
            result["indexable"] = False
            result["indexability_reason"] = f"x_robots_{x_reason}"
        elif result["canonical_url"] and not _same_domain(final_url, result["canonical_url"]):
            result["indexable"] = True
            result["indexability_reason"] = "cross_domain_canonical_review"
        elif result["canonical_url"] and _url_key(result["canonical_url"]) != _url_key(final_url):
            result["indexable"] = True
            result["indexability_reason"] = "canonical_points_elsewhere"
        else:
            result["indexable"] = True
            result["indexability_reason"] = None

        result["crawl_status"] = "ok"
        return result

    except httpx.TimeoutException:
        result["crawl_status"] = "timeout"
        result["error_message"] = "HTTP crawl timed out."
        result["indexable"] = False
        result["indexability_reason"] = "crawl_timeout"
        return result
    except httpx.HTTPError as exc:
        result["crawl_status"] = "error"
        result["error_message"] = str(exc)[:1000]
        result["indexable"] = False
        result["indexability_reason"] = "crawl_error"
        return result
    except Exception as exc:
        result["crawl_status"] = "error"
        result["error_message"] = str(exc)[:1000]
        result["indexable"] = False
        result["indexability_reason"] = "crawl_error"
        return result


async def _google_inspect(
    db: Session,
    company_id: str,
    url: str,
) -> dict[str, Any]:
    """Inspect a URL in Search Console without allowing Google network failures to fail a crawl."""
    try:
        connection = get_connection(db, company_id, "search_console")
        if connection is None:
            return {"status": "not_connected", "message": "Google Search Console is not connected."}

        property_value = None
        for attr in (
            "selected_property",
            "selected_search_console_property",
            "search_console_property",
        ):
            value = getattr(connection, attr, None)
            if value:
                property_value = str(value)
                break

        if not property_value:
            return {"status": "not_configured", "message": "No Search Console property is selected."}

        token = await get_access_token(connection, db)
        timeout = httpx.Timeout(20.0, connect=8.0, read=15.0, write=10.0, pool=8.0)

        async with httpx.AsyncClient(timeout=timeout) as http:
            request_json = {
                "inspectionUrl": url,
                "siteUrl": property_value,
            }
            try:
                response = await http.post(
                    GOOGLE_INSPECTION_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                    json=request_json,
                )
            except asyncio.CancelledError:
                raise
            except httpx.TimeoutException:
                return {
                    "status": "timeout",
                    "message": "Google URL Inspection timed out. The crawl result was retained; inspection can be retried later.",
                    "property": property_value,
                }
            except httpx.RequestError as exc:
                logger.warning("Google URL Inspection request failed for %s: %s", url, exc)
                return {
                    "status": "error",
                    "message": "Google URL Inspection could not be reached. The crawl result was retained.",
                    "property": property_value,
                }

            if response.status_code == 401:
                try:
                    token = await get_access_token(connection, db)
                    response = await http.post(
                        GOOGLE_INSPECTION_ENDPOINT,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/json",
                        },
                        json=request_json,
                    )
                except asyncio.CancelledError:
                    raise
                except httpx.TimeoutException:
                    return {
                        "status": "timeout",
                        "message": "Google URL Inspection timed out after token refresh. The crawl result was retained.",
                        "property": property_value,
                    }
                except httpx.RequestError as exc:
                    logger.warning("Google URL Inspection retry failed for %s: %s", url, exc)
                    return {
                        "status": "error",
                        "message": "Google URL Inspection could not be reached after token refresh. The crawl result was retained.",
                        "property": property_value,
                    }

        if response.status_code == 403:
            return {
                "status": "unavailable",
                "message": "The connected Google OAuth authorization does not permit URL Inspection.",
                "property": property_value,
            }

        if response.status_code >= 400:
            try:
                detail = response.json().get("error", {}).get("message") or "Google URL Inspection failed."
            except Exception:
                detail = f"Google URL Inspection returned HTTP {response.status_code}."
            return {"status": "error", "message": detail, "property": property_value}

        try:
            payload = response.json()
        except ValueError:
            return {
                "status": "error",
                "message": "Google URL Inspection returned an invalid response.",
                "property": property_value,
            }

        parsed = _parse_index_status(payload)
        parsed["property"] = property_value
        return parsed

    except asyncio.CancelledError:
        # Task cancellation is a normal lifecycle event (for example during Uvicorn reload).
        # Never convert it into a fake Google error or swallow cancellation.
        raise
    except Exception as exc:
        logger.exception("Unexpected Google URL Inspection error for %s", url)
        return {
            "status": "error",
            "message": f"Google URL Inspection was unavailable: {str(exc)[:500]}",
        }


async def _google_get_sitemap(
    http: httpx.AsyncClient,
    connection: Any,
    db: Session,
    property_value: str,
    sitemap_url: str,
    token: str,
) -> tuple[dict[str, Any] | None, str]:
    """
    Read the sitemap resource back from Search Console after submission.

    Google documents the PUT submission endpoint as returning an empty body.
    A follow-up GET is therefore the reliable way to distinguish:
      - Google accepted the submission and registered the sitemap;
      - Google accepted the request but the sitemap resource is not visible yet;
      - Google rejected the request.
    """
    endpoint = GOOGLE_SITEMAP_ENDPOINT.format(
        site=quote(property_value, safe=""),
        feed=quote(sitemap_url, safe=""),
    )

    last_response: httpx.Response | None = None
    for attempt in range(3):
        try:
            response = await http.get(
                endpoint,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
        except httpx.TimeoutException:
            if attempt == 2:
                return None, "timeout"
            await asyncio.sleep(1.0)
            continue
        except httpx.RequestError:
            if attempt == 2:
                return None, "request_error"
            await asyncio.sleep(1.0)
            continue

        last_response = response

        if response.status_code == 401:
            token = await get_access_token(connection, db)
            if attempt < 2:
                continue
            return None, "unauthorized"

        if response.status_code == 200:
            try:
                return response.json(), "ok"
            except ValueError:
                return None, "invalid_response"

        # Search Console can be eventually consistent immediately after PUT.
        # A short retry avoids falsely reporting that registration failed.
        if response.status_code in {404, 409, 429, 500, 502, 503, 504} and attempt < 2:
            await asyncio.sleep(1.0 + attempt)
            continue

        break

    if last_response is not None:
        if last_response.status_code == 403:
            return None, "forbidden"
        if last_response.status_code == 404:
            return None, "not_visible_yet"
        if last_response.status_code >= 400:
            return None, f"http_{last_response.status_code}"

    return None, "request_error"


async def _google_submit_sitemap(
    db: Session,
    company_id: str,
    sitemap_url: str,
) -> dict[str, Any]:
    connection = get_connection(db, company_id, "search_console")
    if connection is None:
        return {
            "submitted": False,
            "status": "not_connected",
            "message": "Google Search Console is not connected.",
        }

    property_value = None
    for attr in (
        "selected_property",
        "selected_search_console_property",
        "search_console_property",
    ):
        value = getattr(connection, attr, None)
        if value:
            property_value = str(value)
            break

    if not property_value:
        return {
            "submitted": False,
            "status": "not_configured",
            "message": "No Search Console property is selected.",
        }

    # Never submit a client's sitemap against another client's GSC property.
    site = _clean_site(sitemap_url)
    if not _property_matches_site(property_value, site):
        return {
            "submitted": False,
            "status": "property_mismatch",
            "message": (
                "The selected Google Search Console property does not match "
                "the client's website. Select the correct Search Console property "
                "before submitting its sitemap."
            ),
            "property": property_value,
            "sitemap_url": sitemap_url,
        }

    token = await get_access_token(connection, db)
    endpoint = GOOGLE_SITEMAP_ENDPOINT.format(
        site=quote(property_value, safe=""),
        feed=quote(sitemap_url, safe=""),
    )

    timeout = httpx.Timeout(20.0, connect=8.0, read=15.0, write=10.0, pool=8.0)
    async with httpx.AsyncClient(timeout=timeout) as http:
        try:
            response = await http.put(
                endpoint,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
        except httpx.TimeoutException:
            return {
                "submitted": False,
                "status": "timeout",
                "message": "Google sitemap submission timed out. Please retry.",
            }
        except httpx.RequestError:
            return {
                "submitted": False,
                "status": "error",
                "message": "Google Search Console could not be reached. Please retry.",
            }

        if response.status_code == 401:
            token = await get_access_token(connection, db)
            try:
                response = await http.put(
                    endpoint,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
            except httpx.TimeoutException:
                return {
                    "submitted": False,
                    "status": "timeout",
                    "message": "Google sitemap submission timed out after token refresh. Please retry.",
                }
            except httpx.RequestError:
                return {
                    "submitted": False,
                    "status": "error",
                    "message": "Google Search Console could not be reached after token refresh.",
                }

        if response.status_code == 403:
            return {
                "submitted": False,
                "status": "unavailable",
                "message": "The connected Google OAuth authorization does not permit sitemap submission.",
                "property": property_value,
                "sitemap_url": sitemap_url,
            }

        if response.status_code >= 400:
            try:
                detail = response.json().get("error", {}).get("message") or "Google sitemap submission failed."
            except Exception:
                detail = f"Google sitemap submission returned HTTP {response.status_code}."
            return {
                "submitted": False,
                "status": "error",
                "message": detail,
                "property": property_value,
                "sitemap_url": sitemap_url,
            }

        # The PUT endpoint intentionally returns an empty body. Verify the
        # sitemap through Google's GET resource before claiming registration.
        resource, verify_status = await _google_get_sitemap(
            http,
            connection,
            db,
            property_value,
            sitemap_url,
            token,
        )

    base = {
        "submitted": True,
        "sitemap_url": sitemap_url,
        "property": property_value,
    }

    if resource:
        contents = resource.get("contents") or []
        submitted_urls = sum(
            int(item.get("submitted") or 0)
            for item in contents
            if isinstance(item, dict)
        )
        errors = int(resource.get("errors") or 0)
        warnings = int(resource.get("warnings") or 0)
        pending = bool(resource.get("isPending"))

        if errors:
            message = (
                "Google registered the sitemap, but Search Console reports "
                f"{errors} sitemap error(s). Open the sitemap details in Search Console."
            )
            status_value = "registered_with_errors"
        elif pending:
            message = (
                "Google registered the sitemap and is still processing it. "
                "Search Console's discovered-page counts can update asynchronously."
            )
            status_value = "registered_pending"
        else:
            message = (
                "Google registered the sitemap successfully. Search Console "
                "may take additional time to update Last read and discovered-page counts."
            )
            status_value = "registered"

        return {
            **base,
            "status": status_value,
            "message": message,
            "gsc_path": resource.get("path"),
            "gsc_last_submitted": resource.get("lastSubmitted"),
            "gsc_last_downloaded": resource.get("lastDownloaded"),
            "gsc_is_pending": pending,
            "gsc_is_sitemaps_index": bool(resource.get("isSitemapsIndex")),
            "gsc_type": resource.get("type"),
            "gsc_errors": errors,
            "gsc_warnings": warnings,
            "gsc_submitted_urls": submitted_urls,
            "gsc_contents": contents,
        }

    # PUT succeeded but Google's read-after-write view is not visible yet.
    # This is still a successful submission; do not fabricate a crawl/index result.
    if verify_status == "not_visible_yet":
        return {
            **base,
            "status": "submitted_pending_verification",
            "message": (
                "Google accepted the sitemap submission. Search Console has not "
                "returned the sitemap resource yet; its report is eventually consistent. "
                "Refresh later to see Last read and discovered-page counts."
            ),
            "gsc_verification": "pending",
        }

    if verify_status == "timeout":
        return {
            **base,
            "status": "submitted_verification_timeout",
            "message": (
                "Google accepted the sitemap submission, but the follow-up Search Console "
                "verification timed out. The sitemap may still appear after Google processes it."
            ),
            "gsc_verification": "timeout",
        }

    return {
        **base,
        "status": "submitted",
        "message": (
            "Google accepted the sitemap submission. The Search Console report updates "
            "asynchronously; submission does not mean the URLs are indexed."
        ),
        "gsc_verification": verify_status,
    }

async def _run_crawl(
    run_id: str,
    company_id: str,
    client_id: str,
    site: str,
    payload: CrawlRequest,
) -> None:
    db = SessionLocal()
    advisory_lock_acquired = False
    lock_key = f"boost_rankers:page_post_indexing:{company_id}:{client_id}"
    try:
        # Only one Page & Post crawl may mutate a client's indexing rows at a time.
        # Manual crawls and the unattended automation can otherwise overlap and
        # acquire PostgreSQL relation/index locks in different orders, causing
        # deadlocks during the ON CONFLICT upserts and run-progress UPDATEs.
        lock_row = db.execute(
            text("SELECT pg_try_advisory_lock(hashtextextended(:lock_key, 0)) AS acquired"),
            {"lock_key": lock_key},
        ).scalar()
        advisory_lock_acquired = bool(lock_row)
        if not advisory_lock_acquired:
            db.execute(
                text(
                    "UPDATE page_post_indexing_runs "
                    "SET status='skipped', completed_at=:now, "
                    "progress_message=:message, google_message=:google_message "
                    "WHERE id=:id AND company_id=:company_id"
                ),
                {
                    "id": run_id,
                    "company_id": company_id,
                    "now": _now(),
                    "message": "Crawl skipped because another Page & Post crawl is already running for this client.",
                    "google_message": "Retry after the active crawl completes.",
                },
            )
            db.commit()
            logger.info(
                "Skipped overlapping Page/Post crawl %s for client %s; another crawl holds the advisory lock.",
                run_id,
                client_id,
            )
            return

        db.execute(
            text(
                "UPDATE page_post_indexing_runs "
                "SET status='running', started_at=:now, progress_message=:message "
                "WHERE id=:id AND company_id=:company_id"
            ),
            {
                "id": run_id,
                "company_id": company_id,
                "now": _now(),
                "message": "Discovering WordPress Posts and Pagesâ€¦",
            },
        )
        db.commit()

        wp_items: list[dict[str, Any]] = []
        try:
            wp_items, _, _ = await _discover_wp_items(
                site,
                username=payload.wordpress_username,
                password=payload.wordpress_application_password,
                include_posts=payload.include_posts,
                include_pages=payload.include_pages,
                max_urls=payload.max_urls,
            )
        except Exception as wp_exc:
            logger.warning("WordPress discovery failed; falling back to sitemap: %s", wp_exc)
            wp_items, _ = await _discover_from_sitemap(site, payload.max_urls)

        if not wp_items:
            wp_items, _ = await _discover_from_sitemap(site, payload.max_urls)

        # Deduplicate by canonical URL and keep WordPress-native content types when known.
        deduped: dict[str, dict[str, Any]] = {}
        for item in wp_items:
            key = _url_key(item["url"])
            if not key:
                continue
            existing = deduped.get(key)
            if existing is None or existing.get("content_type") == "unknown":
                deduped[key] = item

        items = list(deduped.values())[:payload.max_urls]

        db.execute(
            text(
                "UPDATE page_post_indexing_runs "
                "SET total_urls=:total, discovered_urls=:total, progress_message=:message "
                "WHERE id=:id"
            ),
            {
                "id": run_id,
                "total": len(items),
                "message": f"Discovered {len(items)} URL(s). Crawlingâ€¦",
            },
        )
        db.commit()

        crawled = 0
        indexable = 0
        errors = 0
        indexed = 0
        not_indexed = 0

        # Keep HTTP concurrency conservative for small-memory deployments.
        semaphore = asyncio.Semaphore(4)

        async def crawl_bounded(item: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await _crawl_url(item)

        for start in range(0, len(items), 25):
            batch = items[start : start + 25]
            results = await asyncio.gather(*(crawl_bounded(item) for item in batch))

            for result in results:
                item_id = str(uuid.uuid4())
                google = {
                    "status": "not_checked",
                    "message": "Google URL Inspection not requested.",
                }

                if payload.verify_google_index and result.get("indexable") and result.get("crawl_status") == "ok":
                    try:
                        google = await _google_inspect(db, company_id, result["final_url"] or result["url"])
                    except Exception as exc:
                        google = {"status": "error", "message": str(exc)[:1000]}

                google_status = google.get("status") or "not_checked"
                if google_status == "indexed":
                    indexed += 1
                elif google_status == "not_indexed":
                    not_indexed += 1

                if result.get("crawl_status") == "ok":
                    crawled += 1
                else:
                    errors += 1
                if result.get("indexable"):
                    indexable += 1

                evidence = {
                    "modified": result.get("modified"),
                    "wordpress_id": result.get("wordpress_id"),
                    "content_type": result.get("content_type"),
                }

                db.execute(
                    text(
                        """
                        INSERT INTO page_post_indexing_items (
                            id, company_id, client_id, run_id, wordpress_id,
                            content_type, url, final_url, title, h1, canonical_url,
                            http_status, content_type_header, robots_meta, x_robots_tag,
                            indexable, indexability_reason, crawl_status,
                            google_index_status, google_verdict, google_coverage_state,
                            google_last_crawl_time, google_canonical, user_canonical,
                            crawled_at, inspected_at, error_message, evidence, updated_at
                        ) VALUES (
                            :id, :company_id, :client_id, :run_id, :wordpress_id,
                            :content_type, :url, :final_url, :title, :h1, :canonical_url,
                            :http_status, :content_type_header, :robots_meta, :x_robots_tag,
                            :indexable, :indexability_reason, :crawl_status,
                            :google_index_status, :google_verdict, :google_coverage_state,
                            :google_last_crawl_time, :google_canonical, :user_canonical,
                            :crawled_at, :inspected_at, :error_message, :evidence, :updated_at
                        )
                        ON CONFLICT (company_id, client_id, url)
                        DO UPDATE SET
                            run_id=EXCLUDED.run_id,
                            wordpress_id=EXCLUDED.wordpress_id,
                            content_type=EXCLUDED.content_type,
                            final_url=EXCLUDED.final_url,
                            title=EXCLUDED.title,
                            h1=EXCLUDED.h1,
                            canonical_url=EXCLUDED.canonical_url,
                            http_status=EXCLUDED.http_status,
                            content_type_header=EXCLUDED.content_type_header,
                            robots_meta=EXCLUDED.robots_meta,
                            x_robots_tag=EXCLUDED.x_robots_tag,
                            indexable=EXCLUDED.indexable,
                            indexability_reason=EXCLUDED.indexability_reason,
                            crawl_status=EXCLUDED.crawl_status,
                            google_index_status=EXCLUDED.google_index_status,
                            google_verdict=EXCLUDED.google_verdict,
                            google_coverage_state=EXCLUDED.google_coverage_state,
                            google_last_crawl_time=EXCLUDED.google_last_crawl_time,
                            google_canonical=EXCLUDED.google_canonical,
                            user_canonical=EXCLUDED.user_canonical,
                            crawled_at=EXCLUDED.crawled_at,
                            inspected_at=EXCLUDED.inspected_at,
                            error_message=EXCLUDED.error_message,
                            evidence=EXCLUDED.evidence,
                            updated_at=EXCLUDED.updated_at
                        """
                    ),
                    {
                        "id": item_id,
                        "company_id": company_id,
                        "client_id": client_id,
                        "run_id": run_id,
                        "wordpress_id": result.get("wordpress_id"),
                        "content_type": result.get("content_type") or "unknown",
                        "url": result["url"],
                        "final_url": result.get("final_url"),
                        "title": result.get("title"),
                        "h1": result.get("h1"),
                        "canonical_url": result.get("canonical_url"),
                        "http_status": result.get("http_status"),
                        "content_type_header": result.get("content_type_header"),
                        "robots_meta": result.get("robots_meta"),
                        "x_robots_tag": result.get("x_robots_tag"),
                        "indexable": result.get("indexable"),
                        "indexability_reason": result.get("indexability_reason"),
                        "crawl_status": result.get("crawl_status"),
                        "google_index_status": google_status,
                        "google_verdict": google.get("verdict"),
                        "google_coverage_state": google.get("coverage_state") or google.get("message"),
                        "google_last_crawl_time": google.get("last_crawl_time"),
                        "google_canonical": google.get("google_canonical"),
                        "user_canonical": google.get("user_canonical"),
                        "crawled_at": _now(),
                        "inspected_at": _now() if google_status not in {"not_checked", "not_connected", "not_configured"} else None,
                        "error_message": result.get("error_message") or google.get("message"),
                        "evidence": _json(evidence | {"google": google}),
                        "updated_at": _now(),
                    },
                )

            db.execute(
                text(
                    "UPDATE page_post_indexing_runs SET crawled_urls=:crawled, "
                    "indexable_urls=:indexable, indexed_urls=:indexed, "
                    "not_indexed_urls=:not_indexed, error_urls=:errors, "
                    "progress_message=:message WHERE id=:id"
                ),
                {
                    "id": run_id,
                    "crawled": crawled,
                    "indexable": indexable,
                    "indexed": indexed,
                    "not_indexed": not_indexed,
                    "errors": errors,
                    "message": f"Crawled {min(start + len(batch), len(items))} of {len(items)} URL(s)â€¦",
                },
            )
            db.commit()

        sitemap_url = None
        sitemap_result = {
            "submitted": False,
            "status": "not_requested",
            "message": "Sitemap submission not requested.",
        }
        if payload.submit_sitemap:
            try:
                discovery = await _discover_submission_sitemap(site)
                sitemap_url = discovery.get("sitemap_url")
                if discovery.get("status") == "ok" and sitemap_url:
                    sitemap_result = await _google_submit_sitemap(
                        db,
                        company_id,
                        sitemap_url,
                    )
                else:
                    sitemap_result = {
                        "submitted": False,
                        "status": discovery.get("status", "error"),
                        "message": discovery.get("message", "No valid sitemap was found."),
                    }
            except Exception as exc:
                logger.exception("Sitemap discovery/submission failed for %s", site)
                sitemap_result = {
                    "submitted": False,
                    "status": "error",
                    "message": str(exc)[:1000],
                }

        final_status = "completed"
        db.execute(
            text(
                """
                UPDATE page_post_indexing_runs
                SET status=:status, completed_at=:completed, progress_message=:message,
                    crawled_urls=:crawled, indexable_urls=:indexable,
                    indexed_urls=:indexed, not_indexed_urls=:not_indexed,
                    error_urls=:errors, sitemap_submitted=:submitted,
                    sitemap_url=:sitemap_url, google_message=:google_message
                WHERE id=:id AND company_id=:company_id
                """
            ),
            {
                "status": final_status,
                "completed": _now(),
                "message": "Page and Post crawl completed.",
                "crawled": crawled,
                "indexable": indexable,
                "indexed": indexed,
                "not_indexed": not_indexed,
                "errors": errors,
                "submitted": bool(sitemap_result.get("submitted")),
                "sitemap_url": sitemap_url,
                "google_message": sitemap_result.get("message"),
                "id": run_id,
                "company_id": company_id,
            },
        )
        db.commit()

    except Exception as exc:
        logger.exception("Page/Post Indexing crawl failed")
        try:
            db.rollback()
            db.execute(
                text(
                    "UPDATE page_post_indexing_runs SET status='failed', completed_at=:now, "
                    "progress_message=:message WHERE id=:id AND company_id=:company_id"
                ),
                {
                    "now": _now(),
                    "message": f"Scan failed: {str(exc)[:900]}",
                    "id": run_id,
                    "company_id": company_id,
                },
            )
            db.commit()
        except Exception:
            db.rollback()
    finally:
        if advisory_lock_acquired:
            try:
                db.execute(
                    text("SELECT pg_advisory_unlock(hashtextextended(:lock_key, 0))"),
                    {"lock_key": lock_key},
                )
                db.commit()
            except Exception:
                db.rollback()
        db.close()



async def _run_automatic_client_cycle(
    company_id: str,
    client_id: str,
    site: str,
) -> None:
    """
    Safe unattended cycle:
    - discovers public WordPress Posts/Pages (or sitemap URLs),
    - crawls a bounded number of URLs,
    - submits the site's sitemap to the connected Search Console property.

    No WordPress credentials are stored or required for the unattended cycle.
    Google individual-URL submission is intentionally not fabricated; normal
    pages/posts are discovered through the sitemap.
    """
    db = SessionLocal()
    try:
        run_id = str(uuid.uuid4())
        db.execute(
            text(
                """
                INSERT INTO page_post_indexing_runs
                    (id, company_id, client_id, status, progress_message)
                VALUES
                    (:id, :company_id, :client_id, 'queued',
                     'Automatic discovery/crawl queuedâ€¦')
                """
            ),
            {"id": run_id, "company_id": company_id, "client_id": client_id},
        )
        db.commit()

        payload = CrawlRequest(
            client_id=client_id,
            wordpress_site=site,
            include_posts=True,
            include_pages=True,
            max_urls=200,
            verify_google_index=False,
            submit_sitemap=True,
        )

        await _run_crawl(
            run_id,
            company_id,
            client_id,
            site,
            payload,
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Automatic Page/Post Indexing cycle failed for client %s",
            client_id,
        )
    finally:
        db.close()


async def run_page_post_indexing_automation_once() -> None:
    """
    Run one bounded cycle across clients.

    This intentionally uses short-lived DB sessions and never keeps a session
    open while HTTP crawling or Google API calls are running.
    """
    db = SessionLocal()
    try:
        clients = (
            db.query(Client)
            .filter(
                Client.website.isnot(None),
                Client.website != "",
            )
            .order_by(Client.created_at.asc())
            .limit(1000)
            .all()
        )
        targets = [
            (str(client.company_id), str(client.id), str(client.website))
            for client in clients
            if client.company_id and client.website
        ]
    finally:
        db.close()

    # Keep unattended work strictly bounded. Do not create hundreds/thousands
    # of coroutine objects at once on small-memory deployments.
    concurrency = 2
    batch_size = 10

    for start in range(0, len(targets), batch_size):
        batch = targets[start : start + batch_size]
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded(target: tuple[str, str, str]) -> None:
            async with semaphore:
                await _run_automatic_client_cycle(*target)

        await asyncio.gather(
            *(bounded(target) for target in batch),
            return_exceptions=True,
        )


async def page_post_indexing_automation_loop() -> None:
    """
    Background automation loop.

    PAGE_POST_INDEXING_AUTO_ENABLED=true enables it.
    PAGE_POST_INDEXING_INTERVAL_SECONDS controls cadence and defaults to 6 hours.
    """
    import os

    if os.getenv("PAGE_POST_INDEXING_AUTO_ENABLED", "false").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        logger.info("Page/Post automatic indexing discovery is disabled by environment.")
        return

    try:
        interval = max(
            3600,
            int(os.getenv("PAGE_POST_INDEXING_INTERVAL_SECONDS", "21600")),
        )
    except ValueError:
        interval = 21600

    logger.info(
        "Page/Post automatic indexing discovery enabled; interval=%ss",
        interval,
    )

    while True:
        try:
            await run_page_post_indexing_automation_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Page/Post automatic indexing automation cycle failed.")
        await asyncio.sleep(interval)


@router.get("/overview")
def overview(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    company_id = _company_id(current_user)
    _client_for_company(db, client_id, company_id)

    row = db.execute(
        text(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE content_type='page') AS pages,
                COUNT(*) FILTER (WHERE content_type='post') AS posts,
                COUNT(*) FILTER (WHERE crawl_status='ok') AS crawled,
                COUNT(*) FILTER (WHERE indexable IS TRUE) AS indexable,
                COUNT(*) FILTER (WHERE google_index_status='indexed') AS indexed,
                COUNT(*) FILTER (WHERE google_index_status='not_indexed') AS not_indexed,
                COUNT(*) FILTER (WHERE indexability_reason='noindex') AS noindex,
                COUNT(*) FILTER (WHERE crawl_status IN ('error','timeout')) AS errors
            FROM page_post_indexing_items
            WHERE company_id=:company_id AND client_id=:client_id
            """
        ),
        {"company_id": company_id, "client_id": client_id},
    ).mappings().one()

    return {"overview": dict(row)}


@router.get("/items")
def list_items(
    client_id: str,
    content_type: str | None = Query(default=None, pattern="^(post|page|unknown)$"),
    google_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    company_id = _company_id(current_user)
    _client_for_company(db, client_id, company_id)

    clauses = ["company_id=:company_id", "client_id=:client_id"]
    params: dict[str, Any] = {
        "company_id": company_id,
        "client_id": client_id,
        "limit": limit,
    }
    if content_type:
        clauses.append("content_type=:content_type")
        params["content_type"] = content_type
    if google_status:
        clauses.append("google_index_status=:google_status")
        params["google_status"] = google_status

    rows = db.execute(
        text(
            f"""
            SELECT id, wordpress_id, content_type, url, final_url, title, h1,
                   canonical_url, http_status, robots_meta, x_robots_tag,
                   indexable, indexability_reason, crawl_status,
                   google_index_status, google_verdict, google_coverage_state,
                   google_last_crawl_time, google_canonical, user_canonical,
                   submitted_at, crawled_at, inspected_at, error_message,
                   created_at, updated_at
            FROM page_post_indexing_items
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()

    return {"items": [dict(row) for row in rows]}


@router.get("/runs")
def list_runs(
    client_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    company_id = _company_id(current_user)
    _client_for_company(db, client_id, company_id)
    rows = db.execute(
        text(
            """
            SELECT *
            FROM page_post_indexing_runs
            WHERE company_id=:company_id AND client_id=:client_id
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"company_id": company_id, "client_id": client_id, "limit": limit},
    ).mappings().all()
    return {"runs": [dict(row) for row in rows]}


@router.post("/crawl", status_code=status.HTTP_202_ACCEPTED)
async def start_crawl(
    payload: CrawlRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    company_id = _company_id(current_user)
    client = _client_for_company(db, payload.client_id, company_id)

    site = _clean_site(str(payload.wordpress_site or client.website or ""))
    if not site:
        raise HTTPException(status_code=400, detail="Client website is required.")

    run_id = str(uuid.uuid4())
    db.execute(
        text(
            """
            INSERT INTO page_post_indexing_runs
                (id, company_id, client_id, status, progress_message)
            VALUES
                (:id, :company_id, :client_id, 'queued', 'Crawl queuedâ€¦')
            """
        ),
        {"id": run_id, "company_id": company_id, "client_id": client.id},
    )
    db.commit()

    # Manual UI crawls are authoritative Google-verification runs.
    # Enforce URL Inspection here so a stale frontend/default cannot silently
    # create a run whose rows are marked "not_checked". The unattended
    # automation calls _run_crawl directly with verify_google_index=False and
    # therefore remains quota-safe.
    manual_payload = payload.model_copy(update={"verify_google_index": True})

    background_tasks.add_task(
        _run_crawl,
        run_id,
        company_id,
        str(client.id),
        site,
        manual_payload,
    )

    return {
        "success": True,
        "run_id": run_id,
        "message": "Page and Post crawl queued.",
    }


@router.post("/submit-sitemap", status_code=status.HTTP_202_ACCEPTED)
async def submit_sitemap(
    payload: SubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    company_id = _company_id(current_user)
    client = _client_for_company(db, payload.client_id, company_id)
    site = _clean_site(str(client.website or ""))

    # If the user supplies a sitemap, validate that exact URL. Otherwise discover
    # the site's verified sitemap from robots.txt and standard WordPress candidates.
    discovery = await _discover_submission_sitemap(
        site,
        str(payload.sitemap_url) if payload.sitemap_url else None,
    )

    if discovery.get("status") != "ok" or not discovery.get("sitemap_url"):
        raise HTTPException(
            status_code=400,
            detail=discovery.get("message") or "No valid sitemap was found for this website.",
        )

    result = await _google_submit_sitemap(
        db,
        company_id,
        str(discovery["sitemap_url"]),
    )
    if not result.get("submitted"):
        result["discovery_source"] = discovery.get("source")
        result["sitemap_kind"] = discovery.get("kind")
        result["discovered_entries"] = discovery.get("loc_count")
    else:
        result["discovery_source"] = discovery.get("source")
        result["sitemap_kind"] = discovery.get("kind")
        result["discovered_entries"] = discovery.get("loc_count")

    if not result.get("submitted") and result.get("status") == "not_connected":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/inspect", status_code=status.HTTP_200_OK)
async def inspect_url(
    payload: InspectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    company_id = _company_id(current_user)
    _client_for_company(db, payload.client_id, company_id)
    url = str(payload.url)
    result = await _google_inspect(db, company_id, url)
    return {"url": url, "inspection": result}


@router.get("/status")
def feature_status(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    company_id = _company_id(current_user)
    client = _client_for_company(db, client_id, company_id)
    connection = get_connection(db, company_id, "search_console")
    return {
        "client_id": client_id,
        "website": client.website,
        "google_search_console_connected": connection is not None,
        "google_url_inspection": "available_if_oauth_scope_allows",
        "automatic_google_individual_url_submission": False,
        "automatic_discovery": True,
        "automatic_sitemap_submission": True,
    }
