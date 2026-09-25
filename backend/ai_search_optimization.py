from __future__ import annotations

import asyncio
import difflib
import ipaddress
import json
import logging
import os
import re
import socket
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, HttpUrl

from api.deps.current_user import get_current_user
from config import settings
from database.database import get_db
from models.company import Company
from models.user import User
from services.secret_service import decrypt_secret

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/ai-search-optimization",
    tags=["AI Search Optimization"],
)

HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0, read=25.0, write=15.0, pool=10.0)
WP_TIMEOUT = httpx.Timeout(45.0, connect=15.0, read=35.0, write=15.0, pool=10.0)
USER_AGENT = "BoostRankers-AISearchOptimizer/1.0"
MAX_CONTENT_CHARS = 30000
MIN_INTERNAL_LINKS = 3
MAX_INTERNAL_LINKS = 5
GENERIC_ANCHORS = {"click here", "read more", "learn more", "here", "more", "this article"}
# Only remove linguistic stopwords. SEO/topic terms such as "service",
# "cleaning", "commercial", "company", "local", and location names are kept
# because they can be the only evidence connecting a source article to a
# legitimate service or location page.
LINK_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "from", "by",
    "how", "what", "why", "when", "where", "who", "which", "your", "our", "this", "that",
    "these", "those", "is", "are", "was", "were", "be", "been", "being",
    "as", "at", "it", "its", "into", "about", "over", "under", "than", "then",
    "can", "could", "should", "would", "will", "may", "might", "do", "does", "did",
    "you", "we", "they", "he", "she", "them", "their", "there", "here",
}


class AnalyzeRequest(BaseModel):
    url: HttpUrl
    focus_keyword: str = Field(default="", max_length=500)
    used_focus_keywords: list[str] = Field(default_factory=list, max_length=500)
    site_content_inventory: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)


class RewriteRequest(BaseModel):
    url: HttpUrl
    focus_keyword: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=3, max_length=500)
    content_html: str = Field(min_length=100, max_length=120000)
    meta_title: str = Field(default="", max_length=500)
    meta_description: str = Field(default="", max_length=1000)
    analysis: dict[str, Any] = Field(default_factory=dict)
    used_focus_keywords: list[str] = Field(default_factory=list, max_length=500)
    internal_link_candidates: list[dict[str, Any]] = Field(default_factory=list, max_length=1000)
    site_content_inventory: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)


