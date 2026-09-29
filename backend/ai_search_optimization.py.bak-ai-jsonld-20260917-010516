from __future__ import annotations

import asyncio
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
MAX_INTERNAL_LINKS = 6
GENERIC_ANCHORS = {"click here", "read more", "learn more", "here", "more", "this article"}


class AnalyzeRequest(BaseModel):
    url: HttpUrl
    focus_keyword: str = Field(default="", max_length=500)
    used_focus_keywords: list[str] = Field(default_factory=list, max_length=500)


class RewriteRequest(BaseModel):
    url: HttpUrl
    focus_keyword: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=3, max_length=500)
    content_html: str = Field(min_length=100, max_length=120000)
    meta_title: str = Field(default="", max_length=500)
    meta_description: str = Field(default="", max_length=1000)
    analysis: dict[str, Any] = Field(default_factory=dict)
    internal_link_candidates: list[dict[str, str]] = Field(default_factory=list, max_length=100)


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


def _focus_candidates(title: str, content: str, used: set[str]) -> list[str]:
    """Build deterministic title/content-derived keyword candidates without inventing topics."""
    stop = {
        "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "from",
        "how", "what", "why", "when", "where", "who", "which", "your", "our", "this", "that",
        "guide", "best", "ultimate", "complete", "tips", "checklist", "services", "service",
    }
    words = re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)?", title.lower())
    meaningful = [w for w in words if len(w) > 2 and w not in stop]
    content_norm = _normalize_phrase(content)
    candidates: list[tuple[float, str]] = []
    for n in (4, 3, 2):
        for i in range(max(0, len(meaningful) - n + 1)):
            phrase = " ".join(meaningful[i:i+n])
            norm = _normalize_phrase(phrase)
            if not norm or norm in used or len(norm) < 5:
                continue
            count = content_norm.count(norm)
            score = (count * 10) + n + (2 if i == 0 else 0)
            candidates.append((score, phrase))
    for n in (3, 2, 1):
        for i in range(max(0, len(meaningful) - n + 1)):
            phrase = " ".join(meaningful[i:i+n])
            norm = _normalize_phrase(phrase)
            if norm and norm not in used and len(norm) >= 5:
                candidates.append((content_norm.count(norm) * 10 + n, phrase))
    candidates.sort(key=lambda item: (-item[0], len(item[1])))
    return [phrase for _, phrase in candidates]


def _choose_focus_keyword(title: str, content: str, requested: str, used_keywords: list[str]) -> tuple[str, bool]:
    used = {_normalize_phrase(x) for x in used_keywords if _normalize_phrase(x)}
    requested = re.sub(r"\s+", " ", requested or "").strip()
    if requested and _normalize_phrase(requested) not in used:
        return requested, False
    for candidate in _focus_candidates(title, content, used):
        return candidate, bool(requested)
    fallback = " ".join(re.findall(r"[A-Za-z0-9]+", title)[:4]).strip() or "primary topic"
    return fallback, bool(requested and _normalize_phrase(requested) in used)


def _canonical_url(value: str, base: str | None = None) -> str:
    absolute = urljoin(base or "", str(value or "").strip())
    parsed = urlparse(absolute)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/') or '/'}"


def _sanitize_internal_links(html: str, source_url: str, candidates: list[dict[str, str]]) -> tuple[str, int, list[str]]:
    """Keep only links to verified WordPress candidates on the same site."""
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
            allowed[key] = {"url": urljoin(source_url, target), "title": title}
    soup = BeautifulSoup(html, "html.parser")
    applied = 0
    targets: list[str] = []
    for anchor in list(soup.find_all("a", href=True)):
        href = str(anchor.get("href") or "").strip()
        key = _canonical_url(href, source_url)
        target = allowed.get(key)
        anchor_text = _strip_html(anchor.get_text(" ", strip=True))
        parsed_href = urlparse(urljoin(source_url, href))
        source_host = urlparse(source_url).netloc.lower().lstrip("www.")
        href_host = parsed_href.netloc.lower().lstrip("www.")
        # Preserve external links; only sanitize AI-generated same-site links.
        if href_host and href_host != source_host:
            continue
        if not target or not anchor_text or _normalize_phrase(anchor_text) in GENERIC_ANCHORS:
            if not target:
                anchor.unwrap()
            else:
                anchor.unwrap()
            continue
        if applied >= MAX_INTERNAL_LINKS:
            anchor.unwrap()
            continue
        anchor["href"] = target["url"]
        applied += 1
        targets.append(target["title"])
    return str(soup), applied, targets


