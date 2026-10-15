from __future__ import annotations

import math
import os
import asyncio
import re
import threading
import hashlib
import time
from pathlib import Path
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, String, and_, func, text
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
LIVE_SERP_PROVIDER = os.getenv(
    "LIVE_SERP_PROVIDER",
    "local_playwright",
).strip().lower() or "local_playwright"


class LiveSERPError(RuntimeError):
    """Raised when the live SERP provider cannot return usable results."""
    
SUPPORTED_LIVE_SERP_PROVIDERS = {"local_playwright"}


# Limit Chromium processes globally. This protects the local machine and database
# from concurrent live checks when several users click Live Google at once.
_PLAYWRIGHT_GATE = threading.BoundedSemaphore(1)



def _live_serp_profile_dir(target_domain: str | None) -> Path:
    """Return a stable local Chromium profile for the live Google checker."""
    root = Path(os.getenv("LIVE_SERP_PROFILE_DIR", ".live_serp_profiles"))
    domain = (target_domain or "default").strip().lower() or "default"
    key = hashlib.sha256(domain.encode("utf-8")).hexdigest()[:20]
    path = root / key
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_configured() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except Exception:
        return False


def configuration_message() -> str:
    return (
        "Windows Playwright is not installed. Run `pip install playwright` "
        "and `python -m playwright install chromium`."
    )