class FocusKeywordSuggestionRequest(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    content: str = Field(default="", max_length=120000)
    current_focus_keyword: str = Field(default="", max_length=500)
    used_focus_keywords: list[str] = Field(default_factory=list, max_length=5000)


class WordPressCredentialsRequest(BaseModel):
    wordpress_site: HttpUrl
    wordpress_username: str = Field(min_length=1, max_length=255)
    wordpress_application_password: str = Field(min_length=1, max_length=255)


class WordPressApplyRequest(WordPressCredentialsRequest):
    post_id: int = Field(ge=1)
    title: str = Field(min_length=3, max_length=500)
    content_html: str = Field(min_length=100, max_length=120000)
    meta_title: str = Field(min_length=1, max_length=500)
    meta_description: str = Field(min_length=1, max_length=1000)
    focus_keyphrase: str = Field(min_length=1, max_length=500)
    status: str = Field(default="draft", pattern="^(draft|publish)$")


def _require_company(user: User) -> str:
    company_id = getattr(user, "company_id", None)
    if not company_id:
        raise HTTPException(status_code=403, detail="Your account is not attached to a company.")
    return str(company_id)


def _clean_url(value: str) -> str:
    parsed = urlparse(str(value).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Enter a valid HTTP/HTTPS URL.")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}{('?' + parsed.query) if parsed.query else ''}"


async def _wordpress_request(
    client: httpx.AsyncClient,
    site: str,
    route: str,
    *,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    auth: tuple[str, str] | None = None,
) -> httpx.Response:
    """Call WordPress REST API with a compatibility fallback.

    Some WordPress installations return 404 for /wp-json/... when REST
    pretty-permalink routing is unavailable or rewritten by the server.
    WordPress also supports the same REST routes through ?rest_route=... .
    Try the normal endpoint first, then the query-string form only on 404.
    """
    clean_route = "/" + str(route or "").lstrip("/")
    primary_url = f"{site}/wp-json{clean_route}"
    request_kwargs: dict[str, Any] = {"params": params or {}, "auth": auth}
    if json_body is not None:
        request_kwargs["json"] = json_body

    response = await client.request(method.upper(), primary_url, **request_kwargs)
    if response.status_code != 404:
        return response

    fallback_params = dict(params or {})
    fallback_params["rest_route"] = clean_route
    fallback_url = f"{site}/"
    return await client.request(
        method.upper(),
        fallback_url,
        params=fallback_params,
        auth=auth,
        **({"json": json_body} if json_body is not None else {}),
    )


def _reject_private_target(url: str) -> None:
    """Prevent the public-page analyzer from becoming an SSRF primitive."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().lower()
    if host in {"localhost", "localhost.localdomain"} or not host:
        raise HTTPException(status_code=400, detail="The analyzer accepts public website URLs only.")
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="The website hostname could not be resolved.") from exc
    for raw in addresses:
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise HTTPException(status_code=400, detail="The analyzer accepts public website URLs only.")


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    return re.sub(r"\s+", " ", unescape(soup.get_text(" ", strip=True))).strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def _keyword_count(text: str, keyword: str) -> int:
    if not keyword.strip():
        return 0
    return len(re.findall(re.escape(keyword.strip()), text or "", flags=re.IGNORECASE))


def _safe_excerpt(text: str, max_chars: int = 7000) -> str:
    return re.sub(r"\s+", " ", text or "").strip()[:max_chars]


def _normalize_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (value or "").lower())).strip()


_FOCUS_KEY_FIELDS = {
    "focus_keyword",
    "focus_keyphrase",
    "focuskeyword",
    "focuskeyphrase",
    "focuskw",
    "_yoast_wpseo_focuskw",
    "yoast_wpseo_focuskw",
    "rank_math_focus_keyword",
    "aioseo_keywords",
    "keyphrase",
}


def _has_explicit_focus_keyword_field(payload: Any) -> bool:
    """Return True when the payload explicitly exposes a focus-keyphrase field.

    An empty focus keyphrase is a valid Yoast state, but a response that simply
    omits the field is not evidence that the post has no focus keyphrase.
    """
    if isinstance(payload, dict):
        for key in payload:
            normalized_key = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
            if normalized_key in {
                "focus_keyword", "focus_keyphrase", "focuskeyword", "focuskeyphrase",
                "focuskw", "yoast_wpseo_focuskw", "_yoast_wpseo_focuskw",
                "rank_math_focus_keyword", "aioseo_keywords", "keyphrase",
            }:
                return True
            if ("focus" in normalized_key and ("keyword" in normalized_key or "keyphrase" in normalized_key or "kw" in normalized_key)) or ("target" in normalized_key and "kw" in normalized_key):
                return True
        return any(_has_explicit_focus_keyword_field(v) for v in payload.values() if isinstance(v, (dict, list)))
    if isinstance(payload, list):
        return any(_has_explicit_focus_keyword_field(v) for v in payload)
    return False


def _extract_focus_keyword(payload: Any) -> str:
    """Extract the stored primary focus keyword from common SEO plugin/meta shapes.

    WordPress exposes SEO metadata differently depending on the active SEO
    plugin and whether the plugin registers its meta keys with REST.  Do not
    rely on one exact key: recognize explicit focus-keyword fields and common
    plugin naming patterns, while avoiding generic fields such as arbitrary
    ``keywords`` values.
    """
    if isinstance(payload, dict):
        # Prefer explicit known fields first.
        for key, value in payload.items():
            normalized_key = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
            if normalized_key in _FOCUS_KEY_FIELDS:
                if isinstance(value, str) and value.strip():
                    return " ".join(value.split())
                if isinstance(value, list):
                    for entry in value:
                        if isinstance(entry, str) and entry.strip():
                            return " ".join(entry.split())

        # Then support additional SEO plugins/custom bridges whose field name
        # explicitly identifies a focus keyword/keyphrase.  This covers keys
        # such as _seopress_analysis_target_kw without treating generic
        # metadata like "keywords" as a focus keyword.
        for key, value in payload.items():
            normalized_key = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
            is_focus_field = (
                ("focus" in normalized_key and ("keyword" in normalized_key or "keyphrase" in normalized_key or "kw" in normalized_key))
                or ("target" in normalized_key and "kw" in normalized_key)
                or normalized_key in {"seopress_analysis_target_kw", "seopress_target_kw"}
            )
            if not is_focus_field:
                continue
            if isinstance(value, str) and value.strip():
                return " ".join(value.split())
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, str) and entry.strip():
                        return " ".join(entry.split())

        for nested_key in ("meta", "seo", "data", "result", "yoast", "rank_math", "aioseo", "seopress"):
            nested = payload.get(nested_key)
            if isinstance(nested, (dict, list)):
                found = _extract_focus_keyword(nested)
                if found:
                    return found
        for value in payload.values():
            if isinstance(value, (dict, list)):
                found = _extract_focus_keyword(value)
                if found:
                    return found
    elif isinstance(payload, list):
        for value in payload:
            found = _extract_focus_keyword(value)
            if found:
                return found
    return ""


def _extract_seo_metadata(payload: Any) -> dict[str, str]:
    """Extract explicit SEO title/description fields from common WP SEO bridges."""
    result = {"meta_title": "", "meta_description": ""}
    title_keys = {
        "seo_title", "meta_title", "seo_title_tag", "_yoast_wpseo_title",
        "yoast_wpseo_title", "rank_math_title", "aioseo_title", "seopress_titles_title",
    }
    description_keys = {
        "meta_description", "seo_description", "_yoast_wpseo_metadesc",
        "yoast_wpseo_metadesc", "rank_math_description", "aioseo_description",
        "seopress_titles_desc",
    }

    def walk(value: Any) -> None:
        if result["meta_title"] and result["meta_description"]:
            return
        if isinstance(value, dict):
            for key, raw in value.items():
                normalized_key = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
                if isinstance(raw, str) and raw.strip():
                    if normalized_key in title_keys and not result["meta_title"]:
                        result["meta_title"] = " ".join(raw.split())
                    elif normalized_key in description_keys and not result["meta_description"]:
                        result["meta_description"] = " ".join(raw.split())
                if isinstance(raw, (dict, list)):
                    walk(raw)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return result


def _intent_profile(title: str, content: str, focus_keyword: str = "") -> str:
    """Classify page intent conservatively for topic-map guidance, not ranking claims."""
    text = _normalize_phrase(" ".join([title, focus_keyword, content[:10000]]))
    commercial = {
        "hire", "hiring", "book", "booking", "quote", "quotes", "pricing", "price", "cost",
        "service", "services", "company", "cleaner", "cleaners", "provider", "providers",
        "commercial", "professional", "request", "appointment", "near me",
    }
    informational = {
        "how", "what", "why", "when", "where", "guide", "guides", "tips", "checklist",
        "explained", "steps", "ideas", "mistakes", "benefits", "difference", "compare",
        "comparison", "faq", "questions", "maintenance", "advice", "things", "included",
    }
    tokens = set(text.split())
    c = len(tokens & commercial)
    i = len(tokens & informational)
    if i >= c + 2:
        return "informational"
    if c >= i + 2:
        return "commercial"
    return "mixed"


def _inventory_for_source(inventory: list[dict[str, Any]], source_url: str) -> list[dict[str, str]]:
    source_key = _canonical_url(source_url)
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in inventory[:5000]:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        key = _canonical_url(url, source_url)
        if key == source_key or key in seen:
            continue
        seen.add(key)
        result.append({
            "id": str(item.get("id") or ""),
            "type": str(item.get("type") or ""),
            "status": str(item.get("status") or ""),
            "title": str(item.get("title") or "").strip(),
            "url": url,
            "focus_keyword": str(item.get("focus_keyword") or "").strip(),
            "meta_title": str(item.get("meta_title") or "").strip(),
            "meta_description": str(item.get("meta_description") or "").strip(),
        })
    return result


def _metadata_similarity(left: str, right: str) -> float:
    a = _normalize_phrase(left)
    b = _normalize_phrase(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    a_tokens, b_tokens = set(a.split()), set(b.split())
    jaccard = len(a_tokens & b_tokens) / max(1, len(a_tokens | b_tokens))
    sequence = difflib.SequenceMatcher(None, a, b).ratio()
    return max(jaccard, sequence)


def _metadata_collision(value: str, inventory: list[dict[str, str]], field: str, threshold: float = 0.90) -> dict[str, Any] | None:
    normalized = _normalize_phrase(value)
    if not normalized:
        return None
    for item in inventory:
        existing = str(item.get(field) or "").strip()
        if not existing:
            continue
        similarity = _metadata_similarity(value, existing)
        if normalized == _normalize_phrase(existing) or similarity >= threshold:
            return {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "field": field,
                "existing": existing,
                "similarity": round(similarity, 3),
            }
    return None


def _topic_intent_collisions(source_title: str, source_focus: str, source_content: str, inventory: list[dict[str, str]]) -> list[dict[str, Any]]:
    source_intent = _intent_profile(source_title, source_content)
    source_terms = _link_terms(" ".join([source_title, source_focus, source_content[:6000]]))
    collisions: list[dict[str, Any]] = []
    for item in inventory:
        existing_title = str(item.get("title") or "")
        existing_focus = str(item.get("focus_keyword") or "")
        if not existing_title and not existing_focus:
            continue
        existing_intent = _intent_profile(existing_title, "", existing_focus)
        existing_terms = _link_terms(" ".join([existing_title, existing_focus]))
        overlap = len(source_terms & existing_terms) / max(1, len(source_terms | existing_terms))
        if source_intent == existing_intent and overlap >= 0.55:
            collisions.append({
                "title": existing_title,
                "url": item.get("url", ""),
                "focus_keyword": existing_focus,
                "intent": existing_intent,
                "topic_overlap": round(overlap, 3),
            })
    return sorted(collisions, key=lambda x: -x["topic_overlap"])[:5]


def _fallback_distinct_meta_title(title: str, focus_keyword: str, inventory: list[dict[str, str]], field: str = "meta_title") -> str:
    base = re.sub(r"\s+", " ", title).strip()
    variants = [
        base,
        f"{base} | Practical Guide",
        f"{base} | Perth Guide",
        f"{base} | What to Know",
        f"{base} | Expert Tips",
    ]
    for candidate in variants:
        if not _metadata_collision(candidate, inventory, field, 0.96):
            return candidate[:500]
    return (base + " | Guide")[:500]


def _fallback_meta_description(title: str, content: str, focus_keyword: str, inventory: list[dict[str, str]]) -> str:
    body = _strip_html(content)
    topic = focus_keyword.strip() or title.strip()
    candidates = [
        f"Learn what to consider about {topic}, including practical steps, key questions, and useful guidance before choosing the right approach.",
        f"Explore practical guidance on {topic}, with key considerations, useful steps, and questions to help you make an informed decision.",
        _safe_excerpt(body, 155),
    ]
    for candidate in candidates:
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if candidate and not _metadata_collision(candidate, inventory, "meta_description", 0.96):
            return candidate[:1000]
    return candidates[0][:1000]


def _validate_rewrite_seo(rewrite: dict[str, Any], inventory: list[dict[str, str]], source_title: str, source_content: str) -> dict[str, Any]:
    title = str(rewrite.get("title") or "").strip()
    meta_title = str(rewrite.get("meta_title") or "").strip()
    meta_description = str(rewrite.get("meta_description") or "").strip()
    focus = str(rewrite.get("focus_keyword") or "").strip()
    checks: dict[str, Any] = {"title_collision": None, "meta_title_collision": None, "meta_description_collision": None, "title_meta_title_same": False, "description_repeats_title": False, "intent_collisions": []}
    checks["title_collision"] = _metadata_collision(title, inventory, "title", 0.88)
    checks["meta_title_collision"] = _metadata_collision(meta_title, inventory, "meta_title", 0.90)
    checks["meta_description_collision"] = _metadata_collision(meta_description, inventory, "meta_description", 0.92)
    checks["title_meta_title_same"] = bool(title and meta_title and _normalize_phrase(title) == _normalize_phrase(meta_title))
    checks["description_repeats_title"] = bool(meta_description and title and _metadata_similarity(meta_description, title) >= 0.72)
    checks["intent_collisions"] = _topic_intent_collisions(title or source_title, focus, source_content, inventory)
    checks["needs_repair"] = any([
        checks["title_collision"], checks["meta_title_collision"], checks["meta_description_collision"],
        checks["title_meta_title_same"], checks["description_repeats_title"],
    ])
    return checks


def _focus_candidates(title: str, content: str, used: set[str]) -> list[str]:
    """Build deterministic title/content-derived keyword candidates without inventing topics."""
    stop = {
        "the", "a", "an", "and", "or", "for", "to", "in", "on", "with", "from",
        "how", "what", "why", "when", "where", "who", "which", "your", "our", "this", "that",
        "guide", "best", "ultimate", "complete", "tips", "checklist",
    }
    words = re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)?", title.lower())
    meaningful = [w for w in words if len(w) > 2 and w not in stop]
    content_norm = _normalize_phrase(content)
    candidates: list[tuple[float, str]] = []
    for n in (4, 3):
        for i in range(max(0, len(meaningful) - n + 1)):
            phrase = " ".join(meaningful[i:i+n])
            norm = _normalize_phrase(phrase)
            if not norm or _keyword_conflicts(norm, used) or len(norm) < 5:
                continue
            count = content_norm.count(norm)
            # Prefer longer, title-aligned phrases while still using body frequency
            # as supporting evidence. This keeps suggestions tightly related to the
            # current post instead of selecting a generic two-word fragment.
            score = (count * 5) + (n * 4) + (5 if i == 0 else 0)
            candidates.append((score, phrase))
    candidates.sort(key=lambda item: (-item[0], len(item[1])))
    return [phrase for _, phrase in candidates]


_KEYWORD_COMPARISON_STOPWORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on",
    "or", "the", "to", "with", "without", "your", "our", "this", "that",
}

_FOCUS_SUGGESTION_GENERIC = {
    "professional", "quality", "reliable", "trusted", "affordable", "best", "complete",
    "help", "helps", "provide", "provides", "service", "services", "company", "companies",
    "guide", "guides", "tips", "ultimate", "local",
}


def _normalize_keyword_token(token: str) -> str:
    """Normalize simple English singular/plural variants for keyword ownership."""
    token = token.strip().lower()
    if token.endswith("ies") and len(token) > 4:
        return f"{token[:-3]}y"
    if token.endswith("s") and len(token) > 4 and not token.endswith("ss"):
        return token[:-1]
    return token


def _keyword_tokens(value: str) -> set[str]:
    return {
        _normalize_keyword_token(token)
        for token in _normalize_phrase(value).split()
        if token and token not in _KEYWORD_COMPARISON_STOPWORDS
    }


def _keyword_conflicts(candidate: str, used_keywords: set[str] | list[str]) -> bool:
    """Return True only when the exact focus-keyword phrase is already assigned.

    Google search-result occurrences and partial phrase overlap are not ownership
    conflicts. ``end of`` can therefore coexist with ``end of lease cleaning Perth``.
    Formatting differences such as punctuation/case/whitespace are normalized.
    """
    candidate_norm = _normalize_phrase(candidate)
    if not candidate_norm:
        return False
    return any(
        candidate_norm == _normalize_phrase(str(used))
        for used in used_keywords
        if _normalize_phrase(str(used))
    )


def _dedupe_keywords(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = re.sub(r"\s+", " ", str(value or "")).strip()
        norm = _normalize_phrase(clean)
        if clean and norm and norm not in seen:
            seen.add(norm)
            result.append(clean)
    return result

def _focus_keyword_fits_intent(candidate: str, title: str, content: str) -> bool:
    """Keep informational articles from being assigned an overtly transactional service phrase."""
    page_intent = _intent_profile(title, content)
    candidate_tokens = set(_normalize_phrase(candidate).split())
    transactional = {
        "hire", "hiring", "book", "booking", "quote", "quotes", "pricing", "price", "cost",
        "service", "services", "company", "provider", "providers", "appointment", "request",
        "near",
    }
    if page_intent == "informational" and len(candidate_tokens & transactional) >= 1:
        return False
    return True


def _choose_focus_keyword(title: str, content: str, requested: str, used_keywords: list[str]) -> tuple[str, bool]:
    used = {_normalize_phrase(x) for x in used_keywords if _normalize_phrase(x)}
    requested = re.sub(r"\s+", " ", requested or "").strip()
    requested_conflict = bool(requested and _keyword_conflicts(requested, used))
    if requested and not requested_conflict and _focus_keyword_fits_intent(requested, title, content):
        return requested, False

    for candidate in _focus_candidates(title, content, used):
        if not _keyword_conflicts(candidate, used) and _focus_keyword_fits_intent(candidate, title, content):
            return candidate, bool(requested)

    # If title-derived phrases are exhausted, derive candidates from the body
    # and rank them by topical overlap with the title. Avoid location-only or
    # generic fragments so the replacement remains useful for the same service.
    title_terms = {
        token for token in _keyword_tokens(title)
        if token not in {"perth", "wa", "australia"}
    }
    content_words = [
        word for word in re.findall(r"[A-Za-z0-9]+", _normalize_phrase(content))
        if len(word) >= 4 and word not in _KEYWORD_COMPARISON_STOPWORDS
    ]
    scored_body_candidates: list[tuple[float, str]] = []
    content_norm = _normalize_phrase(content)
    for n in (4, 3, 2):
        for i in range(max(0, len(content_words) - n + 1)):
            candidate = " ".join(content_words[i:i + n])
            candidate_norm = _normalize_phrase(candidate)
            if len(candidate_norm) < 5 or _keyword_conflicts(candidate, used) or not _focus_keyword_fits_intent(candidate, title, content):
                continue
            candidate_terms = _keyword_tokens(candidate)
            overlap = len(title_terms & candidate_terms)
            if overlap == 0:
                continue
            frequency = content_norm.count(candidate_norm)
            generic_count = len(candidate_terms & _FOCUS_SUGGESTION_GENERIC)
            score = (overlap * 20) + (n * 6) + min(frequency, 5) * 10 - (generic_count * 12)
            scored_body_candidates.append((score, candidate))
    scored_body_candidates.sort(key=lambda item: (-item[0], -len(item[1])))
    if scored_body_candidates:
        return scored_body_candidates[0][1], bool(requested)

    # Keep the result deterministic. This branch is only reached when there is
    # no unique phrase available in the supplied title/content evidence.
    base = " ".join(re.findall(r"[A-Za-z0-9]+", title)[:4]).strip() or "primary topic"
    candidate = base
    suffix = 2
    while _keyword_conflicts(candidate, used):
        candidate = f"{base} {suffix}"
        suffix += 1
    return candidate, bool(requested)


def _canonical_url(value: str, base: str | None = None) -> str:
    absolute = urljoin(base or "", str(value or "").strip())
    parsed = urlparse(absolute)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/') or '/'}"


def _sanitize_internal_links(
    html: str,
    source_url: str,
    candidates: list[dict[str, str]],
) -> tuple[str, int, list[str]]:
    """Keep only verified candidate links, remove self-links/duplicates, and cap at five."""
    if not html or not candidates:
        return html, 0, []

    source_key = _canonical_url(source_url)
    allowed: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        target = str(candidate.get("url") or "").strip()
        title = str(candidate.get("title") or "").strip()
        if not target or not title:
            continue
        key = _canonical_url(target, source_url)
        if key != source_key:
            allowed[key] = {
                "url": urljoin(source_url, target),
                "title": title,
                "focus_keyword": str(candidate.get("focus_keyword") or "").strip(),
            }

    soup = BeautifulSoup(html, "html.parser")
    applied = 0
    targets: list[str] = []
    used_target_keys: set[str] = set()

    for anchor in list(soup.find_all("a", href=True)):
        href = str(anchor.get("href") or "").strip()
        key = _canonical_url(href, source_url)
        target = allowed.get(key)
        anchor_text = _strip_html(anchor.get_text(" ", strip=True))
        parsed_href = urlparse(urljoin(source_url, href))
        source_host = urlparse(source_url).netloc.lower().lstrip("www.")
        href_host = parsed_href.netloc.lower().lstrip("www.")

        # Preserve external links.
        if href_host and href_host != source_host:
            continue

        # Only retain links to verified candidates. The rewrite is generated
        # from source text, so unsupported same-site links are not trustworthy.
        if not target or not anchor_text or _normalize_phrase(anchor_text) in GENERIC_ANCHORS:
            anchor.unwrap()
            continue

        # Prevent multiple links to the same target and cap the final count.
        if key in used_target_keys or applied >= MAX_INTERNAL_LINKS:
            anchor.unwrap()
            continue

        anchor["href"] = target["url"]
        applied += 1
        used_target_keys.add(key)
        targets.append(target["title"])

    return str(soup), applied, targets


def _candidate_anchor_phrases(candidate: dict[str, str]) -> list[str]:
    """Generate natural target phrases from title/focus-keyword evidence."""
    phrases: list[str] = []
    for raw in (
        str(candidate.get("focus_keyword") or ""),
        str(candidate.get("title") or ""),
    ):
        clean = _strip_html(raw)
        if not clean:
            continue
        words = [w for w in re.findall(r"[A-Za-z0-9]+", clean) if len(w) > 2]
        for count in (5, 4, 3, 2):
            if len(words) >= count:
                phrase = " ".join(words[:count]).strip()
                if phrase and _normalize_phrase(phrase) not in GENERIC_ANCHORS:
                    phrases.append(phrase)
    # Preserve order while removing duplicate phrases.
    return list(dict.fromkeys(phrases))


def _insert_contextual_links(
    html: str,
    source_url: str,
    candidates: list[dict[str, str]],
    already_linked: int,
) -> tuple[str, int, list[str]]:
    """
    Add missing links when target wording naturally exists in the article.
    This is intentionally conservative; a separate fallback handles the
    minimum count using a compact related-resources block.
    """
    if already_linked >= MAX_INTERNAL_LINKS or not candidates:
        return html, 0, []

    soup = BeautifulSoup(html, "html.parser")
    source_key = _canonical_url(source_url)
    added = 0
    targets: list[str] = []
    used_targets: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        used_targets.add(_canonical_url(str(anchor.get("href") or ""), source_url))

    paragraphs = [
        p
        for p in soup.find_all(["p", "li"])
        if p.find_parent(
            ["a", "h1", "h2", "h3", "h4", "h5", "h6", "code", "pre", "script", "style"]
        )
        is None
    ]

    for candidate in candidates:
        if already_linked + added >= MAX_INTERNAL_LINKS:
            break

        url = str(candidate.get("url") or "").strip()
        title = str(candidate.get("title") or "").strip()
        if not url or not title:
            continue

        target_key = _canonical_url(url, source_url)
        if target_key == source_key or target_key in used_targets:
            continue

        phrases = _candidate_anchor_phrases(candidate)
        found = False

        for para in paragraphs:
            text = para.get_text(" ", strip=True)
            phrase = next(
                (
                    x
                    for x in phrases
                    if x and re.search(r"\b" + re.escape(x) + r"\b", text, re.I)
                ),
                None,
            )
            if not phrase:
                continue

            for node in list(para.find_all(string=re.compile(re.escape(phrase), re.I))):
                parent = node.parent
                if parent and parent.name in {"a", "strong", "em"}:
                    continue
                match = re.search(re.escape(phrase), str(node), re.I)
                if not match:
                    continue

                before = str(node)[: match.start()]
                matched = str(node)[match.start() : match.end()]
                after = str(node)[match.end() :]
                link = soup.new_tag("a", href=urljoin(source_url, url))
                link.string = matched

                replacement = []
                if before:
                    replacement.append(BeautifulSoup(before, "html.parser"))
                replacement.append(link)
                if after:
                    replacement.append(BeautifulSoup(after, "html.parser"))
                node.replace_with(*replacement)

                added += 1
                used_targets.add(target_key)
                targets.append(title)
                found = True
                break

            if found:
                break

    return str(soup), added, targets


def _append_minimum_internal_links(
    html: str,
    source_url: str,
    candidates: list[dict[str, str]],
    already_linked: int,
) -> tuple[str, int, list[str]]:
    """
    Guarantee the requested minimum of three verified links when three or more
    suitable targets exist. The fallback is a compact related-resources block,
    never invented URLs and never a self-link.
    """
    if already_linked >= MIN_INTERNAL_LINKS or not candidates:
        return html, 0, []

    soup = BeautifulSoup(html, "html.parser")
    source_key = _canonical_url(source_url)
    existing_keys = {
        _canonical_url(str(a.get("href") or ""), source_url)
        for a in soup.find_all("a", href=True)
    }

    selected: list[dict[str, str]] = []
    for candidate in candidates:
        target = str(candidate.get("url") or "").strip()
        title = str(candidate.get("title") or "").strip()
        if not target or not title:
            continue
        target_key = _canonical_url(target, source_url)
        if target_key == source_key or target_key in existing_keys:
            continue
        selected.append(candidate)
        if already_linked + len(selected) >= MIN_INTERNAL_LINKS:
            break

    if not selected:
        return str(soup), 0, []

    heading = soup.new_tag("h3")
    heading.string = "Related resources"
    ul = soup.new_tag("ul")

    for candidate in selected:
        target = str(candidate.get("url") or "").strip()
        title = str(candidate.get("title") or "").strip()
        if not target or not title:
            continue
        li = soup.new_tag("li")
        anchor = soup.new_tag("a", href=urljoin(source_url, target))
        anchor.string = title
        li.append(anchor)
        ul.append(li)

    if not ul.find("a"):
        return str(soup), 0, []

    # Put the fallback block at the end of the article body without touching
    # headings or existing content structure.
    container = soup.find("article") or soup.find("main") or soup.body or soup
    container.append(heading)
    container.append(ul)

    count = len(selected)
    return str(soup), count, [str(item.get("title") or "") for item in selected]


def _schema_type_names(value: Any) -> set[str]:
    """Normalize JSON-LD @type values, including schema.org URLs and arrays."""
    values = value if isinstance(value, list) else [value]
    result: set[str] = set()
    for item in values:
        if not item:
            continue
        text = str(item).strip()
        if not text:
            continue
        # Handles:
        #   LocalBusiness
        #   https://schema.org/LocalBusiness
        #   http://schema.org/LocalBusiness
        normalized = text.rstrip("/").rsplit("/", 1)[-1].split(":", 1)[-1]
        result.add(normalized)
    return result


def _extract_page(html: str, url: str, focus_keyword: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    # JSON-LD MUST be extracted before script tags are removed.
    schema_types: set[str] = set()
    json_ld_detected = False
    schema_parse_errors = 0
    faq_schema_question_count = 0
    local_business_schema_present = False

    def visit_schema(item: Any) -> None:
        nonlocal faq_schema_question_count, local_business_schema_present

        if isinstance(item, list):
            for child in item:
                visit_schema(child)
            return

        if not isinstance(item, dict):
            return

        types = _schema_type_names(item.get("@type"))
        schema_types.update(types)

        if "LocalBusiness" in types or any(
            name.endswith("LocalBusiness") for name in types
        ):
            local_business_schema_present = True

        if "FAQPage" in types:
            main_entity = item.get("mainEntity")
            questions = main_entity if isinstance(main_entity, list) else [main_entity]
            for question in questions:
                if not isinstance(question, dict):
                    continue
                q_types = _schema_type_names(question.get("@type"))
                if "Question" in q_types or question.get("name") or question.get("acceptedAnswer"):
                    faq_schema_question_count += 1

        graph = item.get("@graph")
        if isinstance(graph, list):
            for child in graph:
                visit_schema(child)

        # Some implementations nest structured entities under other object
        # properties. Walk dict/list children without relying on a fixed graph shape.
        for key, value in item.items():
            if key in {"@context", "@type", "@id", "@graph", "mainEntity"}:
                continue
            if isinstance(value, (dict, list)):
                visit_schema(value)

    schema_scripts = soup.find_all(
        "script",
        attrs={"type": re.compile(r"^\s*application/ld\+json\s*$", re.I)},
    )

    for script in schema_scripts:
        json_ld_detected = True
        raw = script.string if script.string is not None else script.get_text()
        raw = (raw or "").strip()

        # Be tolerant of HTML comments occasionally wrapped around JSON-LD.
        raw = re.sub(r"^\s*<!--\s*", "", raw)
        raw = re.sub(r"\s*-->\s*$", "", raw)

        if not raw:
            schema_parse_errors += 1
            continue

        try:
            visit_schema(json.loads(raw))
        except (json.JSONDecodeError, TypeError, ValueError):
            schema_parse_errors += 1

            # Do not pretend malformed JSON-LD is valid. However, preserve
            # obvious @type evidence so the UI can explain a parser problem
            # instead of incorrectly saying that no schema exists.
            raw_types = re.findall(
                r'"@type"\s*:\s*(?:"([^"]+)"|\[\s*([^\]]+)\])',
                raw,
                flags=re.I | re.S,
            )
            for single, array_body in raw_types:
                if single:
                    schema_types.update(_schema_type_names(single))
                elif array_body:
                    for value in re.findall(r'"([^"]+)"', array_body):
                        schema_types.update(_schema_type_names(value))

    # Remove executable/presentation-only elements only AFTER schema extraction.
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True).strip() if soup.title else ""
    meta_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_description = str(meta_tag.get("content") or "").strip() if meta_tag else ""
    canonical = ""
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    if canonical_tag:
        canonical = str(canonical_tag.get("href") or "").strip()

    h1s = [
        re.sub(r"\s+", " ", x.get_text(" ", strip=True)).strip()
        for x in soup.find_all("h1")
    ]
    headings = [
        {
            "level": int(tag.name[1]),
            "text": re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip(),
        }
        for tag in soup.find_all(["h2", "h3", "h4"])
        if tag.get_text(" ", strip=True)
    ]

    main = soup.find("main") or soup.find("article") or soup.body or soup
    content_html = str(main)[:120000]
    text = _strip_html(content_html)
    word_count = _word_count(text)
    first_200 = " ".join(text.split()[:200])

    host = urlparse(url).netloc.lower().lstrip("www.")
    internal_links = 0
    external_links = 0
    for anchor in main.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        parsed = urlparse(href)
        if parsed.netloc and parsed.netloc.lower().lstrip("www.") != host:
            external_links += 1
        else:
            internal_links += 1

    answer_headings = [
        h["text"]
        for h in headings
        if re.search(r"\b(what|why|how|when|where|who|which|can|does|is|are)\b", h["text"], re.I)
    ]

    # Visible author/date signals plus JSON-LD author/date signals.
    author_present = bool(
        soup.find("meta", attrs={"name": re.compile("^author$", re.I)})
        or soup.find(attrs={"rel": "author"})
        or soup.find(class_=re.compile("author", re.I))
    )
    date_present = bool(
        soup.find("time")
        or soup.find("meta", attrs={"property": re.compile("article:(published|modified)_time", re.I)})
    )

    kw = focus_keyword.strip()
    schema_type_count = len(schema_types)
    title_score = 100 if 30 <= len(title) <= 65 else 70 if title else 0
    meta_score = 100 if 120 <= len(meta_description) <= 165 else 70 if meta_description else 0
    h1_score = 100 if len(h1s) == 1 else 50 if h1s else 0
    content_score = min(100, round(word_count / 18))
    answer_score = min(
        100,
        len(answer_headings) * 20
        + (20 if re.search(r"\b(is|are|means|refers to|typically)\b", first_200, re.I) else 0),
    )

    # A valid LocalBusiness/FAQPage is stronger entity evidence than merely
    # counting arbitrary JSON-LD types.
    entity_score = min(
        100,
        schema_type_count * 15
        + (25 if local_business_schema_present else 0)
        + (15 if "FAQPage" in schema_types else 0)
        + (15 if author_present else 0)
        + (10 if date_present else 0),
    )

    checks = [
        {"key": "title", "label": "Title tag", "score": title_score, "detail": f"{len(title)} characters" if title else "Missing title tag"},
        {"key": "meta_description", "label": "Meta description", "score": meta_score, "detail": f"{len(meta_description)} characters" if meta_description else "Missing meta description"},
        {"key": "h1", "label": "H1 structure", "score": h1_score, "detail": f"{len(h1s)} H1 tag(s) detected"},
        {"key": "content_depth", "label": "Content depth", "score": content_score, "detail": f"{word_count:,} words"},
        {"key": "answer_engine", "label": "Answer-engine structure", "score": answer_score, "detail": f"{len(answer_headings)} question-style heading(s)"},
        {
            "key": "entity",
            "label": "Entity/trust signals",
            "score": entity_score,
            "detail": (
                f"{schema_type_count} JSON-LD type(s), "
                f"LocalBusiness={'yes' if local_business_schema_present else 'no'}, "
                f"FAQPage={'yes' if 'FAQPage' in schema_types else 'no'}, "
                f"author={'yes' if author_present else 'no'}, "
                f"date={'yes' if date_present else 'no'}"
            ),
        },
        {"key": "internal_links", "label": "Internal linking", "score": min(100, internal_links * 15), "detail": f"{internal_links} internal link(s)"},
    ]

    if kw:
        checks.extend([
            {
                "key": "keyword_title",
                "label": "Focus keyword in title",
                "score": 100 if _keyword_count(title, kw) else 0,
                "detail": "Present" if _keyword_count(title, kw) else "Missing",
            },
            {
                "key": "keyword_h1",
                "label": "Focus keyword in H1",
                "score": 100 if any(_keyword_count(h, kw) for h in h1s) else 0,
                "detail": "Present" if any(_keyword_count(h, kw) for h in h1s) else "Missing",
            },
            {
                "key": "keyword_intro",
                "label": "Focus keyword in introduction",
                "score": 100 if _keyword_count(first_200, kw) else 0,
                "detail": "Present" if _keyword_count(first_200, kw) else "Missing",
            },
        ])

    overall = round(sum(int(x["score"]) for x in checks) / len(checks)) if checks else 0

    return {
        "url": url,
        "title": title,
        "meta_title": title,
        "meta_description": meta_description,
        "canonical": canonical,
        "h1s": h1s,
        "headings": headings[:80],
        "word_count": word_count,
        "schema_types": sorted(schema_types),
        "json_ld_detected": json_ld_detected,
        "schema_parse_errors": schema_parse_errors,
        "faq_schema_present": "FAQPage" in schema_types,
        "faq_schema_question_count": faq_schema_question_count,
        "local_business_schema_present": local_business_schema_present,
        "internal_links": internal_links,
        "external_links": external_links,
        "focus_keyword": kw,
        "focus_keyword_occurrences": _keyword_count(text, kw),
        "checks": checks,
        "measured_score": overall,
        "content_html": content_html,
        "content_text_excerpt": _safe_excerpt(text),
        "answer_headings": answer_headings[:20],
        "author_present": author_present,
        "date_present": date_present,
    }

async def _fetch_public_page(url: str) -> str:
    _reject_private_target(url)
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch the post URL: {exc}") from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"The post returned HTTP {response.status_code}.")
    if "html" not in response.headers.get("content-type", "").lower():
        raise HTTPException(status_code=415, detail="The supplied URL did not return an HTML page.")
    return response.text[:300000]


def _resolve_anthropic_api_key(db: Session, company_id: str) -> str:
    """Resolve the Claude key using the existing AI Settings architecture.

    Priority:
    1. The current company's encrypted Anthropic key saved in Settings → AI.
    2. The global ANTHROPIC_API_KEY configuration fallback.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is not None:
        encrypted_key = getattr(company, "anthropic_api_key_encrypted", None)
        if encrypted_key:
            try:
                api_key = str(decrypt_secret(str(encrypted_key).strip()) or "").strip()
            except Exception as exc:
                logger.exception("Could not decrypt the company's Anthropic API key")
                raise HTTPException(
                    status_code=503,
                    detail="The stored Claude API key could not be decrypted. Open Settings → AI and save the Anthropic API key again.",
                ) from exc
            if api_key:
                return api_key

    global_key = getattr(settings, "ANTHROPIC_API_KEY", None) or os.getenv("ANTHROPIC_API_KEY", "")
    global_key = str(global_key or "").strip()
    if global_key:
        return global_key

    raise HTTPException(
        status_code=503,
        detail="Claude API key is not configured. Open Settings → AI and configure your Anthropic API key.",
    )


def _anthropic_model() -> str:
    """Use the same configured Anthropic model setting used by other AI modules."""
    model = getattr(settings, "ANTHROPIC_MODEL", None) or os.getenv("AI_SEARCH_OPTIMIZATION_MODEL", "")
    model = str(model or "").strip()
    return model or "claude-sonnet-4-6"


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                raise HTTPException(status_code=502, detail="Claude returned an invalid optimization response.") from exc
        else:
            raise HTTPException(status_code=502, detail="Claude returned an invalid optimization response.") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="Claude returned an invalid optimization response.")
    return parsed


async def _claude_json(
    system: str,
    prompt: str,
    api_key: str,
    max_tokens: int = 7000,
) -> dict[str, Any]:
    client = AsyncAnthropic(api_key=api_key)
    try:
        response = await client.messages.create(
            model=_anthropic_model(),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        logger.exception("AI Search Optimization Claude request failed")
        message = str(exc)
        if "credit" in message.lower() or "billing" in message.lower():
            raise HTTPException(status_code=402, detail="Anthropic billing is required for AI Search Optimization.") from exc
        raise HTTPException(status_code=502, detail="Claude AI is currently unavailable. Please check the backend AI configuration.") from exc
    return _parse_json("".join(block.text for block in response.content if hasattr(block, "text")))



async def _ai_unique_focus_keyword(
    title: str,
    content: str,
    requested_keyword: str,
    used_keywords: list[str],
    api_key: str,
    inventory: list[dict[str, Any]] | None = None,
) -> str:
    """Ask Claude for a topic-specific unused focus keyword and validate it locally."""
    fallback, _ = _choose_focus_keyword(title, content, "", used_keywords)

    system = """You are an expert SEO keyword strategist.
Choose ONE useful focus keyword for the supplied article.
The phrase must describe the article's actual primary topic, be natural for a Google search,
and be specific enough to distinguish this article from the site's existing keyword assignments.
Do not invent services, locations, facts, prices, guarantees, or topics not supported by the article.
Do not use a keyword from the used-keyword list.
Do not return a sentence, punctuation, quotes, or an explanation.
Return JSON only: {"focus_keyword": "..."}. The phrase should normally contain 3-7 meaningful words."""
    inventory = inventory or []
    source_intent = _intent_profile(title, content)
    prompt = f"""
Article title:
{title}

Article content excerpt:
{_safe_excerpt(content, 9000)}

Requested keyword that is unavailable:
{requested_keyword or "(none)"}

Detected article intent:
{source_intent}

Existing WordPress focus-keyword assignments. Do NOT reuse these exact assigned phrases:
{json.dumps(_dedupe_keywords(used_keywords)[:500], ensure_ascii=False)}

Existing site topic/intent map. Avoid selecting a phrase that simply reproduces the same
commercial service intent for an informational article, or the same informational topic
for a service page. Shared words are allowed; the goal is distinct search intent, not
artificial word-level separation:
{json.dumps([
    {"title": x.get("title", ""), "focus_keyword": x.get("focus_keyword", ""),
     "intent": _intent_profile(str(x.get("title", "")), "", str(x.get("focus_keyword", "")))}
    for x in inventory[:500]
], ensure_ascii=False)}

Return one replacement focus keyword that is genuinely useful for this exact article,
reflects its existing intent, and clearly differentiates it from the site's existing
assignments. Use 3-7 meaningful words when possible. Do not add unsupported services,
locations, facts, or claims.
"""
    try:
        result = await _claude_json(system, prompt, api_key=api_key, max_tokens=800)
        candidate = re.sub(
            r"^[\s\"'`]+|[\s\"'`,.]+$",
            "",
            str(result.get("focus_keyword") or result.get("suggested_focus_keyword") or ""),
        ).strip()
        if candidate and not _keyword_conflicts(candidate, set(used_keywords)):
            # Reject suggestions that are essentially generic fragments.
            if len(_keyword_tokens(candidate)) >= 3:
                return candidate
    except HTTPException:
        logger.exception("AI focus-keyword suggestion failed; using deterministic fallback")

    return fallback

async def _ai_repair_metadata(
    rewrite: dict[str, Any],
    source_title: str,
    source_content: str,
    inventory: list[dict[str, str]],
    api_key: str,
) -> dict[str, str]:
    """Repair title/SEO metadata when generated fields collide with site inventory."""
    system = """You are a senior technical SEO editor. Repair only the page title, SEO title, and meta description. Keep the article's existing search intent and facts. Do not turn an informational article into a commercial service page. Do not invent facts. The H1/title, SEO title, and meta description must be distinct but clearly related. The focus keyword is a targeting reference, not a phrase that must appear in every field. Return only JSON."""
    prompt = f"""
Original article title:
{source_title}

Selected focus keyword:
{str(rewrite.get('focus_keyword') or '').strip()}

Current generated title:
{str(rewrite.get('title') or '').strip()}

Current generated SEO title:
{str(rewrite.get('meta_title') or '').strip()}

Current generated meta description:
{str(rewrite.get('meta_description') or '').strip()}

Existing site title/metadata inventory:
{json.dumps(inventory[:500], ensure_ascii=False, indent=2)}

Collision checks:
{json.dumps(_validate_rewrite_seo(rewrite, inventory, source_title, source_content), ensure_ascii=False, indent=2)}

Article excerpt:
{_safe_excerpt(source_content, 10000)}

Return exactly:
{{
  "title": "",
  "meta_title": "",
  "meta_description": ""
}}

Rules:
- Preserve the article's real topic and current search intent.
- If the article is informational, keep the title informational; do not make it a service landing page.
- If the article is commercial, keep the commercial intent accurate.
- Do not copy or closely paraphrase an existing site title or metadata field.
- The SEO title must be a distinct search-result candidate, not a copy of the H1/title.
- The meta description must summarize the actual article, not restate the title.
- The exact focus keyword may be used where natural, but it is NOT mandatory in title, SEO title, or description.
- Avoid keyword stuffing, repetitive brand/service phrasing, clickbait, and unsupported claims.
- Keep the SEO title concise; keep the description useful and natural rather than chasing an artificial fixed character count.
"""
    try:
        result = await _claude_json(system, prompt, api_key=api_key, max_tokens=1800)
        return {
            "title": str(result.get("title") or "").strip(),
            "meta_title": str(result.get("meta_title") or "").strip(),
            "meta_description": str(result.get("meta_description") or "").strip(),
        }
    except Exception:
        logger.exception("AI metadata repair failed; using deterministic fallback")
        return {}


@router.post("/suggest-focus-keyword")
async def suggest_focus_keyword(
    data: FocusKeywordSuggestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return an AI-generated unused focus keyword plus deterministic alternatives.

    This endpoint is intentionally separate from analysis so the UI can show a useful
    replacement immediately when a duplicate assigned WordPress focus keyword is typed.
    Uniqueness is validated locally against the authoritative inventory supplied by the UI.
    """
    company_id = _require_company(current_user)
    api_key = _resolve_anthropic_api_key(db, company_id)
    used = _dedupe_keywords([str(x).strip() for x in data.used_focus_keywords if str(x).strip()])
    primary = await _ai_unique_focus_keyword(
        data.title,
        _strip_html(data.content),
        data.current_focus_keyword.strip(),
        used,
        api_key,
        [],
    )
    alternatives: list[str] = []
    for candidate in _focus_candidates(data.title, _strip_html(data.content), {_normalize_phrase(x) for x in used}):
        if _normalize_phrase(candidate) == _normalize_phrase(primary):
            continue
        if _keyword_conflicts(candidate, used):
            continue
        if candidate not in alternatives:
            alternatives.append(candidate)
        if len(alternatives) >= 4:
            break
    return {
        "success": True,
        "suggested_focus_keyword": primary,
        "alternatives": alternatives,
    }


@router.post("/analyze")
async def analyze_post(
    data: AnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _require_company(current_user)
    api_key = _resolve_anthropic_api_key(db, company_id)
    url = _clean_url(str(data.url))
    html = await _fetch_public_page(url)
    measured = _extract_page(html, url, data.focus_keyword)
    used_keywords = [str(x).strip() for x in data.used_focus_keywords if str(x).strip()]
    inventory = _inventory_for_source(data.site_content_inventory, url)
    inventory_focus_keywords = [str(x.get("focus_keyword") or "").strip() for x in inventory if str(x.get("focus_keyword") or "").strip()]
    used_keywords = _dedupe_keywords(used_keywords + inventory_focus_keywords)
    used_for_prompt = used_keywords[:500]
    source_intent = _intent_profile(measured["title"], measured["content_text_excerpt"])
    intent_collisions = _topic_intent_collisions(measured["title"], data.focus_keyword, measured["content_text_excerpt"], inventory)
    requested_keyword = data.focus_keyword.strip()
    used_keyword_set = {_normalize_phrase(x) for x in used_keywords if _normalize_phrase(x)}
    if requested_keyword and _keyword_conflicts(requested_keyword, used_keyword_set):
        suggested_keyword = await _ai_unique_focus_keyword(
            measured["title"],
            measured["content_text_excerpt"],
            requested_keyword,
            used_keywords,
            api_key,
            inventory,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "code": "FOCUS_KEYWORD_DUPLICATE",
                "message": "Focus keyword already in use by another WordPress post or page. Choose an unused keyword before analyzing or rewriting.",
                "conflicting_keyword": requested_keyword,
                "suggested_focus_keyword": suggested_keyword,
                "suggestion_source": "ai",
            },
        )
    system = """You are a senior SEO and answer-engine optimization consultant. Analyze only supplied page evidence. Never claim that a page is cited by ChatGPT, Perplexity, Gemini, Google AI Overviews, or another AI engine unless evidence proves it. Never invent traffic, rankings, citations, entities, schema, competitor data, or search-volume data. Separate measured HTML facts from recommendations. Build a site-level topic/intent map from the supplied WordPress inventory. Distinguish commercial service intent from informational article intent. If no focus keyword is supplied, recommend one concise topic phrase derived only from the page title/content and existing intent. It must not duplicate any assigned focus keyword. Do not mechanically force the keyword into every SEO field. Return only JSON."""
    prompt = f"""
Page: {url}
Focus keyword: {data.focus_keyword or '(automatic selection required)'}
Already-used focus keywords (do not reuse exactly): {json.dumps(used_for_prompt, ensure_ascii=False)}

Detected source intent: {source_intent}

Existing site topic / intent map:
{json.dumps([{
    "title": x.get("title", ""), "focus_keyword": x.get("focus_keyword", ""),
    "meta_title": x.get("meta_title", ""),
    "intent": _intent_profile(str(x.get("title", "")), "", str(x.get("focus_keyword", "")))
} for x in inventory[:500]], ensure_ascii=False)}

Potential same-intent topic collisions (warning only; do not infer ranking impact):
{json.dumps(intent_collisions, ensure_ascii=False)}

Measured evidence:
{json.dumps({k: v for k, v in measured.items() if k not in {'content_html'}}, indent=2)}

Content excerpt:
{measured['content_text_excerpt']}

Return exactly:
{{
  "ai_search_score": 0,
  "content_quality": 0,
  "answer_engine_readiness": 0,
  "entity_readiness": 0,
  "semantic_coverage": 0,
  "summary": "",
  "critical_issues": [],
  "high_priority_actions": [],
  "quick_wins": [],
  "rewrite_recommended": false,
  "rewrite_reason": "",
  "suggested_focus_keyword": "",
  "suggested_title": "",
  "suggested_meta_title": "",
  "suggested_meta_description": ""
}}
Scores are 0-100 and must be grounded in the evidence.
"""
    ai = await _claude_json(system, prompt, api_key=api_key, max_tokens=5000)
    suggested_keyword = str(ai.get("suggested_focus_keyword") or "").strip()
    chosen_keyword, conflict = _choose_focus_keyword(
        measured["title"],
        measured["content_text_excerpt"],
        requested_keyword or suggested_keyword,
        used_keywords,
    )
    measured = _extract_page(html, url, chosen_keyword)
    ai["suggested_focus_keyword"] = chosen_keyword
    ai["focus_keyword_auto_selected"] = not bool(requested_keyword) or conflict
    ai["focus_keyword_conflict"] = conflict
    ai["search_intent"] = str(ai.get("search_intent") or source_intent).strip().lower() or source_intent
    ai["topic_cluster"] = str(ai.get("topic_cluster") or "").strip()
    ai["intent_collision_risk"] = str(ai.get("intent_collision_risk") or ("medium" if intent_collisions else "low")).strip().lower()
    ai["intent_collision_with"] = ai.get("intent_collision_with") if isinstance(ai.get("intent_collision_with"), list) else intent_collisions
    ai["keyword_plan"] = ai.get("keyword_plan") if isinstance(ai.get("keyword_plan"), dict) else {"role": "", "reason": ""}
    if conflict:
        ai.setdefault("quick_wins", []).insert(0, f"The requested focus keyword was already used elsewhere, so an unused title-derived keyword was selected automatically: {chosen_keyword}.")
    for key in ("ai_search_score", "content_quality", "answer_engine_readiness", "entity_readiness", "semantic_coverage"):
        try:
            ai[key] = max(0, min(100, int(ai.get(key, measured["measured_score"]))))
        except (TypeError, ValueError):
            ai[key] = measured["measured_score"]
    return {"success": True, "measured": measured, "ai_analysis": ai}


def _link_terms(value: str) -> set[str]:
    """Return meaningful lexical terms used for conservative target relevance matching."""
    return {
        token
        for token in re.findall(r"[a-z0-9]+", _normalize_phrase(value))
        if len(token) >= 3 and token not in LINK_STOPWORDS
    }


def _is_service_target(candidate: dict[str, str]) -> bool:
    """Identify likely service/solution pages without assuming a WordPress URL structure."""
    text = _normalize_phrase(
        " ".join(
            [
                str(candidate.get("title") or ""),
                str(candidate.get("focus_keyword") or ""),
                str(candidate.get("excerpt") or ""),
            ]
        )
    )
    service_terms = {
        "service", "services", "cleaning", "commercial", "office", "school", "warehouse",
        "carpet", "house", "industrial", "retail", "medical", "hotel", "gym", "window",
        "disinfection", "sanitation", "facility", "janitorial",
    }
    return bool(set(text.split()) & service_terms)


def _select_internal_link_candidates(
    source_url: str,
    title: str,
    content: str,
    focus_keyword: str,
    candidates: list[dict[str, str]],
) -> list[dict[str, str]]:
    """
    Select 3-5 verified, non-self WordPress targets using the source topic plus
    target title, focus keyword, excerpt and content evidence.

    The selector is deliberately conservative: it prefers topical matches and
    relevant service pages, but never invents a URL or forces a target with no
    meaningful topical connection.
    """
    source_key = _canonical_url(source_url)
    source_text = " ".join([title, focus_keyword, content[:16000]])
    source_terms = _link_terms(source_text)
    focus_norm = _normalize_phrase(focus_keyword)

    scored: list[tuple[float, dict[str, str]]] = []
    seen: set[str] = set()

    for candidate in candidates:
        url = str(candidate.get("url") or "").strip()
        target_title = str(candidate.get("title") or "").strip()
        if not url or not target_title:
            continue

        target_key = _canonical_url(url, source_url)
        if target_key == source_key or target_key in seen:
            continue
        seen.add(target_key)

        target_focus = str(candidate.get("focus_keyword") or "").strip()
        target_excerpt = _strip_html(str(candidate.get("excerpt") or ""))
        target_content = _strip_html(str(candidate.get("content_html") or ""))[:12000]
        target_text = " ".join([target_title, target_focus, target_excerpt, target_content])
        target_terms = _link_terms(target_text)

        title_overlap = len(_link_terms(target_title) & source_terms)
        focus_overlap = len(_link_terms(target_focus) & source_terms)
        body_overlap = len(_link_terms(target_excerpt + " " + target_content) & source_terms)
        total_overlap = len(source_terms & target_terms)

        score = (
            (title_overlap * 14)
            + (focus_overlap * 18)
            + (body_overlap * 2)
            + (total_overlap * 3)
        )

        normalized_target_title = _normalize_phrase(target_title)
        normalized_target_focus = _normalize_phrase(target_focus)
        normalized_source_title = _normalize_phrase(title)
        normalized_source_focus = _normalize_phrase(focus_keyword)

        # Phrase-level evidence is stronger than isolated word overlap.
        if normalized_source_focus and normalized_source_focus in (
            normalized_target_title + " " + normalized_target_focus
        ):
            score += 24

        if normalized_source_title and normalized_source_title in (
            normalized_target_title + " " + normalized_target_focus
        ):
            score += 16

        if focus_norm and focus_norm in (
            normalized_target_title + " " + normalized_target_focus
        ):
            score += 18

        if str(candidate.get("type") or "").lower() == "page":
            score += 3

        # Prefer a genuinely relevant service target, but only when the source
        # itself contains related service language.
        if _is_service_target(candidate):
            service_overlap = len(
                _link_terms(target_title + " " + target_focus) & source_terms
            )
            if service_overlap:
                score += 14 + (service_overlap * 3)

        # A target with no meaningful lexical evidence should not be selected
        # merely because it is a page or service.
        if title_overlap == 0 and focus_overlap == 0 and total_overlap == 0:
            continue

        normalized = {
            "id": str(candidate.get("id") or ""),
            "type": str(candidate.get("type") or ""),
            "title": target_title,
            "url": url,
            "focus_keyword": target_focus,
            "excerpt": target_excerpt[:2500],
            "content_html": str(candidate.get("content_html") or "")[:6000],
        }
        scored.append((score, normalized))

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1]["type"] != "page",
            len(item[1]["title"]),
        )
    )

    if not scored:
        return []

    # Start with the strongest topical candidates.
    selected: list[dict[str, str]] = [item[1] for item in scored[:MAX_INTERNAL_LINKS]]

    # If a relevant service target exists just outside the first five, reserve
    # one slot for it rather than filling every slot with generic blog posts.
    service_selected = any(_is_service_target(item) for item in selected)
    if not service_selected:
        for _, candidate in scored[MAX_INTERNAL_LINKS:]:
            if _is_service_target(candidate):
                if selected:
                    selected[-1] = candidate
                else:
                    selected.append(candidate)
                break

    return selected[:MAX_INTERNAL_LINKS]


@router.post("/rewrite")
async def rewrite_post(
    data: RewriteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _require_company(current_user)
    api_key = _resolve_anthropic_api_key(db, company_id)
    source_text = _strip_html(data.content_html)

    # Accept a larger verified candidate set from WordPress, but keep the
    # rewrite/scoring workload bounded and predictable.
    raw_candidates = data.internal_link_candidates[:100]
    normalized_candidates: list[dict[str, str]] = []
    for candidate in raw_candidates:
        if not isinstance(candidate, dict):
            continue
        normalized = {
            str(key): str(value or "").strip()
            for key, value in candidate.items()
        }
        if normalized.get("url") and normalized.get("title"):
            normalized_candidates.append(normalized)

    source_word_count = _word_count(source_text)
    if source_word_count < 100:
        raise HTTPException(status_code=400, detail="The post needs at least 100 readable words before AI rewriting.")

    inventory = _inventory_for_source(data.site_content_inventory, str(data.url))
    inventory_focus_keywords = [str(x.get("focus_keyword") or "").strip() for x in inventory if str(x.get("focus_keyword") or "").strip()]
    rewrite_used_keywords = _dedupe_keywords(
        [str(x).strip() for x in data.used_focus_keywords if str(x).strip()] + inventory_focus_keywords
    )
    if data.focus_keyword.strip() and _keyword_conflicts(
        data.focus_keyword.strip(),
        rewrite_used_keywords,
    ):
        suggested_keyword = await _ai_unique_focus_keyword(
            data.title,
            source_text,
            data.focus_keyword.strip(),
            rewrite_used_keywords,
            api_key,
            inventory,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "code": "FOCUS_KEYWORD_DUPLICATE",
                "message": "Focus keyword already in use by another WordPress post or page. Choose an unused keyword before rewriting.",
                "conflicting_keyword": data.focus_keyword.strip(),
                "suggested_focus_keyword": suggested_keyword,
                "suggestion_source": "ai",
            },
        )

    chosen_keyword, keyword_conflict = _choose_focus_keyword(
        data.title,
        source_text,
        data.focus_keyword,
        rewrite_used_keywords,
    )

    # Select several evidence-backed targets instead of limiting the rewrite to
    # one page. Candidate content/excerpts/focus keywords are used when present.
    target_candidates = _select_internal_link_candidates(
        str(data.url),
        data.title,
        source_text,
        chosen_keyword,
        normalized_candidates,
    )

    target_summary = [
        {
            "id": item.get("id", ""),
            "type": item.get("type", ""),
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "focus_keyword": item.get("focus_keyword", ""),
            "excerpt": item.get("excerpt", ""),
        }
        for item in target_candidates
    ]

    source_intent = _intent_profile(data.title, source_text)
    topic_collisions = _topic_intent_collisions(data.title, chosen_keyword, source_text, inventory)

    system = """You are a senior SEO content editor specializing in helpful content and AI search / answer-engine optimization. Rewrite the supplied article without inventing business facts, statistics, credentials, locations, prices, awards, reviews, or guarantees. Preserve supported facts and the article's real subject. Improve clarity, topical completeness, passage-level answers, entity clarity, headings, internal coherence, and natural semantic keyword usage. Do not keyword-stuff. The rewritten article must remain about the same existing topic. Use the supplied site topic/intent map to differentiate informational articles from commercial service pages. Return only valid JSON."""

    prompt = f"""
Original URL: {data.url}
Current title: {data.title}
Current page intent: {source_intent}
Focus keyword selected for this rewrite: {chosen_keyword}
Current meta title: {data.meta_title}
Current meta description: {data.meta_description}
Source word count: {source_word_count}

Existing site topic / intent map:
{json.dumps([{
    "id": x.get("id", ""), "type": x.get("type", ""), "status": x.get("status", ""),
    "title": x.get("title", ""), "url": x.get("url", ""),
    "focus_keyword": x.get("focus_keyword", ""), "meta_title": x.get("meta_title", ""),
    "meta_description": x.get("meta_description", ""),
    "intent": _intent_profile(str(x.get("title", "")), "", str(x.get("focus_keyword", "")))
} for x in inventory[:500]], ensure_ascii=False, indent=2)}

Potential same-intent topic collisions:
{json.dumps(topic_collisions, ensure_ascii=False, indent=2)}

Existing analysis:
{json.dumps(data.analysis, indent=2)}

Original article:
{source_text[:28000]}

Verified internal-link targets selected from the connected WordPress site:
{json.dumps(target_summary, ensure_ascii=False, indent=2)}

Return ONLY:
{{
  "title": "",
  "focus_keyword": "{chosen_keyword}",
  "meta_title": "",
  "meta_description": "",
  "article_html": "",
  "change_summary": [],
  "search_intent": "{source_intent}",
  "topic_cluster": "",
  "intent_collision_risk": "",
  "intent_collision_with": [],
  "keyword_plan": {{"role": "", "reason": ""}},
  "focus_keyword_usage": {{"title": true, "first_paragraph": true, "headings": true, "body": true, "natural_usage": true}},
  "internal_links_applied": 0
}}

Rules:
- Use exactly this focus keyword as the targeting reference: {chosen_keyword}. Do not switch to a different focus keyword.
- The focus keyword is NOT a phrase that must be mechanically repeated in every SEO field.
- Preserve the existing article's search intent. If the source is informational, keep it informational; do not convert it into a service landing page merely because a service keyword exists elsewhere on the site.
- If the source is commercial, keep the commercial service intent accurate and specific.
- H1/title, SEO title, and meta description must be distinct but related. Do not make them copies of one another.
- The H1/title should clearly communicate the article's actual topic and intent.
- The SEO title is a concise search-result candidate. It may include the focus keyword when natural, but it does not have to.
- The meta description should accurately summarize the article and entice a relevant click without clickbait. It may include the focus keyword when natural, but it does not have to.
- Do not use a fixed keyword-placement formula. Use the focus keyword and semantically related terms where they improve clarity. Never keyword-stuff or repeat a phrase unnaturally.
- Do not copy or closely paraphrase existing site titles, SEO titles, or meta descriptions shown in the inventory.
- Avoid creating the same commercial service intent as an existing service page when this article is informational. Prefer an informational long-tail angle such as a checklist, explanation, process, comparison, mistakes, or decision guidance only when the article actually supports it.
- Do not invent search volume, rankings, competitor data, or unsupported facts.
- Produce complete WordPress-compatible HTML using h2/h3, p, ul/ol, and strong where useful.
- Do not shorten the article. Target at least {max(source_word_count, 1200)} readable words when the source supports expansion; preserve all useful existing information while adding genuinely useful explanations, examples, steps, FAQs, or decision guidance relevant to the existing topic.
- Do not pad with generic filler.
- Use between {MIN_INTERNAL_LINKS} and {MAX_INTERNAL_LINKS} contextual internal links when that many verified targets are supplied. Prefer genuinely relevant targets and use different URLs rather than repeating one URL.
- Only link to verified targets supplied above. Never invent URLs, never link to the current page, and never link to an unrelated service merely to reach the minimum.
- Use natural descriptive anchors based on the target title/focus keyword. Never use generic anchors such as "click here", "read more", or "learn more".
- Place internal links in relevant body paragraphs or lists, never inside headings, existing links, code, pre, scripts, or styles.
- Do not output markdown.
"""

    rewrite = await _claude_json(system, prompt, api_key=api_key, max_tokens=14000)
    rewrite["focus_keyword"] = chosen_keyword
    article_html = str(rewrite.get("article_html") or "")

    if _word_count(_strip_html(article_html)) < max(100, int(source_word_count * 0.9)):
        expand_prompt = f"""Expand the supplied rewritten WordPress article without changing its subject, facts, focus keyword, or title intent. The current article is too short. Return only JSON with the same fields.
Focus keyword: {chosen_keyword}
Minimum readable word count: {max(source_word_count, 1200)}
Current article HTML:
{article_html[:50000]}

Verified internal-link targets that must remain available:
{json.dumps(target_summary, ensure_ascii=False, indent=2)}

Add useful, specific sections, explanations, steps, FAQs, comparisons, or practical guidance only when supported by the existing article topic. Do not invent business facts. Preserve any valid internal links already present and, where natural, add links to other verified targets. Do not invent URLs or add unrelated service links.
"""
        expanded = await _claude_json(system, expand_prompt, api_key=api_key, max_tokens=14000)
        expanded_html = str(expanded.get("article_html") or "")
        if _word_count(_strip_html(expanded_html)) > _word_count(_strip_html(article_html)):
            rewrite = expanded
            rewrite["focus_keyword"] = chosen_keyword
            article_html = expanded_html

    # First keep only verified candidate links. Then add missing links naturally
    # where target wording already exists in the rewritten article.
    article_html, verified_count, linked_targets = _sanitize_internal_links(
        article_html, str(data.url), target_candidates
    )
    article_html, inserted_count, inserted_targets = _insert_contextual_links(
        article_html, str(data.url), target_candidates, verified_count
    )

    current_link_count = verified_count + inserted_count

    # If the article still has fewer than three links but three or more suitable
    # verified targets exist, append a compact related-resources block. This
    # guarantees the product requirement without fabricating or self-linking.
    article_html, minimum_added, minimum_targets = _append_minimum_internal_links(
        article_html,
        str(data.url),
        target_candidates,
        current_link_count,
    )

    final_link_count = min(
        MAX_INTERNAL_LINKS,
        verified_count + inserted_count + minimum_added,
    )
    final_targets = (linked_targets + inserted_targets + minimum_targets)[:MAX_INTERNAL_LINKS]

    rewrite["article_html"] = article_html
    rewrite["focus_keyword"] = chosen_keyword
    rewrite["internal_links_applied"] = final_link_count
    rewrite["internal_link_targets"] = final_targets

    # Validate generated metadata against the complete WordPress inventory. Exact
    # focus-keyword ownership is a hard uniqueness rule; title/meta collisions are
    # repaired so the blog does not inherit a service page's search-result language.
    rewrite["meta_title"] = str(rewrite.get("meta_title") or "").strip()[:500]
    rewrite["meta_description"] = str(rewrite.get("meta_description") or "").strip()[:1000]
    seo_checks = _validate_rewrite_seo(rewrite, inventory, data.title, source_text)
    if seo_checks["needs_repair"]:
        repaired = await _ai_repair_metadata(
            rewrite,
            data.title,
            source_text,
            inventory,
            api_key,
        )
        if repaired.get("title"):
            rewrite["title"] = repaired["title"][:500]
        if repaired.get("meta_title"):
            rewrite["meta_title"] = repaired["meta_title"][:500]
        if repaired.get("meta_description"):
            rewrite["meta_description"] = repaired["meta_description"][:1000]

        # Final deterministic guard. This runs even if the AI repair is unavailable.
        rewrite["title"] = str(rewrite.get("title") or data.title).strip()[:500]
        if not rewrite["meta_title"] or _normalize_phrase(rewrite["meta_title"]) == _normalize_phrase(rewrite["title"]):
            rewrite["meta_title"] = _fallback_distinct_meta_title(rewrite["title"], chosen_keyword, inventory)
        if not rewrite["meta_description"] or _metadata_similarity(rewrite["meta_description"], rewrite["title"]) >= 0.72:
            rewrite["meta_description"] = _fallback_meta_description(
                rewrite["title"], article_html, chosen_keyword, inventory
            )

        # Re-check against the inventory after repair. If an AI-generated repair is
        # still too close to an existing field, use a deterministic distinct variant.
        final_checks = _validate_rewrite_seo(rewrite, inventory, data.title, source_text)
        if final_checks["title_collision"]:
            rewrite["title"] = _fallback_distinct_meta_title(rewrite["title"], chosen_keyword, inventory, "title")
        if final_checks["meta_title_collision"]:
            rewrite["meta_title"] = _fallback_distinct_meta_title(rewrite["title"], chosen_keyword, inventory)
        if final_checks["meta_description_collision"]:
            rewrite["meta_description"] = _fallback_meta_description(
                rewrite["title"], article_html, chosen_keyword, inventory
            )
        rewrite.setdefault("change_summary", []).append(
            "Validated title and SEO metadata against the WordPress topic/intent inventory and repaired overlapping metadata."
        )

    if not rewrite["meta_title"]:
        rewrite["meta_title"] = _fallback_distinct_meta_title(
            rewrite["title"] or data.title, chosen_keyword, inventory
        )
    if not rewrite["meta_description"]:
        rewrite["meta_description"] = _fallback_meta_description(
            rewrite["title"] or data.title, article_html, chosen_keyword, inventory
        )

    rewrite["meta_title"] = str(rewrite["meta_title"]).strip()[:500]
    rewrite["meta_description"] = str(rewrite["meta_description"]).strip()[:1000]
    rewrite["search_intent"] = str(rewrite.get("search_intent") or source_intent).strip().lower()
    rewrite["topic_cluster"] = str(rewrite.get("topic_cluster") or "").strip()
    rewrite["intent_collision_risk"] = str(rewrite.get("intent_collision_risk") or ("medium" if topic_collisions else "low")).strip().lower()
    rewrite["intent_collision_with"] = rewrite.get("intent_collision_with") if isinstance(rewrite.get("intent_collision_with"), list) else topic_collisions
    rewrite["keyword_plan"] = rewrite.get("keyword_plan") if isinstance(rewrite.get("keyword_plan"), dict) else {"role": "", "reason": ""}

    if keyword_conflict:
        rewrite.setdefault("change_summary", []).append(
            f"Replaced the requested focus keyword with the unused keyword: {chosen_keyword}."
        )

    if final_link_count:
        rewrite.setdefault("change_summary", []).append(
            f"Added {final_link_count} contextual internal link(s) using verified WordPress targets."
        )
    elif len(target_candidates) < MIN_INTERNAL_LINKS:
        rewrite.setdefault("change_summary", []).append(
            f"Fewer than {MIN_INTERNAL_LINKS} suitable verified internal-link targets were available, so unrelated URLs were not forced."
        )

    return {"success": True, "rewrite": rewrite}


@router.post("/wordpress/content")
async def wordpress_content(data: WordPressCredentialsRequest, current_user: User = Depends(get_current_user)):
    _require_company(current_user)
    site = _clean_url(str(data.wordpress_site))
    wordpress_username = data.wordpress_username.strip()
    # WordPress displays Application Passwords in groups separated by spaces.
    # Basic Auth is more reliable when those presentation spaces are removed.
    wordpress_application_password = re.sub(
        r"\s+",
        "",
        data.wordpress_application_password or "",
    )
    auth = (wordpress_username, wordpress_application_password)

    async with httpx.AsyncClient(timeout=WP_TIMEOUT, follow_redirects=True) as client:
        me = await _wordpress_request(
            client, site, "/wp/v2/users/me",
            params={"context": "edit"},
            auth=auth,
        )
        if me.status_code >= 400:
            if me.status_code in {401, 403}:
                detail = (
                    "WordPress authentication failed. Check the WordPress username "
                    "and Application Password. Use a WordPress Application Password "
                    "(not the normal account password)."
                )
            else:
                detail = (
                    f"WordPress REST API returned HTTP {me.status_code}. "
                    "The REST API endpoint could not be found. Verify the WordPress site URL, "
                    "permalink/REST API configuration, and that /wp-json/ or ?rest_route= is available."
                )
            raise HTTPException(status_code=401 if me.status_code in {401, 403} else 502, detail=detail)

        items: list[dict[str, Any]] = []
        max_items = 5000

        for content_type in ("posts", "pages"):
            page_num = 1
            while len(items) < max_items:
                response = await _wordpress_request(
                    client, site, f"/wp/v2/{content_type}",
                    params={
                        "per_page": 100,
                        "page": page_num,
                        "context": "edit",
                        "orderby": "modified",
                        "order": "desc",
                        "_fields": "id,link,title,status,modified,content,excerpt,meta",
                    },
                    auth=auth,
                )
                if response.status_code >= 400:
                    break
                try:
                    rows = response.json()
                except Exception:
                    break
                if not isinstance(rows, list) or not rows:
                    break

                for row in rows:
                    title = str((row.get("title") or {}).get("rendered") or "").strip()
                    if not title:
                        continue
                    row_meta = row.get("meta") or {}
                    row_seo = _extract_seo_metadata(row_meta)
                    items.append(
                        {
                            "id": int(row["id"]),
                            "type": "post" if content_type == "posts" else "page",
                            "title": title,
                            "url": str(row.get("link") or ""),
                            "status": str(row.get("status") or ""),
                            "modified": str(row.get("modified") or ""),
                            "content_html": str((row.get("content") or {}).get("rendered") or ""),
                            "excerpt": str((row.get("excerpt") or {}).get("rendered") or ""),
                            "focus_keyword": _extract_focus_keyword(row_meta),
                            "focus_keyword_source": "wp_rest_meta" if _extract_focus_keyword(row_meta) else "",
                            "meta_title": row_seo["meta_title"],
                            "meta_description": row_seo["meta_description"],
                        }
                    )
                    if len(items) >= max_items:
                        break

                total_pages = int(response.headers.get("X-WP-TotalPages", "0") or 0)
                if len(rows) < 100 or (total_pages and page_num >= total_pages):
                    break
                page_num += 1

        inventory_capped = len(items) >= max_items

        bridge = await _wordpress_request(
            client, site, "/boost-rankers/v1/seo-meta/status", auth=auth,
        )
        focus_inventory_verified = False
        focus_inventory_error = ""

        if inventory_capped:
            focus_inventory_error = (
                f"WordPress contains more than {max_items} posts/pages, so the full "
                "focus-keyword inventory could not be verified."
            )
        elif bridge.status_code == 200 and bool((bridge.json() if bridge.content else {}).get("yoast_active", True)):
            focus_inventory_verified = True
            semaphore = asyncio.Semaphore(10)
            lookup_failures: list[str] = []

            async def load_focus(item: dict[str, Any]) -> None:
                nonlocal focus_inventory_verified
                async with semaphore:
                    try:
                        meta = await _wordpress_request(
                            client, site, f"/boost-rankers/v1/seo-meta/{int(item['id'])}",
                            auth=auth,
                        )
                        payload: Any = meta.json() if meta.status_code < 400 else None
                        has_focus_field = _has_explicit_focus_keyword_field(payload) if payload is not None else False
                        value = _extract_focus_keyword(payload) if payload is not None else ""

                        # If the bridge returns HTTP 200 but omits the Yoast field,
                        # verify through native WordPress REST meta before declaring
                        # the keyphrase empty. This prevents false "unused" results.
                        if not has_focus_field:
                            native = await _wordpress_request(
                                client, site,
                                f"/wp/v2/{'posts' if item.get('type') == 'post' else 'pages'}/{int(item['id'])}",
                                params={"context": "edit", "_fields": "id,meta"},
                                auth=auth,
                            )
                            if native.status_code < 400:
                                native_payload = native.json()
                                has_focus_field = _has_explicit_focus_keyword_field(native_payload)
                                if has_focus_field:
                                    value = _extract_focus_keyword(native_payload)
                                    payload = {"bridge": payload, "native": native_payload}

                        if not has_focus_field:
                            lookup_failures.append(f"{item.get('type', 'item')} {item.get('id')}")
                            focus_inventory_verified = False
                            return

                        item["focus_keyword"] = value
                        item["focus_keyword_source"] = "yoast"
                        seo_values = _extract_seo_metadata(payload) if payload is not None else {"meta_title": "", "meta_description": ""}
                        if seo_values["meta_title"]:
                            item["meta_title"] = seo_values["meta_title"]
                        if seo_values["meta_description"]:
                            item["meta_description"] = seo_values["meta_description"]
                    except Exception as exc:
                        lookup_failures.append(f"{item.get('type', 'item')} {item.get('id')}: {exc}")
                        focus_inventory_verified = False

            await asyncio.gather(*(load_focus(item) for item in items))
            if lookup_failures:
                focus_inventory_error = (
                    "Yoast focus-keyphrase inventory could not be verified for "
                    f"{len(lookup_failures)} WordPress item(s). The SEO Bridge must expose "
                    "the Yoast focus keyphrase field; an omitted field is not treated as empty."
                )
        elif bridge.status_code == 200:
            focus_inventory_error = "Yoast SEO is not reported as active by the Boost Rankers SEO Bridge."
        else:
            # The standard WP REST response may expose SEO meta directly. If the
            # Bridge is unavailable we cannot safely claim that an empty field is
            # an unused focus keyword, so callers must fail closed for uniqueness.
            focus_inventory_error = (
                "Boost Rankers SEO Bridge is not available, so assigned WordPress "
                "focus keywords could not be verified."
            )

        mapped_focus_keyword_count = sum(1 for item in items if str(item.get("focus_keyword") or "").strip())
        return {
            "success": True,
            "items": items,
            "focus_keyword_inventory_verified": focus_inventory_verified,
            "focus_keyword_inventory_error": focus_inventory_error,
            "focus_keyword_count": mapped_focus_keyword_count,
            "focus_keyword_total_items": len(items),
        }


@router.post("/wordpress/apply")
async def apply_to_wordpress(data: WordPressApplyRequest, current_user: User = Depends(get_current_user)):
    _require_company(current_user)
    site = _clean_url(str(data.wordpress_site))
    wordpress_username = data.wordpress_username.strip()
    # WordPress displays Application Passwords in groups separated by spaces.
    # Basic Auth is more reliable when those presentation spaces are removed.
    wordpress_application_password = re.sub(
        r"\s+",
        "",
        data.wordpress_application_password or "",
    )
    auth = (wordpress_username, wordpress_application_password)
    async with httpx.AsyncClient(timeout=WP_TIMEOUT, follow_redirects=True) as client:
        me = await _wordpress_request(
            client, site, "/wp/v2/users/me",
            params={"context": "edit"},
            auth=auth,
        )
        if me.status_code >= 400:
            if me.status_code in {401, 403}:
                detail = (
                    "WordPress authentication failed. Check the WordPress username "
                    "and Application Password. Use a WordPress Application Password "
                    "(not the normal account password)."
                )
            else:
                detail = (
                    f"WordPress REST API returned HTTP {me.status_code}. "
                    "The REST API endpoint could not be found. Verify the WordPress site URL, "
                    "permalink/REST API configuration, and that /wp-json/ or ?rest_route= is available."
                )
            raise HTTPException(
                status_code=401 if me.status_code in {401, 403} else 502,
                detail=detail,
            )

        content_type = None
        for candidate in ("posts", "pages"):
            existing = await _wordpress_request(
                client, site, f"/wp/v2/{candidate}/{data.post_id}",
                params={"context": "edit"}, auth=auth,
            )
            if existing.status_code == 200:
                content_type = candidate
                break
        if content_type is None:
            raise HTTPException(status_code=404, detail=f"WordPress content ID {data.post_id} could not be loaded as a post or page.")

        updated = await _wordpress_request(
            client, site, f"/wp/v2/{content_type}/{data.post_id}",
            method="POST",
            json_body={"title": data.title, "content": data.content_html, "status": data.status},
            auth=auth,
        )
        if updated.status_code >= 400:
            try:
                detail = updated.json().get("message", updated.text)
            except Exception:
                detail = updated.text
            raise HTTPException(status_code=502, detail=f"WordPress rejected the optimized content: {detail}")

        seo_applied = False
        bridge = await _wordpress_request(
            client, site, "/boost-rankers/v1/seo-meta/status", auth=auth,
        )
        if bridge.status_code == 200 and bridge.json().get("yoast_active"):
            seo_response = await _wordpress_request(
                client, site, f"/boost-rankers/v1/seo-meta/{data.post_id}",
                method="POST",
                json_body={"seo_title": data.meta_title[:500], "meta_description": data.meta_description[:1000], "focus_keyphrase": data.focus_keyphrase[:500]},
                auth=auth,
            )
            if seo_response.status_code >= 400:
                try:
                    detail = seo_response.json().get("message", seo_response.text)
                except Exception:
                    detail = seo_response.text
                raise HTTPException(status_code=502, detail=f"WordPress SEO metadata could not be saved: {detail}")
            seo_applied = True

        return {
            "success": True,
            "message": "Optimized content applied to WordPress.",
            "wordpress": {
                "content_type": content_type[:-1],
                "post_id": data.post_id,
                "url": updated.json().get("link"),
                "seo_metadata_applied": seo_applied,
                "status": data.status,
            },
        }