def _insert_contextual_links(html: str, source_url: str, candidates: list[dict[str, str]], already_linked: int) -> tuple[str, int, list[str]]:
    """Safely add missing contextual links only when candidate wording occurs in a paragraph."""
    if already_linked >= MAX_INTERNAL_LINKS or not candidates:
        return html, 0, []
    soup = BeautifulSoup(html, "html.parser")
    source_key = _canonical_url(source_url)
    added = 0
    targets: list[str] = []
    used_targets: set[str] = set()
    paragraphs = [p for p in soup.find_all(["p", "li"]) if p.find_parent(["a", "h1", "h2", "h3", "h4", "h5", "h6", "code", "pre", "script", "style"]) is None]
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
        title_words = [w for w in re.findall(r"[A-Za-z0-9]+", title) if len(w) > 2]
        phrases = [" ".join(title_words[:4]), " ".join(title_words[:3]), " ".join(title_words[:2])]
        found = False
        for para in paragraphs:
            text = para.get_text(" ", strip=True)
            phrase = next((x for x in phrases if x and re.search(r"\b" + re.escape(x) + r"\b", text, re.I)), None)
            if not phrase:
                continue
            for node in list(para.find_all(string=re.compile(re.escape(phrase), re.I))):
                parent = node.parent
                if parent and parent.name in {"a", "strong", "em"}:
                    continue
                match = re.search(re.escape(phrase), str(node), re.I)
                if not match:
                    continue
                before, matched, after = str(node)[:match.start()], str(node)[match.start():match.end()], str(node)[match.end():]
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