def _normalize_live_host(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        return (parsed.hostname or "").strip().lower().removeprefix("www.")
    except Exception:
        return ""


def _normalize_live_url(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        host = (parsed.hostname or "").strip().lower().removeprefix("www.")
        path = parsed.path.rstrip("/") or "/"
        return f"{host}{path}"
    except Exception:
        return raw.rstrip("/").lower()

def _normalize_live_text_urls(value: str | None) -> set[str]:
    """Extract and normalize URLs printed as text inside Google result blocks."""
    text_value = (value or "").strip()
    if not text_value:
        return set()
    matches = re.findall(r"https?://[^\s<>\"]+", text_value, flags=re.IGNORECASE)
    normalized: set[str] = set()
    for match in matches:
        cleaned = match.rstrip(".,;:)")
        value_norm = _normalize_live_url(cleaned)
        if value_norm:
            normalized.add(value_norm)
    return normalized




def _is_google_goto_url(value: str | None) -> bool:
    """Return True for Google's navigation/redirect wrappers."""
    raw = (value or "").strip()
    if not raw:
        return False
    try:
        parsed = urlparse(raw)
        host = (parsed.hostname or "").strip().lower().removeprefix("www.")
        path = parsed.path.rstrip("/").lower()
        return (
            host in {"google.com", "googleusercontent.com"}
            and path in {"/goto", "/url", "/search"}
            and bool(parsed.query)
        )
    except Exception:
        return False

def _extract_wrapped_destination(value: str | None) -> list[str]:
    """Extract destination URLs from Google's encoded redirect parameters."""
    raw = (value or "").strip()
    if not raw:
        return []
    values: list[str] = []
    seen: set[str] = set()

    def add(candidate: str | None) -> None:
        candidate = unquote((candidate or "").strip())
        if not candidate:
            return
        if candidate.startswith("//"):
            candidate = "https:" + candidate
        if candidate.startswith("/"):
            candidate = "https://www.google.com" + candidate
        if not candidate.startswith(("http://", "https://")):
            return
        if candidate not in seen:
            seen.add(candidate)
            values.append(candidate)

    pending = [raw]
    for _ in range(3):
        current = pending
        pending = []
        for item in current:
            add(item)
            try:
                parsed = urlparse(item if "://" in item else f"https://www.google.com{item}")
                params = parse_qs(parsed.query)
                for key in ("url", "q", "u", "target", "dest", "destination", "uddg"):
                    for nested in params.get(key, []):
                        nested = unquote(nested)
                        if nested.startswith(("http://", "https://")):
                            add(nested)
                            pending.append(nested)
            except Exception:
                continue
    return values


async def _resolve_google_goto_url(
    client: Any,
    value: str,
) -> str:
    """Resolve a Google /goto wrapper using Google's redirect chain only."""

    if not value:
        return value

    try:
        response = await client.get(
            value,
            follow_redirects=False,
        )
        location = response.headers.get("location")

        if location and not _is_google_goto_url(location):
            return location
    except Exception:
        pass

    try:
        response = await client.get(
            value,
            follow_redirects=True,
        )
        final_url = str(response.url)

        if final_url and not _is_google_goto_url(final_url):
            return final_url
    except Exception:
        pass

    return value


async def _resolve_live_result_urls(
    organic: list[dict[str, Any]],
    target_domain: str | None,
    target_url: str | None = None,
) -> list[tuple[dict[str, Any], str]]:
    """Resolve Google /goto result URLs in bounded concurrent batches."""
    import httpx

    candidates = [(item, str(item.get("url") or "")) for item in organic]
    if not target_domain and not target_url:
        return candidates
    target_url_norm = _normalize_live_url(target_url)

    timeout = max(3.0, float(os.getenv("LIVE_SERP_RESULT_RESOLVE_TIMEOUT", "8")))
    headers = {
        "User-Agent": os.getenv(
            "LIVE_SERP_RESOLVE_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/154 Safari/537.36",
        )
    }
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=10)
    resolved: list[tuple[dict[str, Any], str]] = []

    async with httpx.AsyncClient(
        timeout=timeout,
        headers=headers,
        limits=limits,
    ) as client:
        for start in range(0, len(candidates), 10):
            batch = candidates[start:start + 10]
            tasks = [
                _resolve_google_goto_url(client, url)
                if _is_google_goto_url(url)
                else _noop_live_url(url)
                for _, url in batch
            ]
            urls = await asyncio.gather(*tasks)
            for (item, original_url), resolved_url in zip(batch, urls):
                final_url = resolved_url or original_url
                resolved.append((item, final_url))
                if target_url_norm and _normalize_live_url(final_url) == target_url_norm:
                    return resolved
                if not target_url_norm and _normalize_live_host(final_url) == target_domain:
                    return resolved

    return resolved


async def _noop_live_url(value: str) -> str:
    return value


async def check_google_organic_rank(
    *,
    keyword: str,
    location: str,
    language: str = "en",
    device: str = "desktop",
    target_url: str | None = None,
    target_domain: str | None = None,
    allow_domain_fallback: bool = False,
) -> dict[str, Any]:
    """Check live Google organic results with Windows Playwright.

    Playwright is executed in a dedicated worker thread so FastAPI/Uvicorn's
    Windows event loop cannot interfere with Playwright's Chromium subprocess.
    Google Search Console remains the source of historical GSC metrics.
    """
    if LIVE_SERP_PROVIDER not in SUPPORTED_LIVE_SERP_PROVIDERS:
        raise LiveSERPError(
            f"Unsupported live SERP provider: {LIVE_SERP_PROVIDER}. "
            "The free local provider is 'local_playwright'."
        )
    
    if not is_configured():
        raise LiveSERPError(configuration_message())

    location = (location or "").strip()
    if not location:
        raise LiveSERPError("A city/location is required for a live SERP check.")

    language = (language or "en").strip().lower() or "en"
    device = (device or "desktop").strip().lower() or "desktop"
    if device == "all":
        device = "desktop"
    if device != "desktop":
        raise LiveSERPError("Windows Playwright live rank checking currently uses desktop Google results.")

    import asyncio as _asyncio

    result = await _asyncio.to_thread(
        _check_google_playwright_sync,
        keyword.strip(),
        location,
        language,
        target_url,
        target_domain,
        allow_domain_fallback,
    )
    return result


def _check_google_playwright_sync(
    keyword: str,
    location: str,
    language: str,
    target_url: str | None,
    target_domain: str | None,
    allow_domain_fallback: bool,
) -> dict[str, Any]:
    """Run one real-time Google organic rank check with Windows Playwright.

    Important: this function is intentionally self-contained. It does not use
    SQLAlchemy or any database connection while Chromium is running.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

    wanted_url = _normalize_live_url(target_url)
    wanted_domain = _normalize_live_host(target_domain) or _normalize_live_host(target_url)

    location = (location or "").strip()
    language = (language or "en").strip().lower() or "en"
    if not location:
        raise LiveSERPError("A city/location is required for a live SERP check.")

    # Keep the user's keyword intact when it already contains the city.
    # Otherwise append the city so the live check remains location-aware.
    search_text = keyword.strip()
    city = location.split(",", 1)[0].strip()
    if city and city.lower() not in search_text.lower():
        search_text = f"{search_text} {city}".strip()

    from urllib.parse import quote
    country = os.getenv("LIVE_SERP_GOOGLE_COUNTRY", "au").strip().lower() or "au"
    gl = country[:2]
    # IMPORTANT: `gl=au` only selects the country; it does not reliably
    # reproduce a Perth-local Google SERP. When the keyword already contains
    # "Perth", the old logic skipped adding the location to the query, so
    # Google could return results based on the machine's actual location
    # instead of the requested Perth location.
    #
    # Use Google's UULE location parameter so the live check is genuinely
    # location-aware while keeping the keyword itself unchanged.
    def _google_uule(value: str) -> str:
        raw = value.strip()
        payload = bytearray((0x08, 0x02, 0x10, 0x20))
        encoded = raw.encode("utf-8")
        length = len(encoded)
        while length > 0x7F:
            payload.append((length & 0x7F) | 0x80)
            length >>= 7
        payload.append(length)
        payload.extend(encoded)
        import base64
        return "w+" + base64.b64encode(bytes(payload)).decode("ascii")

    url = (
        "https://www.google.com/search?q=" + quote(search_text)
        + "&num=100&hl=" + quote(language)
        + "&gl=" + quote(gl)
        + "&uule=" + quote(_google_uule(location))
        + "&pws=0&filter=0"
    )

    acquired = _PLAYWRIGHT_GATE.acquire(timeout=90)
    if not acquired:
        raise LiveSERPError("Live Google rank service is busy. Please try again shortly.")

    try:
        with sync_playwright() as p:
            # Use a persistent local profile so a CAPTCHA solved once can leave
            # Google's verification cookie/session available to the next keyword.
            # The normal browser is headless; a visible browser is opened only
            # when Google actually asks for human verification.
            profile_dir = _live_serp_profile_dir(wanted_domain or target_domain)
            launch_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=True,
                args=launch_args,
                locale=f"{language}-{gl.upper()}",
                viewport={"width": 1366, "height": 900},
            )
            browser = None
            try:
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)

                def google_verification_required() -> bool:
                    """Detect Google's verification page using URL, text and DOM markers."""
                    current_url = page.url.lower()
                    try:
                        body_text = page.locator("body").inner_text(timeout=3000).lower()
                    except Exception:
                        body_text = ""

                    try:
                        iframe_count = page.locator(
                            "iframe[src*='recaptcha'], iframe[title*='recaptcha' i], "
                            "iframe[src*='captcha'], iframe[title*='captcha' i]"
                        ).count()
                    except Exception:
                        iframe_count = 0

                    try:
                        marker_count = page.locator(
                            "#captcha-form, form[action*='/sorry/'], "
                            "[data-sitekey], [id*='captcha' i], [class*='captcha' i]"
                        ).count()
                    except Exception:
                        marker_count = 0

                    return (
                        "/sorry/" in current_url
                        or "our systems have detected unusual traffic" in body_text
                        or "unusual traffic from your computer network" in body_text
                        or "verify you are human" in body_text
                        or "recaptcha" in body_text
                        or "captcha" in body_text
                        or iframe_count > 0
                        or marker_count > 0
                    )

                def open_visible_verification_session(navigation_url: str | None = None) -> None:
                    nonlocal context, page
                    try:
                        context.close()
                    except Exception:
                        pass

                    context = p.chromium.launch_persistent_context(
                        user_data_dir=str(profile_dir),
                        headless=False,
                        args=launch_args,
                        locale=f"{language}-{gl.upper()}",
                        viewport={"width": 1366, "height": 900},
                    )
                    page = context.new_page()
                    page.goto(navigation_url or url, wait_until="domcontentloaded", timeout=60000)

                    verification_timeout = max(
                        30,
                        int(os.getenv("LIVE_SERP_MANUAL_VERIFICATION_TIMEOUT", "180")),
                    )
                    deadline = datetime.now(UTC).timestamp() + verification_timeout

                    while datetime.now(UTC).timestamp() < deadline:
                        page.wait_for_timeout(2000)
                        if not google_verification_required():
                            break

                    if google_verification_required():
                        raise LiveSERPError(
                            "Google requires manual verification. "
                            "Complete the CAPTCHA in the visible Chromium window "
                            "before the verification timeout expires."
                        )

                    page.wait_for_timeout(2500)

                if google_verification_required():
                    open_visible_verification_session()

                # The request is intentionally a single Google request with
                # num=100. We do not issue seven separate automated searches.
                # Google identifies rank-checking/search-scraper traffic as
                # automated traffic, so keeping one verified SERP request is
                # materially safer than paginating seven requests.
                try:
                    page.wait_for_selector("h3", timeout=15000)
                except PlaywrightTimeoutError:
                    # A challenge can appear after the initial navigation without
                    # putting "recaptcha" into body text. Re-check the DOM before
                    # treating the page as a SERP parsing failure.
                    if google_verification_required():
                        open_visible_verification_session()
                    else:
                        page.wait_for_timeout(2000)

                if google_verification_required():
                    open_visible_verification_session()

                candidates: list[dict[str, Any]] = []
                seen_candidate_keys: set[str] = set()

                def add_candidate(title: str, block_text: str, links: list[dict[str, str]]) -> None:
                    title = (title or "").strip()
                    if not title or not links:
                        return
                    key_parts = [title.lower()]
                    for link in links:
                        key_parts.append((link.get("href") or "").strip())
                    key = "|".join(key_parts)
                    if key in seen_candidate_keys:
                        return
                    seen_candidate_keys.add(key)
                    lower_block = (block_text or "").lower()
                    if (
                        "sponsored results" in lower_block
                        or lower_block.startswith("sponsored")
                        or "people also ask" in lower_block
                        or "ai overview" in lower_block
                    ):
                        return
                    candidates.append({
                        "title": title,
                        "text": (block_text or title).strip(),
                        "links": links,
                    })

                # Primary extractor: modern Google commonly puts the result
                # title h3 directly inside its destination anchor. This avoids
                # relying on Google's changing MjjYud/container classes.
                for h3 in page.locator("h3").all():
                    try:
                        if not h3.is_visible():
                            continue
                        title = h3.inner_text().strip()
                        if not title:
                            continue

                        title_anchor = h3.locator("xpath=ancestor::a[1]")
                        links: list[dict[str, str]] = []
                        if title_anchor.count():
                            try:
                                href = (title_anchor.get_attribute("href") or "").strip()
                                data_rw = (title_anchor.get_attribute("data-rw") or "").strip()
                                if href:
                                    links.append({
                                        "href": href,
                                        "data_rw": data_rw,
                                        "text": title_anchor.inner_text().strip(),
                                    })
                            except Exception:
                                pass

                        # Build a compact result block around the h3. Google
                        # frequently renders the destination/cite text outside
                        # the title anchor, so title-anchor-only parsing loses the
                        # real hostname. Prefer the smallest ancestor that contains
                        # the h3, links, and useful surrounding text.
                        best_block = title
                        best_links = links
                        best_score = None

                        try:
                            ancestors = h3.locator(
                                "xpath=ancestor::div[.//h3 and .//a]"
                            ).all()
                        except Exception:
                            ancestors = []

                        for ancestor in ancestors[:12]:
                            try:
                                if not ancestor.is_visible():
                                    continue
                                text_value = ancestor.inner_text().strip()
                                if not text_value or title.lower() not in text_value.lower():
                                    continue
                                if len(text_value) > 2500:
                                    continue

                                ancestor_links: list[dict[str, str]] = []
                                for anchor in ancestor.locator("a").all():
                                    href = (anchor.get_attribute("href") or "").strip()
                                    data_rw = (anchor.get_attribute("data-rw") or "").strip()
                                    if href or data_rw:
                                        ancestor_links.append({
                                            "href": href,
                                            "data_rw": data_rw,
                                            "text": anchor.inner_text().strip(),
                                        })
                                if not ancestor_links:
                                    continue

                                # Prefer a block that contains a visible hostname
                                # or URL; otherwise prefer the smallest useful block.
                                host_bonus = 0
                                if wanted_domain and wanted_domain in text_value.lower().replace("www.", ""):
                                    host_bonus = 100000
                                score = host_bonus + len(text_value)
                                if best_score is None or score < best_score:
                                    best_score = score
                                    best_block = text_value
                                    best_links = ancestor_links
                            except Exception:
                                continue

                        links = best_links
                        block_text = best_block
                        add_candidate(title, block_text, links)
                    except Exception:
                        continue

                # Secondary extractor: if Google uses an unusual DOM where the
                # title anchor is not an ancestor of h3, use the original
                # container-independent h3 scan as a fallback.
                if not candidates:
                    for h3 in page.locator("h3").all():
                        try:
                            if not h3.is_visible():
                                continue
                            title = h3.inner_text().strip()
                            if not title:
                                continue
                            block = h3.locator("xpath=ancestor::div[contains(@class,'MjjYud')][1]")
                            if block.count() == 0:
                                block = h3.locator("xpath=ancestor::div[.//a][1]")
                            if block.count() == 0:
                                block = h3
                            block_text = block.inner_text().strip()
                            links: list[dict[str, str]] = []
                            for anchor in block.locator("a").all():
                                href = (anchor.get_attribute("href") or "").strip()
                                data_rw = (anchor.get_attribute("data-rw") or "").strip()
                                if href:
                                    links.append({
                                        "href": href,
                                        "data_rw": data_rw,
                                        "text": anchor.inner_text().strip(),
                                    })
                            add_candidate(title, block_text, links)
                        except Exception:
                            continue

                if not candidates:
                    body_text = page.locator("body").inner_text()[:3000]
                    raise LiveSERPError(
                        "Google returned no usable organic result blocks. "
                        f"Page preview: {body_text[:500]}"
                    )

                def all_candidate_urls(candidate: dict[str, Any]) -> list[str]:
                    """Collect destination URLs from Google result links.

                    Google can expose organic destinations as absolute URLs,
                    relative /url or /goto links, data-rw values, or encoded
                    query parameters. Normalize all of those forms before the
                    rank matcher makes a decision.
                    """
                    values: list[str] = []

                    def add(value: str | None) -> None:
                        value = (value or "").strip()
                        if not value:
                            return
                        if value.startswith("/"):
                            value = "https://www.google.com" + value
                        if not value.startswith(("http://", "https://")):
                            return
                        if value not in values:
                            values.append(value)

                    for link in candidate["links"]:
                        for value in (link.get("data_rw"), link.get("href")):
                            add(value)
                            for nested in _extract_wrapped_destination(value):
                                add(nested)
                    return values

                def candidate_text_urls(candidate: dict[str, Any]) -> set[str]:
                    """Extract full URLs plus Google-style breadcrumb URLs from visible text."""
                    text = str(candidate.get("text") or "")
                    normalized = set(_normalize_live_text_urls(text))

                    # Google often renders the destination as a breadcrumb,
                    # e.g. `example.com › path › page`, without printing https://.
                    if wanted_domain:
                        domain_pattern = re.escape(wanted_domain)
                        for match in re.finditer(domain_pattern + r"(?:\s*[›>·/]\s*[^\n|]+)?", text, flags=re.IGNORECASE):
                            raw = match.group(0).strip()
                            raw = re.sub(r"\s*[›>·]\s*", "/", raw)
                            raw = raw.strip(" .|\t")
                            if raw:
                                normalized.add(_normalize_live_url("https://" + raw))

                    return normalized

                def candidate_matches(candidate: dict[str, Any]) -> tuple[bool, bool, str | None]:
                    """Return exact-page, domain, and best direct URL match."""
                    urls = all_candidate_urls(candidate)
                    visible = f"{candidate['title']} {candidate['text']}".lower()
                    text_urls = candidate_text_urls(candidate)

                    exact_hit = False
                    domain_hit = False
                    best_url: str | None = None

                    for candidate_url in urls:
                        normalized = _normalize_live_url(candidate_url)
                        host = _normalize_live_host(candidate_url)
                        if wanted_url and normalized == wanted_url:
                            exact_hit = True
                            best_url = candidate_url
                            break
                        if wanted_domain and host == wanted_domain:
                            domain_hit = True
                            best_url = best_url or candidate_url

                    if wanted_url:
                        for text_url in text_urls:
                            if text_url == wanted_url:
                                exact_hit = True
                                best_url = best_url or target_url
                                break

                    if wanted_domain and wanted_domain in visible:
                        domain_hit = True

                    # Breadcrumbs can identify the target domain/path even when
                    # the anchor href is an opaque Google wrapper.
                    if wanted_domain:
                        for text_url in text_urls:
                            if _normalize_live_host(text_url) == wanted_domain:
                                domain_hit = True
                                if wanted_url and text_url == wanted_url:
                                    exact_hit = True
                                break

                    return exact_hit, domain_hit, best_url

                # Rank is based on the order of actual organic result blocks,
                # not on Google's href/rank attribute. This avoids counting
                # ads, PAA, AI Overview and navigation elements.
                exact_matches: list[tuple[int, str]] = []
                domain_matches: list[tuple[int, str]] = []

                for rank, candidate in enumerate(candidates, start=1):
                    exact_hit, domain_hit, best_url = candidate_matches(candidate)
                    if exact_hit:
                        exact_matches.append((rank, best_url or target_url or ""))
                    if domain_hit:
                        domain_matches.append((rank, best_url or ""))

                # For a GSC-inferred target page, the page itself is preferred,
                # but the domain is a valid fallback because Google can rank a
                # different page from the same site for the current query.
                if wanted_url:
                    matches = exact_matches or (
                        domain_matches if allow_domain_fallback else []
                    )
                else:
                    matches = domain_matches

                # If Google hides the destination behind /goto, resolve only
                # the candidate links that are relevant to the target. First
                # try links whose visible result text already contains the
                # target domain. This is fast and handles Google's current DOM.
                if not matches and wanted_domain:
                    for rank, candidate in enumerate(candidates, start=1):
                        exact_hit, domain_hit, _ = candidate_matches(candidate)
                        if not domain_hit:
                            continue
                        for candidate_url in all_candidate_urls(candidate):
                            if not _is_google_goto_url(candidate_url):
                                continue
                            target_page = None
                            try:
                                target_page = context.new_page()
                                target_page.goto(
                                    candidate_url,
                                    wait_until="commit",
                                    timeout=10000,
                                )
                                final_url = target_page.url
                                final_host = _normalize_live_host(final_url)
                                final_norm = _normalize_live_url(final_url)
                                if final_host == wanted_domain:
                                    if wanted_url:
                                        if final_norm == wanted_url:
                                            matches = [(rank, final_url)]
                                            break
                                        if allow_domain_fallback:
                                            matches = [(rank, final_url)]
                                            break
                                    else:
                                        matches = [(rank, final_url)]
                                        break
                            except Exception:
                                pass
                            finally:
                                if target_page is not None:
                                    try:
                                        target_page.close()
                                    except Exception:
                                        pass
                        if matches:
                            break

                # Final bounded fallback: inspect the first 100 organic
                # candidates, but only navigate Google /goto links. This is
                # necessary when Google exposes neither the destination href
                # nor the destination hostname in the result DOM.
                if not matches and wanted_url:
                    for rank, candidate in enumerate(candidates, start=1):
                        for candidate_url in all_candidate_urls(candidate):
                            if not _is_google_goto_url(candidate_url):
                                continue
                            target_page = None
                            try:
                                target_page = context.new_page()
                                target_page.goto(
                                    candidate_url,
                                    wait_until="commit",
                                    timeout=8000,
                                )
                                final_url = target_page.url
                                if _normalize_live_url(final_url) == wanted_url:
                                    matches = [(rank, final_url)]
                                    break
                                if (
                                    allow_domain_fallback
                                    and wanted_domain
                                    and _normalize_live_host(final_url) == wanted_domain
                                ):
                                    matches = [(rank, final_url)]
                                    break
                            except Exception:
                                pass
                            finally:
                                if target_page is not None:
                                    try:
                                        target_page.close()
                                    except Exception:
                                        pass
                        if matches:
                            break

                # If the first Google SERP page does not contain the target,
                # continue through up to seven result pages in the same persistent
                # browser session. This keeps ranking depth at 70 results while
                # allowing the manual verification cookie to be reused.
                if not matches and wanted_domain:
                    base_search_url = url
                    for page_number in range(1, 7):
                        page_url = (
                            base_search_url
                            + ("&" if "?" in base_search_url else "?")
                            + f"start={page_number * 10}"
                        )
                        try:
                            page.goto(page_url, wait_until="domcontentloaded", timeout=45000)
                            if google_verification_required():
                                open_visible_verification_session(page_url)

                            try:
                                page.wait_for_selector("h3", timeout=10000)
                            except PlaywrightTimeoutError:
                                pass

                            page_candidates: list[dict[str, Any]] = []
                            page_seen: set[str] = set()

                            for h3 in page.locator("h3").all():
                                try:
                                    if not h3.is_visible():
                                        continue
                                    title = h3.inner_text().strip()
                                    if not title:
                                        continue

                                    title_anchor = h3.locator("xpath=ancestor::a[1]")
                                    links: list[dict[str, str]] = []
                                    if title_anchor.count():
                                        href = (title_anchor.get_attribute("href") or "").strip()
                                        data_rw = (title_anchor.get_attribute("data-rw") or "").strip()
                                        if href or data_rw:
                                            links.append({"href": href, "data_rw": data_rw, "text": title_anchor.inner_text().strip()})

                                    container = h3.locator("xpath=ancestor::div[.//h3 and .//a][1]")
                                    block_text = title
                                    if container.count():
                                        try:
                                            block_text = container.inner_text().strip() or title
                                            for anchor in container.locator("a").all():
                                                href = (anchor.get_attribute("href") or "").strip()
                                                data_rw = (anchor.get_attribute("data-rw") or "").strip()
                                                if href or data_rw:
                                                    links.append({"href": href, "data_rw": data_rw, "text": anchor.inner_text().strip()})
                                        except Exception:
                                            pass

                                    key = title.lower() + "|" + "|".join(sorted(x.get("href","") for x in links))
                                    if key not in page_seen:
                                        page_seen.add(key)
                                        lower_block = block_text.lower()
                                        if not any(x in lower_block for x in (
                                            "sponsored results", "people also ask", "ai overview"
                                        )):
                                            page_candidates.append({"title": title, "text": block_text, "links": links})
                                except Exception:
                                    continue

                            for offset, candidate in enumerate(page_candidates, start=1):
                                rank = page_number * 10 + offset
                                exact_hit, domain_hit, best_url = candidate_matches(candidate)
                                if exact_hit or (domain_hit and allow_domain_fallback):
                                    matches = [(rank, best_url or target_url or "")]
                                    break

                            if matches:
                                break
                        except Exception:
                            continue

                if not matches:
                    return {
                        "position": None,
                        "ranking_url": None,
                        "location": location,
                        "language": language,
                        "device": "desktop",
                        "provider": LIVE_SERP_PROVIDER,
                        "message": (
                            f"The target domain '{wanted_domain or '(unknown)'}' was not found in "
                            f"the {min(len(candidates), 100)} parsed Google organic result blocks for this location. "
                            "Google may have returned a different SERP, a verification page, or a result layout "
                            "that did not expose the destination URL."
                        ),
                    }

                rank, ranking_url = min(matches, key=lambda item: item[0])
                return {
                    "position": rank,
                    "ranking_url": ranking_url or target_url,
                    "location": location,
                    "language": language,
                    "device": "desktop",
                    "provider": LIVE_SERP_PROVIDER,
                    "message": f"Live Google organic rank checked for {location} on desktop.",
                }
            finally:
                try:
                    context.close()
                except Exception:
                    pass
                if browser is not None:
                    try:
                        browser.close()
                    except Exception:
                        pass
    except LiveSERPError:
        raise
    except PlaywrightTimeoutError as exc:
        raise LiveSERPError("Local Playwright timed out while loading Google results.") from exc
    except Exception as exc:
        raise LiveSERPError(
            f"Local Playwright live rank check failed: {str(exc)[:500]}"
        ) from exc
    finally:
        _PLAYWRIGHT_GATE.release()

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
    measurement_start_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    measurement_end_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    comparison_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    comparison_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    comparison_position: Mapped[float | None] = mapped_column(Float, nullable=True)
    period: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
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
    keyword_ids: list[str] = Field(default_factory=list, max_length=500)
    period: str = Field(default="daily", max_length=20)
    compare: str = Field(default="previous_period", max_length=30)
    custom_compare_start: date | None = None
    custom_compare_end: date | None = None

    @field_validator("period")
    @classmethod
    def validate_period(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"daily", "weekly", "monthly", "yearly"}:
            raise ValueError("Period must be daily, weekly, monthly, or yearly.")
        return value

    @field_validator("compare")
    @classmethod
    def validate_compare(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"previous_period", "previous_week", "previous_month", "previous_year", "custom"}:
            raise ValueError("Invalid comparison period.")
        return value



class LiveRefreshRequest(BaseModel):
    keyword_ids: list[str] = Field(default_factory=list, max_length=500)
    location: str | None = Field(default=None, max_length=255)
    device: str | None = Field(default=None, max_length=20)
    language: str | None = Field(default=None, max_length=20)



def _company_id(current_user: User) -> str:
    if not current_user.company_id:
        raise HTTPException(status_code=403, detail="A company account is required for rank tracking.")
    return str(current_user.company_id)


def _auto_assign_single_client(db: Session, rows: list[RankTrackingKeyword], company_id: str) -> None:
    """Repair legacy NULL client mappings only when the company has exactly one client."""
    if not rows:
        return
    clients = db.query(Client).filter(
        Client.company_id == company_id,
        Client.deleted_at.is_(None),
    ).all()
    if len(clients) != 1:
        return
    client_id = clients[0].id
    changed = False
    for row in rows:
        if row.client_id is None:
            row.client_id = client_id
            changed = True
    if changed:
        db.commit()


def _latest_gsc_ranking_url(db: Session, row: RankTrackingKeyword) -> str | None:
    """Return the latest measured GSC landing page for legacy unmapped keywords."""
    snapshot = (
        db.query(RankTrackingSnapshot.ranking_url)
        .filter(
            RankTrackingSnapshot.keyword_id == row.id,
            RankTrackingSnapshot.source == "google_search_console",
            RankTrackingSnapshot.status == "ok",
            RankTrackingSnapshot.ranking_url.isnot(None),
        )
        .order_by(RankTrackingSnapshot.checked_at.desc())
        .first()
    )
    return str(snapshot[0]).strip() if snapshot and snapshot[0] else None


def _effective_target_url(db: Session, row: RankTrackingKeyword) -> tuple[str | None, str]:
    """Resolve the page used for live matching without changing stored mappings."""
    explicit = (row.target_url or "").strip()
    if explicit:
        return explicit, "explicit"
    gsc_url = _latest_gsc_ranking_url(db, row)
    if gsc_url:
        return gsc_url, "gsc_ranking_url"
    return None, "none"


def _serialize_keyword(db: Session, row: RankTrackingKeyword, period: str | None = None) -> dict[str, Any]:
    snapshot_query = db.query(RankTrackingSnapshot).filter(
        RankTrackingSnapshot.keyword_id == row.id,
        RankTrackingSnapshot.status == "ok",
        RankTrackingSnapshot.source == "google_search_console",
    )
    if period:
        snapshot_query = snapshot_query.filter(RankTrackingSnapshot.period == period)
    latest = snapshot_query.order_by(RankTrackingSnapshot.checked_at.desc()).first()
    position = latest.position if latest else None
    # Only use an explicitly measured preceding GSC period. Legacy snapshots
    # have no period metadata, so movement remains null until the next refresh.
    previous_position = latest.comparison_position if latest else None
    change = round(previous_position - position, 2) if position is not None and previous_position is not None else None
    client = db.get(Client, row.client_id) if row.client_id else None
    effective_target_url, target_url_source = _effective_target_url(db, row)
    return {
        "id": row.id,
        "company_id": row.company_id,
        "client_id": row.client_id,
        "client_name": getattr(client, "business_name", None),
        "keyword": row.keyword,
        "target_url": row.target_url,
        "effective_target_url": effective_target_url,
        "target_url_source": target_url_source,
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
        "clicks": latest.clicks if latest else 0,
        "impressions": latest.impressions if latest else 0,
        "ctr": latest.ctr if latest else 0,
        "measurement_start_date": latest.measurement_start_date.isoformat() if latest and latest.measurement_start_date else None,
        "measurement_end_date": latest.measurement_end_date.isoformat() if latest and latest.measurement_end_date else None,
        "comparison_start_date": latest.comparison_start_date.isoformat() if latest and latest.comparison_start_date else None,
        "comparison_end_date": latest.comparison_end_date.isoformat() if latest and latest.comparison_end_date else None,
        "snapshot_period": latest.period if latest else None,
        "latest_gsc_date": latest.measurement_end_date.isoformat() if latest and latest.measurement_end_date else None,
        **_serialize_live_rank(db, row),
    }


def _serialize_live_rank(db: Session, row: RankTrackingKeyword) -> dict[str, Any]:
    """Expose the newest live SERP snapshot without replacing GSC metrics."""
    latest_live = (
        db.query(RankTrackingSnapshot)
        .filter(
            RankTrackingSnapshot.keyword_id == row.id,
            RankTrackingSnapshot.source == "live_serp",
        )
        .order_by(RankTrackingSnapshot.checked_at.desc())
        .first()
    )
    if latest_live is None:
        return {
            "live_position": None,
            "live_previous_position": None,
            "live_change": None,
            "live_ranking_url": None,
            "live_checked_at": None,
            "live_status": "not_checked",
            "live_error": None,
            "live_location": None,
            "live_device": None,
            "live_provider": None,
        }

    previous = (
        db.query(RankTrackingSnapshot)
        .filter(
            RankTrackingSnapshot.keyword_id == row.id,
            RankTrackingSnapshot.source == "live_serp",
            RankTrackingSnapshot.id != latest_live.id,
            RankTrackingSnapshot.status == "ok",
        )
        .order_by(RankTrackingSnapshot.checked_at.desc())
        .first()
    )
    previous_position = previous.position if previous else None
    current_position = latest_live.position
    change = (
        round(previous_position - current_position, 2)
        if current_position is not None and previous_position is not None
        else None
    )
    return {
        "live_position": current_position,
        "live_previous_position": previous_position,
        "live_change": change,
        "live_ranking_url": latest_live.ranking_url,
        "live_checked_at": latest_live.checked_at.isoformat() if latest_live.checked_at else None,
        "live_status": latest_live.status,
        "live_error": latest_live.error_message,
        "live_location": (row.location or os.getenv("LIVE_SERP_DEFAULT_LOCATION", "").strip() or None),
        "live_device": ((row.device or "desktop").strip().lower() if (row.device or "desktop").strip().lower() != "all" else "desktop"),
        "live_provider": LIVE_SERP_PROVIDER if latest_live.source == "live_serp" else None,
    }


def _live_target_domain(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        host = (parsed.hostname or "").strip().lower().removeprefix("www.")
        return host or None
    except Exception:
        return None



def _get_keyword(db: Session, company_id: str, keyword_id: str) -> RankTrackingKeyword:
    row = db.query(RankTrackingKeyword).filter(
        RankTrackingKeyword.id == keyword_id,
        RankTrackingKeyword.company_id == company_id,
        RankTrackingKeyword.deleted_at.is_(None),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Tracked keyword not found.")
    return row


def _period_days(period: str) -> int:
    return {"daily": 1, "weekly": 7, "monthly": 30, "yearly": 365}.get(period, 1)


def _period_windows(
    period: str = "daily",
    latest_end: date | None = None,
    compare: str = "previous_period",
    custom_compare_start: date | None = None,
    custom_compare_end: date | None = None,
) -> tuple[date, date, date, date]:
    """Build the selected GSC period and its comparison period."""
    days = _period_days(period)
    current_end = latest_end or (date.today() - timedelta(days=3))
    current_start = current_end - timedelta(days=days - 1)

    if compare == "custom":
        if not custom_compare_start or not custom_compare_end:
            raise HTTPException(status_code=422, detail="Custom comparison requires a start and end date.")
        if custom_compare_end < custom_compare_start:
            raise HTTPException(status_code=422, detail="Custom comparison end date must be on or after the start date.")
        previous_start = custom_compare_start
        previous_end = custom_compare_end
    else:
        shifts = {
            "previous_period": days,
            "previous_week": 7,
            "previous_month": 30,
            "previous_year": 365,
        }
        shift = shifts.get(compare, days)
        previous_end = current_end - timedelta(days=shift)
        previous_start = previous_end - timedelta(days=days - 1)
    return current_start, current_end, previous_start, previous_end


def _date_window(days: int = 90) -> tuple[str, str]:
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


async def _latest_gsc_date(
    connection: GoogleIntegration,
    db: Session,
    *,
    site_url: str,
    keyword: str,
    country: str = "global",
    device: str = "all",
) -> date | None:
    """Return the newest date for which GSC has data for this exact query."""
    base = {
        "startDate": (date.today() - timedelta(days=14)).isoformat(),
        "endDate": date.today().isoformat(),
        "dimensions": ["date"],
        "rowLimit": 30,
        "dataState": "all",
    }
    filters = [{"dimension": "query", "operator": "equals", "expression": keyword}]
    country_values = _normalize_country(country)
    device_value = _normalize_device(device)
    if country_values:
        filters.append({"dimension": "country", "operator": "equals", "expression": country_values[0]})
    if device_value:
        filters.append({"dimension": "device", "operator": "equals", "expression": device_value})
    try:
        rows = await _gsc_request(
            connection, db, site_url, {**base, "dimensionFilterGroups": [{"filters": filters}]}
        )
    except HTTPException:
        rows = []
    dates = []
    for row in rows:
        raw = str((row.get("keys") or [""])[0] or "")
        try:
            dates.append(date.fromisoformat(raw))
        except ValueError:
            pass
    return max(dates) if dates else None


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
        matching = [
            r for r in rows
            if str((r.get("keys") or [None, None])[1] or "").rstrip("/").casefold() == target_norm
        ]
        if not matching:
            return {
                "position": None,
                "ranking_url": None,
                "clicks": 0.0,
                "impressions": 0.0,
                "ctr": 0.0,
                "matched_rows": 0,
                "message": "The configured target URL had no Search Console data for this query in the selected period.",
            }
        rows = matching

    # GSC position is an average metric, not a live SERP rank. When the API
    # returns multiple page rows, use an impression-weighted position instead
    # of selecting the numerically smallest page position. Selecting min() was
    # the source of inflated Top 3/10/20 results in the previous implementation.
    total_impressions = sum(float(item.get("impressions", 0)) for item in rows)
    if total_impressions:
        weighted_position = sum(
            float(item.get("position", 0)) * float(item.get("impressions", 0))
            for item in rows
        ) / total_impressions
    else:
        weighted_position = sum(float(item.get("position", 0)) for item in rows) / len(rows)
    # If an exact target URL is configured, rows contains only that page.
    # Otherwise keep legacy data deterministic by preferring the page with
    # strongest query visibility instead of arbitrarily choosing the lowest
    # position from a secondary page.
    best = max(
        rows,
        key=lambda item: (
            float(item.get("impressions", 0)),
            float(item.get("clicks", 0)),
            -float(item.get("position", math.inf)),
        ),
    )
    total_clicks = sum(float(item.get("clicks", 0)) for item in rows)
    total_impressions = sum(float(item.get("impressions", 0)) for item in rows)
    return {
        "position": round(weighted_position, 2),
        "ranking_url": (best.get("keys") or [None, None])[1],
        "clicks": total_clicks,
        "impressions": total_impressions,
        "ctr": total_clicks / total_impressions if total_impressions else 0.0,
        "matched_rows": len(rows),
        "message": f"Matched {len(rows)} Search Console result row(s).",
    }


async def _refresh_keyword(
    db: Session,
    row: RankTrackingKeyword,
    company_id: str,
    period: str = "daily",
    compare: str = "previous_period",
    custom_compare_start: date | None = None,
    custom_compare_end: date | None = None,
) -> dict[str, Any]:
    connection = get_connection(db, company_id, "search_console")
    if connection is None:
        raise HTTPException(status_code=400, detail="Google Search Console is not connected. Connect it in Google Integration first.")

    site_url, available_sites = await _resolve_gsc_property(connection, db)
    latest_gsc_date = await _latest_gsc_date(
        connection, db, site_url=site_url, keyword=row.keyword, country=row.country, device=row.device
    )
    current_start, current_end, previous_start, previous_end = _period_windows(
        period, latest_gsc_date, compare, custom_compare_start, custom_compare_end
    )
    current_start_text, current_end_text = current_start.isoformat(), current_end.isoformat()
    previous_start_text, previous_end_text = previous_start.isoformat(), previous_end.isoformat()
    try:
        current_data = await _query_gsc_keyword(
            connection, db, site_url=site_url, keyword=row.keyword,
            start_date=current_start_text, end_date=current_end_text, country=row.country,
            device=row.device, target_url=row.target_url,
        )
        previous_data = await _query_gsc_keyword(
            connection, db, site_url=site_url, keyword=row.keyword,
            start_date=previous_start_text, end_date=previous_end_text, country=row.country,
            device=row.device, target_url=row.target_url,
        )
        snapshot = (
            db.query(RankTrackingSnapshot)
            .filter(
                RankTrackingSnapshot.keyword_id == row.id,
                RankTrackingSnapshot.measurement_start_date == current_start,
                RankTrackingSnapshot.measurement_end_date == current_end,
                RankTrackingSnapshot.period == period,
                RankTrackingSnapshot.comparison_start_date == previous_start,
                RankTrackingSnapshot.comparison_end_date == previous_end,
            )
            .order_by(RankTrackingSnapshot.checked_at.desc())
            .first()
        )
        if snapshot is None:
            snapshot = RankTrackingSnapshot(
                keyword_id=row.id,
                measurement_start_date=current_start,
                measurement_end_date=current_end,
                comparison_start_date=previous_start,
                comparison_end_date=previous_end,
            )
            db.add(snapshot)
        snapshot.checked_at = datetime.now(UTC)
        snapshot.position = current_data["position"]
        snapshot.ranking_url = current_data["ranking_url"]
        snapshot.clicks = current_data["clicks"]
        snapshot.impressions = current_data["impressions"]
        snapshot.ctr = current_data["ctr"]
        snapshot.comparison_position = previous_data["position"]
        snapshot.period = period
        snapshot.source = "google_search_console"
        snapshot.status = "ok"
        if current_data["position"] is None:
            snapshot.error_message = current_data["message"]
        elif previous_data["position"] is None:
            snapshot.error_message = f"Current period matched data, but comparison period has no Search Console position: {previous_data['message']}"
        else:
            snapshot.error_message = None
        db.commit()
        db.refresh(snapshot)
        result = _serialize_keyword(db, row)
        result["measurement_property"] = site_url
        result["available_properties"] = available_sites
        result["date_range"] = {"start": current_start_text, "end": current_end_text}
        result["comparison_date_range"] = {"start": previous_start_text, "end": previous_end_text}
        result["period"] = period
        result["compare"] = compare
        result["latest_gsc_date"] = latest_gsc_date.isoformat() if latest_gsc_date else None
        result["measurement_message"] = current_data["message"]
        result["comparison_message"] = previous_data["message"]
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
    """Return local Rank Tracker configuration without blocking on Google APIs."""
    company_id = _company_id(current_user)
    connection = get_connection(db, company_id, "search_console")
    connected = connection is not None
    selected = _property_from_connection(connection) if connection else None
    configured = is_configured()
    return {
        "google_search_console_connected": connected,
        "selected_property": selected,
        "measurement": "Google Search Console average position",
        "live_serp_configured": configured,
        "live_serp_provider": LIVE_SERP_PROVIDER,
        "live_serp_message": configuration_message() if not configured else "Live Google organic SERP checks are configured.",
    }


def _serialize_keywords_bulk(
    db: Session,
    rows: list[RankTrackingKeyword],
    period: str,
) -> list[dict[str, Any]]:
    """Serialize tracked keywords with a bounded number of DB queries."""
    if not rows:
        return []

    ids = [row.id for row in rows]

    clients = {}
    client_ids = {row.client_id for row in rows if row.client_id}
    if client_ids:
        clients = {
            client.id: client
            for client in db.query(Client).filter(Client.id.in_(client_ids)).all()
        }

    gsc_max = (
        db.query(
            RankTrackingSnapshot.keyword_id.label("keyword_id"),
            func.max(RankTrackingSnapshot.checked_at).label("checked_at"),
        )
        .filter(
            RankTrackingSnapshot.keyword_id.in_(ids),
            RankTrackingSnapshot.source == "google_search_console",
            RankTrackingSnapshot.status == "ok",
            RankTrackingSnapshot.period == period,
        )
        .group_by(RankTrackingSnapshot.keyword_id)
        .subquery()
    )
    gsc_rows = (
        db.query(RankTrackingSnapshot)
        .join(
            gsc_max,
            and_(
                RankTrackingSnapshot.keyword_id == gsc_max.c.keyword_id,
                RankTrackingSnapshot.checked_at == gsc_max.c.checked_at,
            ),
        )
        .all()
    )
    gsc_by_id = {item.keyword_id: item for item in gsc_rows}

    # Latest GSC landing page is also the fallback target for legacy keywords
    # whose explicit target_url is still NULL.
    gsc_target_by_id = {
        item.keyword_id: item.ranking_url
        for item in gsc_rows
        if item.ranking_url
    }

    live_rows = (
        db.query(RankTrackingSnapshot)
        .filter(
            RankTrackingSnapshot.keyword_id.in_(ids),
            RankTrackingSnapshot.source == "live_serp",
        )
        .order_by(
            RankTrackingSnapshot.keyword_id.asc(),
            RankTrackingSnapshot.checked_at.desc(),
        )
        .all()
    )
    live_by_id: dict[str, list[RankTrackingSnapshot]] = {}
    for item in live_rows:
        live_by_id.setdefault(item.keyword_id, []).append(item)

    output: list[dict[str, Any]] = []
    for row in rows:
        latest = gsc_by_id.get(row.id)
        current_position = latest.position if latest else None
        previous_position = latest.comparison_position if latest else None
        change = (
            round(previous_position - current_position, 2)
            if current_position is not None and previous_position is not None
            else None
        )

        effective_target_url = (row.target_url or "").strip() or gsc_target_by_id.get(row.id)
        target_source = "explicit" if (row.target_url or "").strip() else (
            "gsc_ranking_url" if effective_target_url else "none"
        )

        live_items = live_by_id.get(row.id, [])
        latest_live = live_items[0] if live_items else None
        previous_live = next(
            (item for item in live_items[1:] if item.status == "ok"),
            None,
        )
        live_position = latest_live.position if latest_live else None
        live_previous = previous_live.position if previous_live else None
        live_change = (
            round(live_previous - live_position, 2)
            if live_position is not None and live_previous is not None
            else None
        )

        client = clients.get(row.client_id) if row.client_id else None
        output.append({
            "id": row.id,
            "company_id": row.company_id,
            "client_id": row.client_id,
            "client_name": getattr(client, "business_name", None),
            "keyword": row.keyword,
            "target_url": row.target_url,
            "effective_target_url": effective_target_url,
            "target_url_source": target_source,
            "search_engine": row.search_engine,
            "country": row.country,
            "location": row.location,
            "language": row.language,
            "device": row.device,
            "frequency": row.frequency,
            "is_active": row.is_active,
            "current_position": current_position,
            "previous_position": previous_position,
            "change": change,
            "ranking_url": latest.ranking_url if latest else None,
            "last_checked_at": latest.checked_at.isoformat() if latest else None,
            "status": latest.status if latest else "not_checked",
            "last_error": latest.error_message if latest and latest.error_message else None,
            "clicks": latest.clicks if latest else 0,
            "impressions": latest.impressions if latest else 0,
            "ctr": latest.ctr if latest else 0,
            "measurement_start_date": latest.measurement_start_date.isoformat() if latest and latest.measurement_start_date else None,
            "measurement_end_date": latest.measurement_end_date.isoformat() if latest and latest.measurement_end_date else None,
            "comparison_start_date": latest.comparison_start_date.isoformat() if latest and latest.comparison_start_date else None,
            "comparison_end_date": latest.comparison_end_date.isoformat() if latest and latest.comparison_end_date else None,
            "snapshot_period": latest.period if latest else None,
            "latest_gsc_date": latest.measurement_end_date.isoformat() if latest and latest.measurement_end_date else None,
            "live_position": live_position,
            "live_previous_position": live_previous,
            "live_change": live_change,
            "live_ranking_url": latest_live.ranking_url if latest_live else None,
            "live_checked_at": latest_live.checked_at.isoformat() if latest_live and latest_live.checked_at else None,
            "live_status": latest_live.status if latest_live else "not_checked",
            "live_error": latest_live.error_message if latest_live else None,
            "live_location": row.location or os.getenv("LIVE_SERP_DEFAULT_LOCATION", "").strip() or None,
            "live_device": row.device or "desktop",
            "live_provider": LIVE_SERP_PROVIDER if latest_live else None,
        })
    return output


@router.get("/keywords")
def list_keywords(
    active_only: bool = Query(False),
    client_id: str | None = Query(None),
    period: str = Query("daily"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    if period not in {"daily", "weekly", "monthly", "yearly"}:
        raise HTTPException(status_code=422, detail="Invalid period.")
    company_id = _company_id(current_user)
    query = db.query(RankTrackingKeyword).filter(
        RankTrackingKeyword.company_id == company_id,
        RankTrackingKeyword.deleted_at.is_(None),
    )
    if active_only:
        query = query.filter(RankTrackingKeyword.is_active.is_(True))
    if client_id:
        query = query.filter(RankTrackingKeyword.client_id == client_id)
    rows = query.order_by(RankTrackingKeyword.created_at.desc()).all()
    _auto_assign_single_client(db, rows, company_id)
    return _serialize_keywords_bulk(db, rows, period)


@router.post("/keywords", status_code=status.HTTP_201_CREATED)
def create_keyword(payload: KeywordCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)
    if not payload.client_id:
        raise HTTPException(status_code=422, detail="Client mapping is required for a tracked keyword.")
    if not payload.target_url or not payload.target_url.strip():
        raise HTTPException(status_code=422, detail="An exact target URL is required for a tracked keyword.")
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
def overview(
    client_id: str | None = Query(None),
    period: str = Query("daily"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if period not in {"daily", "weekly", "monthly", "yearly"}:
        raise HTTPException(status_code=422, detail="Invalid period.")
    company_id = _company_id(current_user)
    query = db.query(RankTrackingKeyword).filter(
        RankTrackingKeyword.company_id == company_id,
        RankTrackingKeyword.deleted_at.is_(None),
        RankTrackingKeyword.is_active.is_(True),
    )
    if client_id:
        query = query.filter(RankTrackingKeyword.client_id == client_id)
    rows = query.all()
    _auto_assign_single_client(db, rows, company_id)
    items = _serialize_keywords_bulk(db, rows, period)
    positions = [float(item["current_position"]) for item in items if item["current_position"] is not None]
    changes = [float(item["change"]) for item in items if item["change"] is not None]
    return {
        "tracked_keywords": len(items), "top_3": sum(p <= 3 for p in positions),
        "top_10": sum(p <= 10 for p in positions), "top_20": sum(p <= 20 for p in positions),
        "improved": sum(c > 0 for c in changes), "declined": sum(c < 0 for c in changes),
        "not_ranking": sum(item["current_position"] is None for item in items),
        "average_position": round(sum(positions) / len(positions), 2) if positions else None,
    }

async def _bulk_gsc_rows(
    connection: GoogleIntegration,
    db: Session,
    *,
    site_url: str,
    start_date: date,
    end_date: date,
    country: str,
    device: str,
) -> list[dict[str, Any]]:
    """Fetch query/page GSC data for bulk rank synchronization."""

    base: dict[str, Any] = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["query", "page"],
        "rowLimit": 25000,
        "dataState": "all",
    }

    filters: list[dict[str, str]] = []

    country_values = _normalize_country(country)
    device_value = _normalize_device(device)

    if country_values:
        filters.append({
            "dimension": "country",
            "operator": "equals",
            "expression": country_values[0],
        })

    if device_value:
        filters.append({
            "dimension": "device",
            "operator": "equals",
            "expression": device_value,
        })

    if filters:
        base["dimensionFilterGroups"] = [{"filters": filters}]

    rows: list[dict[str, Any]] = []
    start_row = 0

    # Search Console supports a maximum rowLimit of 25,000.
    # Continue paging until the returned page is smaller than the limit.
    while True:
        page_rows = await _gsc_request(
            connection,
            db,
            site_url,
            {**base, "startRow": start_row},
        )

        rows.extend(page_rows)

        if len(page_rows) < 25000:
            break

        start_row += 25000

        # Prevent an unexpectedly huge property from keeping one
        # synchronization request alive indefinitely.
        if start_row >= 100000:
            break

    return rows


def _index_bulk_gsc_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Build one normalized-query index so bulk matching is O(1) per keyword."""
    index: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        normalized = " ".join(str((row.get("keys") or [""])[0] or "").casefold().split())
        if normalized:
            index.setdefault(normalized, []).append(row)
    return index


def _bulk_match_gsc_rows(
    rows: list[dict[str, Any]] | dict[str, list[dict[str, Any]]],
    *,
    keyword: str,
    target_url: str | None = None,
) -> dict[str, Any]:
    """Match one keyword from bulk GSC rows using a pre-built query index."""
    normalized_keyword = " ".join(keyword.casefold().split())
    if isinstance(rows, dict):
        matching = list(rows.get(normalized_keyword, []))
    else:
        matching = [
            row for row in rows
            if normalized_keyword
            == " ".join(str((row.get("keys") or [""])[0] or "").casefold().split())
        ]

    if target_url:
        target_norm = target_url.rstrip("/").casefold()
        matching = [
            row for row in matching
            if str((row.get("keys") or [None, None])[1] or "").rstrip("/").casefold() == target_norm
        ]
        if not matching:
            return {
                "position": None,
                "ranking_url": None,
                "clicks": 0.0,
                "impressions": 0.0,
                "ctr": 0.0,
                "matched_rows": 0,
                "message": "The configured target URL had no Search Console data for this query in the selected period.",
            }

    if not matching:
        return {
            "position": None,
            "ranking_url": None,
            "clicks": 0.0,
            "impressions": 0.0,
            "ctr": 0.0,
            "matched_rows": 0,
            "message": "No Search Console data found for this keyword in the selected period.",
        }

    total_clicks = sum(float(item.get("clicks", 0)) for item in matching)
    total_impressions = sum(float(item.get("impressions", 0)) for item in matching)
    if total_impressions:
        weighted_position = sum(
            float(item.get("position", 0)) * float(item.get("impressions", 0))
            for item in matching
        ) / total_impressions
    else:
        weighted_position = sum(float(item.get("position", 0)) for item in matching) / len(matching)

    best = min(matching, key=lambda item: float(item.get("position", math.inf)))
    return {
        "position": round(weighted_position, 2),
        "ranking_url": (best.get("keys") or [None, None])[1],
        "clicks": total_clicks,
        "impressions": total_impressions,
        "ctr": total_clicks / total_impressions if total_impressions else 0.0,
        "matched_rows": len(matching),
        "message": f"Matched {len(matching)} Search Console result row(s).",
    }


async def _refresh_keywords_bulk(
    db: Session,
    rows: list[RankTrackingKeyword],
    company_id: str,
    *,
    period: str,
    compare: str,
    custom_compare_start: date | None,
    custom_compare_end: date | None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Synchronize many keywords using batched GSC queries."""

    connection = get_connection(
        db,
        company_id,
        "search_console",
    )

    if connection is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Google Search Console is not connected. "
                "Connect it in Google Integration first."
            ),
        )

    site_url, available_sites = await _resolve_gsc_property(
        connection,
        db,
    )

    # Use one common GSC date for the bulk operation.
    # This avoids one date-discovery request per keyword.
    latest_date_base = date.today() - timedelta(days=3)

    current_start, current_end, previous_start, previous_end = (
        _period_windows(
            period,
            latest_date_base,
            compare,
            custom_compare_start,
            custom_compare_end,
        )
    )

    # Group keywords so GSC is queried once per country/device
    # combination rather than once per keyword.
    groups: dict[tuple[str, str], list[RankTrackingKeyword]] = {}

    for row in rows:
        key = (
            (row.country or "global").strip().lower(),
            (row.device or "all").strip().lower(),
        )
        groups.setdefault(key, []).append(row)

    current_rows_by_group: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = {}

    previous_rows_by_group: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = {}
    current_index_by_group: dict[
        tuple[str, str],
        dict[str, list[dict[str, Any]]],
    ] = {}
    previous_index_by_group: dict[
        tuple[str, str],
        dict[str, list[dict[str, Any]]],
    ] = {}

    errors: list[dict[str, str]] = []

    for group_key, group_rows in groups.items():
        country, device = group_key

        try:
            current_rows_by_group[group_key] = await _bulk_gsc_rows(
                connection,
                db,
                site_url=site_url,
                start_date=current_start,
                end_date=current_end,
                country=country,
                device=device,
            )

            previous_rows_by_group[group_key] = await _bulk_gsc_rows(
                connection,
                db,
                site_url=site_url,
                start_date=previous_start,
                end_date=previous_end,
                country=country,
                device=device,
            )

            current_index_by_group[group_key] = _index_bulk_gsc_rows(
                current_rows_by_group[group_key]
            )
            previous_index_by_group[group_key] = _index_bulk_gsc_rows(
                previous_rows_by_group[group_key]
            )

        except HTTPException as exc:
            message = str(exc.detail)

            for row in group_rows:
                errors.append({
                    "keyword_id": row.id,
                    "keyword": row.keyword,
                    "error": message,
                })

    results: list[dict[str, Any]] = []

    for row in rows:
        group_key = (
            (row.country or "global").strip().lower(),
            (row.device or "all").strip().lower(),
        )

        if group_key not in current_rows_by_group:
            continue

        try:
            current_data = _bulk_match_gsc_rows(
                current_index_by_group[group_key],
                keyword=row.keyword,
                target_url=row.target_url,
            )

            previous_data = _bulk_match_gsc_rows(
                previous_index_by_group.get(group_key, {}),
                keyword=row.keyword,
                target_url=row.target_url,
            )

            snapshot = (
                db.query(RankTrackingSnapshot)
                .filter(
                    RankTrackingSnapshot.keyword_id == row.id,
                    RankTrackingSnapshot.measurement_start_date == current_start,
                    RankTrackingSnapshot.measurement_end_date == current_end,
                    RankTrackingSnapshot.period == period,
                    RankTrackingSnapshot.comparison_start_date == previous_start,
                    RankTrackingSnapshot.comparison_end_date == previous_end,
                )
                .order_by(
                    RankTrackingSnapshot.checked_at.desc()
                )
                .first()
            )

            if snapshot is None:
                snapshot = RankTrackingSnapshot(
                    keyword_id=row.id,
                    measurement_start_date=current_start,
                    measurement_end_date=current_end,
                    comparison_start_date=previous_start,
                    comparison_end_date=previous_end,
                )
                db.add(snapshot)

            snapshot.checked_at = datetime.now(UTC)
            snapshot.position = current_data["position"]
            snapshot.ranking_url = current_data["ranking_url"]
            snapshot.clicks = current_data["clicks"]
            snapshot.impressions = current_data["impressions"]
            snapshot.ctr = current_data["ctr"]
            snapshot.comparison_position = previous_data["position"]
            snapshot.period = period
            snapshot.source = "google_search_console"
            snapshot.status = "ok"

            if current_data["position"] is None:
                snapshot.error_message = current_data["message"]
            elif previous_data["position"] is None:
                snapshot.error_message = (
                    "Current period matched data, but comparison "
                    "period has no Search Console position: "
                    f"{previous_data['message']}"
                )
            else:
                snapshot.error_message = None

            db.commit()
            db.refresh(snapshot)

            result = _serialize_keyword(
                db,
                row,
                period,
            )

            result["measurement_property"] = site_url
            result["available_properties"] = available_sites
            result["date_range"] = {
                "start": current_start.isoformat(),
                "end": current_end.isoformat(),
            }
            result["comparison_date_range"] = {
                "start": previous_start.isoformat(),
                "end": previous_end.isoformat(),
            }
            result["period"] = period
            result["compare"] = compare
            result["latest_gsc_date"] = (
                current_end.isoformat()
            )
            result["measurement_message"] = (
                current_data["message"]
            )
            result["comparison_message"] = (
                previous_data["message"]
            )

            results.append(result)

        except Exception as exc:
            db.rollback()

            errors.append({
                "keyword_id": row.id,
                "keyword": row.keyword,
                "error": str(exc)[:1000],
            })

    return results, errors


@router.post("/live-refresh")
async def live_refresh_keywords(
    payload: LiveRefreshRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Run live Google checks without holding a PostgreSQL connection during Playwright."""
    company_id = _company_id(current_user)
    if not is_configured():
        raise HTTPException(status_code=503, detail=configuration_message())

    query = db.query(RankTrackingKeyword).filter(
        RankTrackingKeyword.company_id == company_id,
        RankTrackingKeyword.deleted_at.is_(None),
        RankTrackingKeyword.is_active.is_(True),
        RankTrackingKeyword.search_engine == "google",
    )
    if payload.keyword_ids:
        query = query.filter(RankTrackingKeyword.id.in_(payload.keyword_ids))

    rows = query.order_by(RankTrackingKeyword.created_at.asc()).all()
    if not rows:
        return {"requested": 0, "updated": 0, "failed": 0, "items": [], "errors": []}

    _auto_assign_single_client(db, rows, company_id)

    default_location = (
        (payload.location or "").strip()
        or os.getenv("LIVE_SERP_DEFAULT_LOCATION", "").strip()
    )
    default_language = (payload.language or "").strip().lower()
    default_device = (payload.device or "").strip().lower()

    # IMPORTANT: resolve every DB-backed target mapping BEFORE Playwright starts.
    # The old implementation called _effective_target_url(db, row) inside each
    # async worker. A synchronous SQLAlchemy Session then held one PostgreSQL
    # connection while awaiting Playwright, so five concurrent workers could
    # exhaust a pool of only five connections and even block /api/users/me.
    gsc_connection = get_connection(db, company_id, "search_console")
    gsc_property = _property_from_connection(gsc_connection) if gsc_connection else None
    target_domain_fallback = _live_target_domain(gsc_property)

    jobs: list[dict[str, Any]] = []
    for row in rows:
        effective_target_url, target_source = _effective_target_url(db, row)
        target_domain = _live_target_domain(effective_target_url) or target_domain_fallback
        jobs.append({
            "id": row.id,
            "keyword": row.keyword,
            "location": (row.location or "").strip() or default_location,
            "language": default_language or (row.language or "en").strip().lower() or "en",
            "device": default_device or (row.device or "desktop").strip().lower(),
            "target_url": effective_target_url,
            "target_domain": target_domain,
            "target_source": target_source,
        })

    # Release the SQLAlchemy connection/transaction BEFORE any long-running
    # browser work. The request's Session can safely be reused afterwards.
    db.rollback()

    async def check_one(job: dict[str, Any]) -> tuple[dict[str, Any], Any, str | None]:
        location = job["location"]
        if not location:
            return job, None, "A city/location is required. Set the keyword location or provide location in the Live SERP check."
        if not job["target_url"] and not job["target_domain"]:
            return job, None, "A target URL is required for live rank matching when no GSC ranking page or GSC property is available."
        try:
            result = await check_google_organic_rank(
                keyword=job["keyword"],
                location=location,
                language=job["language"],
                device=job["device"],
                target_url=job["target_url"],
                target_domain=job["target_domain"],
                allow_domain_fallback=True,
            )
            result["target_url_source"] = job["target_source"]
            return job, (result, location, job["language"], job["device"]), None
        except LiveSERPError as exc:
            return job, None, str(exc)
        except Exception as exc:
            return job, None, str(exc)[:1000]

    # Process live Google jobs sequentially. This is intentional: one persistent
    # Google profile can carry a legitimate manual verification session forward
    # to subsequent keywords, while a burst of concurrent searches is much more
    # likely to trigger Google's automated-traffic controls.
    checked: list[tuple[dict[str, Any], Any, str | None]] = []
    inter_request_delay = max(0.0, float(os.getenv("LIVE_SERP_INTER_REQUEST_DELAY", "3")))
    for index, job in enumerate(jobs):
        if index:
            await asyncio.sleep(inter_request_delay)
        checked.append(await check_one(job))

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for job, payload_result, error in checked:
        row = db.get(RankTrackingKeyword, job["id"])
        if row is None:
            errors.append({
                "keyword_id": job["id"],
                "keyword": job["keyword"],
                "error": "Tracked keyword no longer exists.",
            })
            continue

        if error:
            db.add(RankTrackingSnapshot(
                keyword_id=row.id,
                checked_at=datetime.now(UTC),
                source="live_serp",
                status="error",
                error_message=error[:1000],
            ))
            db.commit()
            errors.append({"keyword_id": row.id, "keyword": row.keyword, "error": error})
            continue

        live_result, location, language, device = payload_result

        previous_live = (
            db.query(RankTrackingSnapshot)
            .filter(
                RankTrackingSnapshot.keyword_id == row.id,
                RankTrackingSnapshot.source == "live_serp",
                RankTrackingSnapshot.status == "ok",
            )
            .order_by(RankTrackingSnapshot.checked_at.desc())
            .first()
        )

        # A live check that did not identify the target page is NOT a valid
        # successful measurement. Keep the previous successful live snapshot
        # visible and record this attempt as an error instead of turning a
        # temporary parser/Google-layout mismatch into a false null ranking.
        if live_result.get("position") is None:
            error_message = (
                str(live_result.get("message") or "The live Google result could not be matched to the configured target page.")
            )[:1000]
            db.add(RankTrackingSnapshot(
                keyword_id=row.id,
                checked_at=datetime.now(UTC),
                source="live_serp",
                status="not_found",
                error_message=error_message,
            ))
            db.commit()
            errors.append({
                "keyword_id": row.id,
                "keyword": row.keyword,
                "error": error_message,
            })
            continue

        snapshot = RankTrackingSnapshot(
            keyword_id=row.id,
            checked_at=datetime.now(UTC),
            position=live_result.get("position"),
            ranking_url=live_result.get("ranking_url"),
            comparison_position=previous_live.position if previous_live else None,
            source="live_serp",
            status="ok",
            error_message=None,
        )
        db.add(snapshot)
        db.commit()

        results.append(_serialize_keyword(db, row))

    return {
        "requested": len(rows),
        "updated": len(results),
        "failed": len(errors),
        "items": results,
        "errors": errors,
    }

@router.post("/refresh")
async def refresh_keywords(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    company_id = _company_id(current_user)

    query = db.query(RankTrackingKeyword).filter(
        RankTrackingKeyword.company_id == company_id,
        RankTrackingKeyword.deleted_at.is_(None),
        RankTrackingKeyword.is_active.is_(True),
    )

    if payload.keyword_ids:
        query = query.filter(
            RankTrackingKeyword.id.in_(payload.keyword_ids)
        )

    rows = (
        query
        .order_by(RankTrackingKeyword.created_at.asc())
        .all()
    )

    results, errors = await _refresh_keywords_bulk(
        db,
        rows,
        company_id,
        period=payload.period,
        compare=payload.compare,
        custom_compare_start=payload.custom_compare_start,
        custom_compare_end=payload.custom_compare_end,
    )

    return {
        "requested": len(rows),
        "updated": len(results),
        "failed": len(errors),
        "items": results,
        "errors": errors,
    }
    return {"updated": len(results), "items": results, "errors": errors}


@router.post("/keywords/{keyword_id}/refresh")
async def refresh_one_keyword(
    keyword_id: str,
    period: str = Query("daily"),
    compare: str = Query("previous_period"),
    custom_compare_start: date | None = Query(None),
    custom_compare_end: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if period not in {"daily", "weekly", "monthly", "yearly"}:
        raise HTTPException(status_code=422, detail="Invalid period.")
    if compare not in {"previous_period", "previous_week", "previous_month", "previous_year", "custom"}:
        raise HTTPException(status_code=422, detail="Invalid comparison period.")
    company_id = _company_id(current_user)
    row = _get_keyword(db, company_id, keyword_id)
    return await _refresh_keyword(db, row, company_id, period, compare, custom_compare_start, custom_compare_end)


@router.get("/keywords/{keyword_id}/history")
def keyword_history(keyword_id: str, limit: int = Query(90, ge=1, le=365), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)
    row = _get_keyword(db, company_id, keyword_id)
    snapshots = db.query(RankTrackingSnapshot).filter(
        RankTrackingSnapshot.keyword_id == row.id,
        RankTrackingSnapshot.source == "google_search_console",
    ).order_by(RankTrackingSnapshot.checked_at.desc()).limit(limit).all()
    snapshots.reverse()
    return {"keyword": _serialize_keyword(db, row), "history": [{
        "id": item.id, "checked_at": item.checked_at.isoformat(), "position": item.position,
        "ranking_url": item.ranking_url, "clicks": item.clicks, "impressions": item.impressions,
        "ctr": item.ctr, "source": item.source, "status": item.status, "error_message": item.error_message,
        "measurement_start_date": item.measurement_start_date.isoformat() if item.measurement_start_date else None,
        "measurement_end_date": item.measurement_end_date.isoformat() if item.measurement_end_date else None,
        "comparison_start_date": item.comparison_start_date.isoformat() if item.comparison_start_date else None,
        "comparison_end_date": item.comparison_end_date.isoformat() if item.comparison_end_date else None,
    } for item in snapshots]}


@router.on_event("startup")
def ensure_rank_tracking_tables() -> None:
    RankTrackingKeyword.__table__.create(bind=engine, checkfirst=True)
    RankTrackingSnapshot.__table__.create(bind=engine, checkfirst=True)
    # Existing installations need idempotent column creation because CREATE TABLE
    # IF NOT EXISTS does not evolve an already-existing table.
    with engine.begin() as connection:
        for statement in (
            "ALTER TABLE rank_tracking_snapshots ADD COLUMN IF NOT EXISTS measurement_start_date DATE",
            "ALTER TABLE rank_tracking_snapshots ADD COLUMN IF NOT EXISTS measurement_end_date DATE",
            "ALTER TABLE rank_tracking_snapshots ADD COLUMN IF NOT EXISTS comparison_start_date DATE",
            "ALTER TABLE rank_tracking_snapshots ADD COLUMN IF NOT EXISTS comparison_end_date DATE",
            "ALTER TABLE rank_tracking_snapshots ADD COLUMN IF NOT EXISTS comparison_position DOUBLE PRECISION",
            "ALTER TABLE rank_tracking_snapshots ADD COLUMN IF NOT EXISTS period VARCHAR(20)",
            "CREATE INDEX IF NOT EXISTS ix_rank_tracking_snapshots_keyword_measurement_period ON rank_tracking_snapshots (keyword_id, measurement_start_date, measurement_end_date)",
            "CREATE INDEX IF NOT EXISTS ix_rank_tracking_snapshots_keyword_period ON rank_tracking_snapshots (keyword_id, period, checked_at)",
        ):
            connection.execute(text(statement))