def _extract_page(html: str, url: str, focus_keyword: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True).strip() if soup.title else ""
    meta_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_description = str(meta_tag.get("content") or "").strip() if meta_tag else ""
    canonical = ""
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    if canonical_tag:
        canonical = str(canonical_tag.get("href") or "").strip()

    h1s = [re.sub(r"\s+", " ", x.get_text(" ", strip=True)).strip() for x in soup.find_all("h1")]
    headings = [
        {"level": int(tag.name[1]), "text": re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()}
        for tag in soup.find_all(["h2", "h3", "h4"])
        if tag.get_text(" ", strip=True)
    ]

    main = soup.find("main") or soup.find("article") or soup.body or soup
    content_html = str(main)[:120000]
    text = _strip_html(content_html)
    word_count = _word_count(text)
    first_200 = " ".join(text.split()[:200])

    schema_types: list[str] = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = script.string or script.get_text()
        try:
            data = json.loads(raw)
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if not isinstance(item, dict):
                continue
            typ = item.get("@type")
            if isinstance(typ, list):
                schema_types.extend(str(x) for x in typ)
            elif typ:
                schema_types.append(str(typ))
            graph = item.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)

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
        h["text"] for h in headings
        if re.search(r"\b(what|why|how|when|where|who|which|can|does|is|are)\b", h["text"], re.I)
    ]
    author_present = bool(
        soup.find("meta", attrs={"name": re.compile("^author$", re.I)})
        or soup.find(attrs={"rel": "author"})
        or soup.find(class_=re.compile("author", re.I))
    )
    date_present = bool(
        soup.find("time")
        or soup.find("meta", attrs={"property": re.compile("article:published_time", re.I)})
    )

    kw = focus_keyword.strip()
    title_score = 100 if 30 <= len(title) <= 65 else 70 if title else 0
    meta_score = 100 if 120 <= len(meta_description) <= 165 else 70 if meta_description else 0
    h1_score = 100 if len(h1s) == 1 else 50 if h1s else 0
    content_score = min(100, round(word_count / 18))
    answer_score = min(100, len(answer_headings) * 20 + (20 if re.search(r"\b(is|are|means|refers to|typically)\b", first_200, re.I) else 0))
    entity_score = min(100, len(set(schema_types)) * 20 + (15 if author_present else 0) + (10 if date_present else 0))

    checks = [
        {"key": "title", "label": "Title tag", "score": title_score, "detail": f"{len(title)} characters" if title else "Missing title tag"},
        {"key": "meta_description", "label": "Meta description", "score": meta_score, "detail": f"{len(meta_description)} characters" if meta_description else "Missing meta description"},
        {"key": "h1", "label": "H1 structure", "score": h1_score, "detail": f"{len(h1s)} H1 tag(s) detected"},
        {"key": "content_depth", "label": "Content depth", "score": content_score, "detail": f"{word_count:,} words"},
        {"key": "answer_engine", "label": "Answer-engine structure", "score": answer_score, "detail": f"{len(answer_headings)} question-style heading(s)"},
        {"key": "entity", "label": "Entity/trust signals", "score": entity_score, "detail": f"{len(set(schema_types))} JSON-LD type(s), author={'yes' if author_present else 'no'}, date={'yes' if date_present else 'no'}"},
        {"key": "internal_links", "label": "Internal linking", "score": min(100, internal_links * 15), "detail": f"{internal_links} internal link(s)"},
    ]
    if kw:
        checks.extend([
            {"key": "keyword_title", "label": "Focus keyword in title", "score": 100 if _keyword_count(title, kw) else 0, "detail": "Present" if _keyword_count(title, kw) else "Missing"},
            {"key": "keyword_h1", "label": "Focus keyword in H1", "score": 100 if any(_keyword_count(h, kw) for h in h1s) else 0, "detail": "Present" if any(_keyword_count(h, kw) for h in h1s) else "Missing"},
            {"key": "keyword_intro", "label": "Focus keyword in introduction", "score": 100 if _keyword_count(first_200, kw) else 0, "detail": "Present" if _keyword_count(first_200, kw) else "Missing"},
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
        "schema_types": sorted(set(schema_types)),
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
    return response.text[:MAX_CONTENT_CHARS * 4]


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
    used_for_prompt = used_keywords[:250]
    system = """You are a senior SEO and answer-engine optimization consultant. Analyze only supplied page evidence. Never claim that a page is cited by ChatGPT, Perplexity, Gemini, Google AI Overviews, or another AI engine unless evidence proves it. Never invent traffic, rankings, citations, entities, schema, competitor data, or search-volume data. Separate measured HTML facts from recommendations. If no focus keyword is supplied, recommend one concise topic phrase derived only from the page title/content. It must not duplicate any focus keyword in the supplied used-keyword list. Also suggest a compelling, accurate title that improves click appeal without clickbait. Return only JSON."""
    prompt = f"""
Page: {url}
Focus keyword: {data.focus_keyword or '(automatic selection required)'}
Already-used focus keywords (do not reuse): {json.dumps(used_for_prompt, ensure_ascii=False)}

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
    requested_keyword = data.focus_keyword.strip()
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
    if conflict:
        ai.setdefault("quick_wins", []).insert(0, f"The requested focus keyword was already used elsewhere, so an unused title-derived keyword was selected automatically: {chosen_keyword}.")
    for key in ("ai_search_score", "content_quality", "answer_engine_readiness", "entity_readiness", "semantic_coverage"):
        try:
            ai[key] = max(0, min(100, int(ai.get(key, measured["measured_score"]))))
        except (TypeError, ValueError):
            ai[key] = measured["measured_score"]
    return {"success": True, "measured": measured, "ai_analysis": ai}


@router.post("/rewrite")
async def rewrite_post(
    data: RewriteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = _require_company(current_user)
    api_key = _resolve_anthropic_api_key(db, company_id)
    source_text = _strip_html(data.content_html)
    if _word_count(source_text) < 100:
        raise HTTPException(status_code=400, detail="The post needs at least 100 readable words before AI rewriting.")
    system = """You are a senior SEO content editor specializing in AI search and answer-engine optimization. Rewrite the supplied article without inventing business facts, statistics, credentials, locations, prices, awards, reviews, or guarantees. Preserve supported facts. Improve clarity, topical completeness, passage-level answers, entity clarity, headings, internal coherence, and natural focus-keyword usage. Do not keyword-stuff. Return only valid JSON."""
    prompt = f"""
Original URL: {data.url}
Current title: {data.title}
Focus keyword: {data.focus_keyword}
Current meta title: {data.meta_title}
Current meta description: {data.meta_description}

Existing analysis:
{json.dumps(data.analysis, indent=2)}

Original article:
{source_text[:28000]}

Verified internal-link candidates from the connected WordPress site:
{json.dumps(data.internal_link_candidates[:100], ensure_ascii=False, indent=2)}

Return ONLY:
{{
  "title": "",
  "focus_keyword": "{data.focus_keyword}",
  "meta_title": "",
  "meta_description": "",
  "article_html": "",
  "change_summary": [],
  "focus_keyword_usage": {{"title": true, "first_paragraph": true, "headings": true, "body": true, "natural_usage": true}},
  "internal_links_applied": 0
}}

Rules:
- Keep the focus keyword exactly as supplied: {data.focus_keyword}
- Use it naturally in the title/H1, opening section, one relevant subheading where natural, and body.
- Never force it into every heading or sentence.
- Replace the current title with a high-engagement, specific, benefit-led title that accurately matches the article intent. Do not use clickbait.
- Meta title should be concise, compelling, accurate, and contain the exact focus keyword naturally.
- Meta description should be approximately 140-160 characters, accurate, and contain the exact focus keyword naturally.
- Produce clean WordPress-compatible HTML using h2/h3, p, ul/ol, and strong where useful.
- Add up to {MAX_INTERNAL_LINKS} contextual internal links ONLY to the verified WordPress candidates supplied above. Never invent URLs, never link to the current page, never use generic anchors, and never place links inside headings, existing links, code, pre, scripts, or styles.
- If a candidate is not contextually relevant, do not force a link.
- Do not output markdown.
- Do not invent unsupported facts.
"""
    rewrite = await _claude_json(system, prompt, api_key=api_key, max_tokens=10000)
    rewrite["focus_keyword"] = data.focus_keyword
    article_html = str(rewrite.get("article_html") or "")
    article_html, verified_count, linked_targets = _sanitize_internal_links(article_html, str(data.url), data.internal_link_candidates)
    article_html, inserted_count, inserted_targets = _insert_contextual_links(
        article_html, str(data.url), data.internal_link_candidates, verified_count
    )
    rewrite["article_html"] = article_html
    rewrite["internal_links_applied"] = verified_count + inserted_count
    rewrite["internal_link_targets"] = (linked_targets + inserted_targets)[:MAX_INTERNAL_LINKS]
    if rewrite["internal_links_applied"]:
        rewrite.setdefault("change_summary", []).append(
            f"Added {rewrite['internal_links_applied']} contextual internal link(s) using verified WordPress content."
        )
    return {"success": True, "rewrite": rewrite}


@router.post("/wordpress/content")
async def wordpress_content(data: WordPressCredentialsRequest, current_user: User = Depends(get_current_user)):
    _require_company(current_user)
    site = _clean_url(str(data.wordpress_site))
    auth = (data.wordpress_username.strip(), data.wordpress_application_password.strip())
    async with httpx.AsyncClient(timeout=WP_TIMEOUT, follow_redirects=True) as client:
        me = await client.get(f"{site}/wp-json/wp/v2/users/me", params={"context": "edit"}, auth=auth)
        if me.status_code >= 400:
            raise HTTPException(status_code=401, detail="WordPress authentication failed. Use a WordPress Application Password.")
        items: list[dict[str, Any]] = []
        for content_type in ("posts", "pages"):
            response = await client.get(
                f"{site}/wp-json/wp/v2/{content_type}",
                params={"per_page": 50, "page": 1, "context": "edit", "orderby": "modified", "order": "desc", "_fields": "id,link,title,status,modified,content,excerpt"},
                auth=auth,
            )
            if response.status_code >= 400:
                continue
            try:
                rows = response.json()
            except Exception:
                continue
            if not isinstance(rows, list):
                continue
            for row in rows:
                title = str((row.get("title") or {}).get("rendered") or "").strip()
                if not title:
                    continue
                items.append({
                    "id": int(row["id"]),
                    "type": "post" if content_type == "posts" else "page",
                    "title": title,
                    "url": str(row.get("link") or ""),
                    "status": str(row.get("status") or ""),
                    "modified": str(row.get("modified") or ""),
                    "content_html": str((row.get("content") or {}).get("rendered") or ""),
                    "excerpt": str((row.get("excerpt") or {}).get("rendered") or ""),
                    "focus_keyword": "",
                })

        # Read existing focus keyphrases only when the verified SEO Bridge is available.
        # Fail-soft so loading WordPress content remains usable if the bridge is absent.
        bridge = await client.get(f"{site}/wp-json/boost-rankers/v1/seo-meta/status", auth=auth)
        if bridge.status_code == 200:
            semaphore = asyncio.Semaphore(10)

            async def load_focus(item: dict[str, Any]) -> None:
                async with semaphore:
                    try:
                        meta = await client.get(
                            f"{site}/wp-json/boost-rankers/v1/seo-meta/{int(item['id'])}",
                            auth=auth,
                        )
                        if meta.status_code >= 400:
                            return
                        payload = meta.json()
                        value = payload.get("focus_keyword") or payload.get("focuskw") or payload.get("_yoast_wpseo_focuskw")
                        if isinstance(value, str):
                            item["focus_keyword"] = " ".join(value.split())
                    except Exception:
                        return

            await asyncio.gather(*(load_focus(item) for item in items))

        return {"success": True, "items": items}


@router.post("/wordpress/apply")
async def apply_to_wordpress(data: WordPressApplyRequest, current_user: User = Depends(get_current_user)):
    _require_company(current_user)
    site = _clean_url(str(data.wordpress_site))
    auth = (data.wordpress_username.strip(), data.wordpress_application_password.strip())
    async with httpx.AsyncClient(timeout=WP_TIMEOUT, follow_redirects=True) as client:
        me = await client.get(f"{site}/wp-json/wp/v2/users/me", params={"context": "edit"}, auth=auth)
        if me.status_code >= 400:
            raise HTTPException(status_code=401, detail="WordPress authentication failed. Use a WordPress Application Password.")

        content_type = None
        for candidate in ("posts", "pages"):
            existing = await client.get(f"{site}/wp-json/wp/v2/{candidate}/{data.post_id}", params={"context": "edit"}, auth=auth)
            if existing.status_code == 200:
                content_type = candidate
                break
        if content_type is None:
            raise HTTPException(status_code=404, detail=f"WordPress content ID {data.post_id} could not be loaded as a post or page.")

        updated = await client.post(
            f"{site}/wp-json/wp/v2/{content_type}/{data.post_id}",
            json={"title": data.title, "content": data.content_html, "status": data.status},
            auth=auth,
        )
        if updated.status_code >= 400:
            try:
                detail = updated.json().get("message", updated.text)
            except Exception:
                detail = updated.text
            raise HTTPException(status_code=502, detail=f"WordPress rejected the optimized content: {detail}")

        seo_applied = False
        bridge = await client.get(f"{site}/wp-json/boost-rankers/v1/seo-meta/status", auth=auth)
        if bridge.status_code == 200 and bridge.json().get("yoast_active"):
            seo_response = await client.post(
                f"{site}/wp-json/boost-rankers/v1/seo-meta/{data.post_id}",
                json={"seo_title": data.meta_title[:500], "meta_description": data.meta_description[:1000], "focus_keyphrase": data.focus_keyphrase[:500]},
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
