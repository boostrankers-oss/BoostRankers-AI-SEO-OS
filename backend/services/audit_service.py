from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, AsyncGenerator
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic, AuthenticationError, RateLimitError
from sqlalchemy.orm import Session

from config import settings
from models.audit import Audit, AuditStatus
from models.company import Company
from models.user import User
from services.secret_service import decrypt_secret

logger = logging.getLogger(__name__)


class _PageParser(HTMLParser):
    """Small dependency-free HTML extractor for SEO crawling."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.lang = ""
        self.robots = ""
        self.h1: list[str] = []
        self.h2: list[str] = []
        self.h3: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.schema_types: list[str] = []
        self.og: dict[str, str] = {}
        self.twitter: dict[str, str] = {}
        self._tag_stack: list[str] = []
        self._capture: str | None = None
        self._capture_buf: list[str] = []
        self._schema_capture = False
        self._schema_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        a = {str(k).lower(): (v or "") for k, v in attrs}
        self._tag_stack.append(tag)
        if tag == "html":
            self.lang = a.get("lang", "").strip()
        if tag == "title":
            self._capture = "title"
            self._capture_buf = []
        elif tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            content = a.get("content", "").strip()
            if name == "description":
                self.description = content
            elif name in {"robots", "googlebot"}:
                self.robots = content
            elif name.startswith("og:"):
                self.og[name] = content
            elif name.startswith("twitter:"):
                self.twitter[name] = content
        elif tag == "link":
            rel = a.get("rel", "").lower().split()
            href = a.get("href", "").strip()
            if "canonical" in rel and href:
                self.canonical = href
        elif tag in {"h1", "h2", "h3"}:
            self._capture = tag
            self._capture_buf = []
        elif tag == "a":
            href = a.get("href", "").strip()
            if href:
                self.links.append({
                    "href": href,
                    "rel": a.get("rel", ""),
                    "text": "",
                })
                self._capture = "a"
                self._capture_buf = []
        elif tag == "img":
            self.images.append({"src": a.get("src", ""), "alt": a.get("alt", "")})
        elif tag == "script" and "application/ld+json" in a.get("type", "").lower():
            self._schema_capture = True
            self._schema_buf = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._capture == tag:
            value = " ".join("".join(self._capture_buf).split())
            if tag == "title":
                self.title = value
            elif tag == "h1":
                self.h1.append(value)
            elif tag == "h2":
                self.h2.append(value)
            elif tag == "h3":
                self.h3.append(value)
            elif tag == "a" and self.links:
                self.links[-1]["text"] = value
            self._capture = None
            self._capture_buf = []
        if tag == "script" and self._schema_capture:
            raw = "".join(self._schema_buf).strip()
            self._schema_capture = False
            self._schema_buf = []
            if raw:
                try:
                    data = json.loads(raw)
                    self._collect_schema_types(data)
                except Exception:
                    self.schema_types.append("Invalid JSON-LD")
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._capture_buf.append(data)
        elif not self._schema_capture:
            cleaned = " ".join(data.split())
            if cleaned:
                self.text_parts.append(cleaned)
        if self._schema_capture:
            self._schema_buf.append(data)

    def _collect_schema_types(self, value: Any) -> None:
        if isinstance(value, dict):
            t = value.get("@type")
            if isinstance(t, str):
                self.schema_types.append(t)
            elif isinstance(t, list):
                self.schema_types.extend(str(x) for x in t)
            for child in value.values():
                if isinstance(child, (dict, list)):
                    self._collect_schema_types(child)
        elif isinstance(value, list):
            for child in value:
                self._collect_schema_types(child)


class AuditService:
    """Real website crawler + sequential AI SEO audit orchestrator.

    This service intentionally keeps the existing /api/audits/run endpoint and
    database model. The crawler runs first and its measured evidence is then
    supplied to each specialist agent. No synthetic crawl statistics are used.
    """

    MAX_PAGES = 500
    REQUEST_TIMEOUT = 20.0
    MAX_HTML_BYTES = 5_000_000

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _sse(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, default=str)}\n\n"

    def _safe_commit(self) -> None:
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _get_api_key(company: Company) -> str | None:
        encrypted = getattr(company, "anthropic_api_key_encrypted", None)
        if encrypted:
            try:
                value = decrypt_secret(str(encrypted).strip()).strip()
                if value:
                    return value
            except (ValueError, TypeError):
                logger.exception("Could not decrypt company Anthropic API key")
                return None
        value = getattr(settings, "ANTHROPIC_API_KEY", None)
        return str(value).strip() if value else None

    @staticmethod
    def _get_model_name() -> str:
        value = getattr(settings, "ANTHROPIC_MODEL", None)
        return str(value).strip() if value else "claude-sonnet-4-6"

    @staticmethod
    def _classify_anthropic_error(exc: Exception) -> tuple[str, str, bool]:
        if isinstance(exc, AuthenticationError):
            return "invalid_api_key", "Anthropic rejected the API key. Please update it in Settings.", False
        if isinstance(exc, RateLimitError):
            return "rate_limit_or_quota", "Anthropic usage quota or rate limit was reached. Check billing and try again.", True
        if isinstance(exc, APIConnectionError):
            return "provider_connection_error", "Could not connect to Anthropic. Check the server connection and try again.", True
        if isinstance(exc, APIStatusError):
            code = getattr(exc, "status_code", None)
            body = getattr(exc, "body", None)
            message = str(exc)
            if isinstance(body, dict) and isinstance(body.get("error"), dict):
                message = str(body["error"].get("message", message))
            low = message.lower()
            if code == 402 or "credit balance" in low or "billing" in low:
                return "billing_required", "Anthropic billing or credits are required. Please check your Anthropic plan.", True
            if code == 403:
                return "provider_forbidden", "The Anthropic account or key is not permitted to make this request.", False
            if code == 429:
                return "rate_limit_or_quota", "Anthropic rate limit or quota reached. Try again later.", True
            if code and code >= 500:
                return "provider_server_error", "Anthropic is temporarily unavailable. Try again shortly.", True
            return "provider_error", f"Anthropic error: {message}", True
        return "provider_error", f"Anthropic error: {exc}", True

    @staticmethod
    def _agents() -> list[dict[str, str]]:
        return [
            {"name": "Technical SEO Agent", "description": "HTTP status, crawlability, indexability, canonicals, robots and sitemap", "prompt": "Analyze only technical evidence from the crawl. Check HTTP status, redirects, indexability, canonicals, robots.txt, sitemap, crawl errors and page metadata. Do not invent facts."},
            {"name": "Content SEO Agent", "description": "Titles, meta descriptions, headings, content depth and duplicates", "prompt": "Analyze measured titles, descriptions, headings, word counts, duplicate hashes and page content patterns. Give actionable findings tied to measured URLs/counts."},
            {"name": "Local SEO Agent", "description": "Local relevance and on-site trust signals", "prompt": "Analyze only what the crawl can prove about local SEO: location terms, contact/about pages, Organization/LocalBusiness schema and local landing-page signals. Explicitly say when off-site GBP/citation data was not crawled."},
            {"name": "Schema Agent", "description": "JSON-LD and structured-data coverage", "prompt": "Analyze JSON-LD schema types and invalid JSON-LD observations from the crawl. Identify missing or inconsistent structured-data opportunities without claiming Google validation results."},
            {"name": "EEAT Agent", "description": "Experience, expertise, authority and trust signals", "prompt": "Analyze crawl evidence for About, Contact, author, policy, credentials, references and organization/entity signals. Do not invent credentials or external authority."},
            {"name": "Internal Linking Agent", "description": "Internal graph, orphan pages, anchors and click depth", "prompt": "Analyze the measured internal-link graph. Identify orphan pages, pages with few inbound links, pages with excessive outbound links, broken internal links, anchor-text patterns and crawl depth."},
            {"name": "Competitor Agent", "description": "Competitive opportunities supported by site evidence", "prompt": "Use only the site's own crawl evidence. Do not fabricate competitor rankings, backlink gaps or SERP positions. Explain which competitive analysis requires external data."},
            {"name": "Backlink Agent", "description": "Backlink profile readiness and limitations", "prompt": "Do not pretend a site crawl measures backlinks. Review only internal evidence relevant to link acquisition readiness and clearly state that external backlink metrics require a backlink provider or GSC data."},
            {"name": "AI Search Agent", "description": "Entity, answerability and machine-readable content", "prompt": "Analyze entity/schema coverage, headings, concise answer sections, page semantics, organization information and crawlable content for AI-search readiness."},
            {"name": "Reporting Agent", "description": "Executive summary and prioritized remediation plan", "prompt": "Compile the measured crawl evidence and specialist results into a concise executive summary. Prioritize issues by impact and effort. Never report zero when the crawler measured a non-zero value."},
        ]

    @staticmethod
    def _normalize_url(url: str, base: str | None = None) -> str | None:
        try:
            absolute = urljoin(base or "", url.strip())
            absolute, _ = urldefrag(absolute)
            p = urlparse(absolute)
            if p.scheme not in {"http", "https"} or not p.netloc:
                return None
            path = p.path or "/"
            return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", p.query, ""))
        except Exception:
            return None

    @staticmethod
    def _same_domain(url: str, root: str) -> bool:
        return urlparse(url).netloc.lower().removeprefix("www.") == urlparse(root).netloc.lower().removeprefix("www.")

    @staticmethod
    def _xml_urls(body: str) -> tuple[list[str], list[str]]:
        urls: list[str] = []
        sitemaps: list[str] = []
        try:
            root = ET.fromstring(body)
            tag = root.tag.lower()
            if tag.endswith("sitemapindex"):
                for loc in root.iter():
                    if loc.tag.lower().endswith("loc") and loc.text:
                        sitemaps.append(loc.text.strip())
            else:
                for loc in root.iter():
                    if loc.tag.lower().endswith("loc") and loc.text:
                        urls.append(loc.text.strip())
        except ET.ParseError:
            urls.extend(re.findall(r"<loc>\s*(.*?)\s*</loc>", body, re.I | re.S))
        return urls, sitemaps

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> tuple[httpx.Response | None, float, str | None]:
        started = time.perf_counter()
        try:
            response = await client.get(url, follow_redirects=True, headers={"User-Agent": "BoostRankersAISEOOS/1.0 (+SEO audit crawler)"})
            elapsed = (time.perf_counter() - started) * 1000
            return response, elapsed, None
        except httpx.HTTPError as exc:
            elapsed = (time.perf_counter() - started) * 1000
            return None, elapsed, str(exc)

    async def _discover_sitemap(self, client: httpx.AsyncClient, root: str, robots_body: str | None) -> tuple[list[str], str | None, bool]:
        candidates: list[str] = []
        if robots_body:
            for line in robots_body.splitlines():
                if line.lower().startswith("sitemap:"):
                    value = line.split(":", 1)[1].strip()
                    if value:
                        candidates.append(value)
        candidates += [urljoin(root, "/sitemap.xml"), urljoin(root, "/sitemap_index.xml")]
        seen: set[str] = set()
        found_url: str | None = None
        discovered: list[str] = []
        queue = deque(candidates)
        while queue and len(seen) < 20:
            candidate = self._normalize_url(queue.popleft())
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            response, _, _ = await self._fetch(client, candidate)
            if not response or response.status_code >= 400:
                continue
            content_type = response.headers.get("content-type", "")
            if "xml" not in content_type and not candidate.endswith((".xml", ".xml.gz")):
                continue
            found_url = found_url or candidate
            urls, indexes = self._xml_urls(response.text[:2_000_000])
            discovered.extend(self._normalize_url(x) for x in urls if self._normalize_url(x))
            queue.extend(indexes)
        return list(dict.fromkeys(discovered)), found_url, bool(found_url)

    async def _crawl(self, root: str, emit) -> dict[str, Any]:
        root = self._normalize_url(root) or root
        parsed_root = urlparse(root)
        origin = f"{parsed_root.scheme}://{parsed_root.netloc}"
        robots_url = origin + "/robots.txt"
        started = time.perf_counter()
        pages: dict[str, dict[str, Any]] = {}
        discovered_order: list[str] = []
        queue = deque([root])
        queued: set[str] = {root}
        inbound: defaultdict[str, set[str]] = defaultdict(set)
        all_internal_targets: set[str] = set()
        external_links = 0
        broken_external = 0
        broken_internal = 0
        robots_found = False
        robots_valid = False
        robots_body = ""
        sitemap_urls: list[str] = []
        sitemap_url: str | None = None
        sitemap_found = False
        sitemap_valid = False

        limits = httpx.Limits(max_connections=8, max_keepalive_connections=4)
        async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT, limits=limits, max_redirects=8) as client:
            robots_response, robots_ms, robots_error = await self._fetch(client, robots_url)
            if robots_response and robots_response.status_code == 200:
                robots_found = True
                robots_body = robots_response.text[:1_000_000]
                rp = RobotFileParser()
                try:
                    rp.parse(robots_body.splitlines())
                    robots_valid = True
                except Exception:
                    robots_valid = False
            await emit({"type": "crawl_stage", "stage": "robots", "message": f"robots.txt: {'found' if robots_found else 'not found'}", "progress": 3})

            sitemap_urls, sitemap_url, sitemap_found = await self._discover_sitemap(client, root, robots_body or None)
            sitemap_valid = bool(sitemap_found and sitemap_urls)
            for u in sitemap_urls:
                if self._same_domain(u, root) and u not in queued and len(queued) < self.MAX_PAGES * 2:
                    queue.append(u)
                    queued.add(u)
            await emit({"type": "crawl_stage", "stage": "sitemap", "message": f"Sitemap: {'found' if sitemap_found else 'not found'} ({len(sitemap_urls)} URLs discovered)", "progress": 7})

            while queue and len(pages) < self.MAX_PAGES:
                current = queue.popleft()
                if current in pages:
                    continue
                if not self._same_domain(current, root):
                    continue
                if robots_found:
                    rp = RobotFileParser()
                    try:
                        rp.set_url(robots_url)
                        rp.parse(robots_body.splitlines())
                        if not rp.can_fetch("BoostRankersAISEOOS", current):
                            pages[current] = {"url": current, "status": 0, "blocked_by_robots": True, "links": [], "text": "", "word_count": 0, "schema_types": []}
                            continue
                    except Exception:
                        pass

                response, response_ms, fetch_error = await self._fetch(client, current)
                item: dict[str, Any] = {
                    "url": current,
                    "status": response.status_code if response else 0,
                    "response_ms": round(response_ms, 2),
                    "error": fetch_error,
                    "final_url": current,
                    "redirects": [],
                    "content_type": "",
                    "title": "",
                    "description": "",
                    "canonical": "",
                    "robots": "",
                    "lang": "",
                    "h1": [],
                    "h2": [],
                    "h3": [],
                    "word_count": 0,
                    "links": [],
                    "images": [],
                    "schema_types": [],
                    "og": {},
                    "twitter": {},
                    "hash": "",
                }
                if response:
                    item["final_url"] = str(response.url)
                    item["redirects"] = [str(h.url) for h in response.history]
                    item["content_type"] = response.headers.get("content-type", "")
                    body = response.content[: self.MAX_HTML_BYTES]
                    if "text/html" in item["content_type"].lower() or body.lstrip().startswith(b"<"):
                        text = body.decode(response.encoding or "utf-8", errors="ignore")
                        parser = _PageParser()
                        parser.feed(text)
                        item.update({
                            "title": parser.title,
                            "description": parser.description,
                            "canonical": self._normalize_url(parser.canonical, current) if parser.canonical else "",
                            "robots": parser.robots,
                            "lang": parser.lang,
                            "h1": parser.h1,
                            "h2": parser.h2,
                            "h3": parser.h3,
                            "word_count": len(re.findall(r"\b[\w'-]+\b", " ".join(parser.text_parts))),
                            "images": parser.images,
                            "schema_types": sorted(set(parser.schema_types)),
                            "og": parser.og,
                            "twitter": parser.twitter,
                        })
                        text_for_hash = " ".join(parser.text_parts).lower()
                        item["hash"] = hashlib.sha256(text_for_hash.encode("utf-8", errors="ignore")).hexdigest() if text_for_hash else ""
                        for link in parser.links:
                            target = self._normalize_url(link.get("href", ""), current)
                            if not target:
                                continue
                            link["url"] = target
                            item["links"].append(link)
                            if self._same_domain(target, root):
                                all_internal_targets.add(target)
                                inbound[target].add(current)
                                if target not in queued and target not in pages and len(queued) < self.MAX_PAGES * 2:
                                    queue.append(target)
                                    queued.add(target)
                            else:
                                external_links += 1
                pages[current] = item
                discovered_order.append(current)
                crawl_pct = 8 + int((len(pages) / self.MAX_PAGES) * 55)
                await emit({
                    "type": "crawl_progress",
                    "stage": "crawl",
                    "url": current,
                    "pages_crawled": len(pages),
                    "pages_discovered": len(queued),
                    "progress": min(63, crawl_pct),
                    "message": f"Crawled {len(pages)} page(s) — {current}",
                })

        # Validate internal targets after discovery; a URL is broken if its fetched status is 4xx/5xx.
        for source, page in pages.items():
            for link in page.get("links", []):
                target = link.get("url")
                if not target or not self._same_domain(target, root):
                    continue
                target_page = pages.get(target)
                if target_page and (target_page.get("status", 0) >= 400 or target_page.get("status", 0) == 0):
                    broken_internal += 1
        for target in all_internal_targets:
            if target not in pages and len(pages) >= self.MAX_PAGES:
                continue

        successful = sum(1 for p in pages.values() if 200 <= int(p.get("status", 0)) < 400)
        failed = sum(1 for p in pages.values() if int(p.get("status", 0)) >= 400 or int(p.get("status", 0)) == 0)
        redirects = sum(1 for p in pages.values() if p.get("redirects"))
        internal_links = sum(sum(1 for l in p.get("links", []) if self._same_domain(l.get("url", ""), root)) for p in pages.values())
        external_links = sum(sum(1 for l in p.get("links", []) if l.get("url") and not self._same_domain(l.get("url", ""), root)) for p in pages.values())
        duplicate_groups: dict[str, list[str]] = defaultdict(list)
        title_groups: dict[str, list[str]] = defaultdict(list)
        for u, p in pages.items():
            if p.get("hash"):
                duplicate_groups[p["hash"]].append(u)
            if p.get("title"):
                title_groups[p["title"].strip().lower()].append(u)
        duplicate_pages = sum(max(0, len(v) - 1) for v in duplicate_groups.values())
        duplicate_titles = sum(max(0, len(v) - 1) for v in title_groups.values())
        orphan_pages = [u for u, p in pages.items() if u != root and not inbound.get(u)]
        noindex_pages = [u for u, p in pages.items() if "noindex" in p.get("robots", "").lower()]
        missing_titles = [u for u, p in pages.items() if not p.get("title")]
        missing_descriptions = [u for u, p in pages.items() if not p.get("description")]
        missing_h1 = [u for u, p in pages.items() if not p.get("h1")]
        multiple_h1 = [u for u, p in pages.items() if len(p.get("h1", [])) > 1]
        missing_canonical = [u for u, p in pages.items() if not p.get("canonical") and int(p.get("status", 0)) < 400]
        schema_pages = [u for u, p in pages.items() if p.get("schema_types")]
        schema_types = sorted(set(t for p in pages.values() for t in p.get("schema_types", [])))
        total_words = sum(int(p.get("word_count", 0)) for p in pages.values())
        response_times = [float(p.get("response_ms", 0)) for p in pages.values() if p.get("response_ms")]
        status_counts = Counter(str(p.get("status", 0)) for p in pages.values())
        depth: dict[str, int] = {root: 0}
        changed = True
        while changed:
            changed = False
            for source, p in pages.items():
                if source not in depth:
                    continue
                for link in p.get("links", []):
                    target = link.get("url")
                    if target in pages and target not in depth and self._same_domain(target, root):
                        depth[target] = depth[source] + 1
                        changed = True
        deep_pages = [u for u, d in depth.items() if d > 4]
        crawl_duration_ms = int((time.perf_counter() - started) * 1000)
        evidence_pages = []
        for u in list(pages)[:80]:
            p = pages[u]
            evidence_pages.append({
                "url": u,
                "status": p.get("status"),
                "response_ms": p.get("response_ms"),
                "title": p.get("title"),
                "description": p.get("description"),
                "h1": p.get("h1", [])[:3],
                "word_count": p.get("word_count", 0),
                "canonical": p.get("canonical"),
                "robots": p.get("robots"),
                "schema_types": p.get("schema_types", []),
                "internal_outbound": sum(1 for l in p.get("links", []) if l.get("url") and self._same_domain(l["url"], root)),
                "internal_inbound": len(inbound.get(u, set())),
                "depth": depth.get(u, -1),
            })
        return {
            "root": root,
            "pages": pages,
            "pages_discovered": len(queued),
            "pages_crawled": len(pages),
            "pages_successful": successful,
            "pages_failed": failed,
            "internal_links": internal_links,
            "external_links": external_links,
            "broken_internal_links": broken_internal,
            "broken_external_links": broken_external,
            "orphan_pages": orphan_pages[:100],
            "orphan_pages_count": len(orphan_pages),
            "deep_pages": deep_pages[:100],
            "noindex_pages": noindex_pages[:100],
            "missing_titles": missing_titles[:100],
            "missing_descriptions": missing_descriptions[:100],
            "missing_h1": missing_h1[:100],
            "multiple_h1": multiple_h1[:100],
            "missing_canonical": missing_canonical[:100],
            "duplicate_pages": duplicate_pages,
            "duplicate_titles": duplicate_titles,
            "schema_found": bool(schema_pages),
            "schema_pages": len(schema_pages),
            "schema_types": schema_types,
            "robots_found": robots_found,
            "robots_valid": robots_valid,
            "robots_url": robots_url,
            "sitemap_found": sitemap_found,
            "sitemap_valid": sitemap_valid,
            "sitemap_url": sitemap_url,
            "sitemap_urls": len(sitemap_urls),
            "total_words": total_words,
            "average_words": round(total_words / len(pages), 1) if pages else 0,
            "average_response_ms": round(sum(response_times) / len(response_times), 1) if response_times else 0,
            "status_counts": dict(status_counts),
            "redirects": redirects,
            "depth_average": round(sum(depth.values()) / len(depth), 2) if depth else 0,
            "max_depth": max(depth.values()) if depth else 0,
            "crawl_duration_ms": crawl_duration_ms,
            "evidence_pages": evidence_pages,
        }

    def _persist_crawl(self, audit: Audit, crawl: dict[str, Any]) -> None:
        """Persist measured crawl counters into existing Audit columns only."""
        mapping = {
            "pages_discovered": "pages_discovered", "pages_crawled": "pages_crawled", "pages_successful": "pages_successful",
            "pages_failed": "pages_failed", "internal_links": "internal_links", "external_links": "external_links",
            "broken_internal_links": "broken_internal_links", "broken_external_links": "broken_external_links",
            "orphan_pages_count": "orphan_pages_count", "schema_found": "schema_found", "robots_found": "robots_txt_found",
            "robots_valid": "robots_txt_valid", "sitemap_found": "sitemap_found", "sitemap_valid": "sitemap_valid",
            "duplicate_pages": "duplicate_pages", "duplicate_titles": "duplicate_titles", "total_words": "total_words",
            "average_words": "average_words_per_page", "average_response_ms": "average_response_time", "crawl_duration_ms": "crawl_duration_ms",
            "redirects": "redirects_found", "depth_average": "crawl_depth_average",
        }
        for source, target in mapping.items():
            if hasattr(audit, target):
                try:
                    setattr(audit, target, crawl.get(source, 0))
                except Exception:
                    logger.debug("Could not persist audit field %s", target)
        statuses = crawl.get("status_counts", {})
        for code in (200, 301, 302, 304, 400, 401, 403, 404, 410, 429, 500, 502, 503):
            field = f"status_{code}"
            if hasattr(audit, field):
                setattr(audit, field, int(statuses.get(str(code), 0)))
        if hasattr(audit, "status_other"):
            known = sum(int(statuses.get(str(c), 0)) for c in (200,301,302,304,400,401,403,404,410,429,500,502,503))
            setattr(audit, "status_other", max(0, len(crawl.get("pages", {})) - known))
        for source, field in (("missing_titles", "missing_titles"), ("missing_descriptions", "missing_meta_descriptions"), ("missing_h1", "missing_h1"), ("multiple_h1", "multiple_h1"), ("missing_canonical", "canonical_missing")):
            if hasattr(audit, field):
                setattr(audit, field, len(crawl.get(source, [])))
        for field, value in (("total_titles", len(crawl.get("pages", {}))), ("total_meta_descriptions", len(crawl.get("pages", {}))), ("pages_with_h1", len(crawl.get("pages", {})) - len(crawl.get("missing_h1", []))), ("indexable_pages", len(crawl.get("pages", {})) - len(crawl.get("noindex_pages", []))), ("noindex_pages", len(crawl.get("noindex_pages", []))), ("average_internal_links_per_page", crawl.get("internal_links", 0) / max(1, len(crawl.get("pages", {}))))):
            if hasattr(audit, field):
                setattr(audit, field, value)

    async def _check_anthropic_availability(self, client: AsyncAnthropic, model: str) -> tuple[bool, str, str | None, bool]:
        try:
            response = await client.messages.create(model=model, max_tokens=8, system="Reply with exactly OK.", messages=[{"role": "user", "content": "OK"}])
            return bool(response), "" if response else "Anthropic returned an empty response.", None if response else "provider_empty_response", not bool(response)
        except Exception as exc:
            code, message, retryable = self._classify_anthropic_error(exc)
            return False, message, code, retryable

    async def _run_agent(
        self,
        client: AsyncAnthropic,
        model: str,
        agent: dict[str, str],
        url: str,
        crawl: dict[str, Any],
        previous: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Run one specialist agent with defensive Claude JSON handling.

        The audit must never assume that an LLM response is valid JSON.
        Claude can return fenced JSON, surrounding text, or a truncated
        response when the output-token limit is reached. This method treats
        provider truncation and malformed JSON as recoverable conditions and
        performs one controlled retry/repair before reporting an agent error.
        """

        # Do not send the entire previous result history back to Claude. It can
        # become unnecessarily large, especially for the Reporting Agent.
        previous_compact: list[dict[str, Any]] = []
        for item in previous[-8:]:
            if not isinstance(item, dict):
                continue
            previous_compact.append(
                {
                    "agent": str(item.get("agent", "")),
                    "score": item.get("score", 0),
                    "findings": [
                        {
                            "severity": str(f.get("severity", "info")),
                            "title": str(f.get("title", "Finding")),
                            "detail": str(f.get("detail", ""))[:500],
                        }
                        for f in item.get("findings", [])[:3]
                        if isinstance(f, dict)
                    ],
                }
            )

        evidence = {
            "website": url,
            "crawl": {k: v for k, v in crawl.items() if k not in {"pages"}},
            "pages_sample": crawl.get("evidence_pages", [])[:60],
            "previous_agent_results": previous_compact,
        }

        prompt = f"""Website SEO audit. You MUST use only the measured crawl evidence below.

SPECIALIST: {agent['name']}
TASK: {agent['prompt']}

MEASURED EVIDENCE:
{json.dumps(evidence, ensure_ascii=False, default=str)}

Return ONLY one valid JSON object. No Markdown. No code fences. No commentary.
Use exactly this shape:
{{"score": 0, "findings": [{{"severity":"critical|high|medium|low|info","title":"...","detail":"...","recommendation":"...","evidence":"..."}}]}}

Rules:
- Score must be an integer from 0 to 100.
- Return exactly 3 concise findings when evidence exists; otherwise return an empty findings array.
- Keep each title/detail/recommendation/evidence short.
- Never invent a metric, URL, backlink count, ranking, traffic value, or external data.
- If a requested metric cannot be measured by this crawl, explicitly say that it requires external data.
"""

        async def request_json(max_tokens: int) -> tuple[str, Any]:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=(
                    "You are a senior evidence-driven SEO auditor. "
                    "Output compact valid JSON only. Never fabricate measurements."
                ),
                messages=[{"role": "user", "content": prompt}],
            )

            parts: list[str] = []
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    text = getattr(block, "text", "")
                    if text:
                        parts.append(text)

            return "".join(parts).strip(), response

        def clean_json_text(value: str) -> str:
            text = str(value or "").strip()

            # Remove Markdown fences if a provider/model adds them anyway.
            fenced = re.search(
                r"```(?:json)?\s*(.*?)\s*```",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if fenced:
                text = fenced.group(1).strip()

            if text.lower().startswith("json\n"):
                text = text[5:].strip()

            # If Claude surrounds the object with a sentence, recover the
            # first complete JSON object without accepting arbitrary text.
            first = text.find("{")
            if first > 0:
                text = text[first:]

            return text.strip()

        def parse_json_object(value: str) -> dict[str, Any]:
            text = clean_json_text(value)
            if not text:
                raise ValueError("Anthropic returned an empty response.")

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                # JSONDecoder can recover a complete object when harmless
                # trailing text exists after it.
                decoder = json.JSONDecoder()
                parsed, _ = decoder.raw_decode(text)

            if not isinstance(parsed, dict):
                raise ValueError("Claude response JSON must be an object.")

            return parsed

        content, response = await request_json(3200)
        stop_reason = getattr(response, "stop_reason", None)

        # A max_tokens stop means the JSON may be physically incomplete.
        # Never feed truncated JSON to json.loads(); retry with a larger budget.
        if stop_reason == "max_tokens":
            logger.warning(
                "Claude output truncated for %s; retrying with larger budget.",
                agent["name"],
            )
            content, response = await request_json(6000)
            stop_reason = getattr(response, "stop_reason", None)

            if stop_reason == "max_tokens":
                raise RuntimeError(
                    f"Claude output remained truncated for {agent['name']} after retry."
                )

        if stop_reason == "refusal":
            raise RuntimeError(
                f"Claude refused to generate the {agent['name']} result."
            )

        try:
            parsed = parse_json_object(content)
        except (json.JSONDecodeError, TypeError, ValueError, RuntimeError) as parse_exc:
            logger.warning(
                "Invalid Claude JSON for %s; attempting one repair. Error: %s",
                agent["name"],
                parse_exc,
            )

            repair_prompt = f"""Repair the following malformed SEO audit response.
Return ONLY valid JSON with exactly this shape:
{{"score": 0, "findings": [{{"severity":"critical|high|medium|low|info","title":"...","detail":"...","recommendation":"...","evidence":"..."}}]}}
Do not add Markdown or explanation. Keep at most 3 concise findings.

Malformed response:
{content[:14000]}
"""

            repair_response = await client.messages.create(
                model=model,
                max_tokens=2400,
                system="You repair malformed JSON. Return JSON only.",
                messages=[{"role": "user", "content": repair_prompt}],
            )

            repair_parts: list[str] = []
            for block in repair_response.content:
                if getattr(block, "type", None) == "text":
                    text = getattr(block, "text", "")
                    if text:
                        repair_parts.append(text)

            repaired = "".join(repair_parts).strip()

            if getattr(repair_response, "stop_reason", None) == "max_tokens":
                raise RuntimeError(
                    f"Claude JSON repair was truncated for {agent['name']}."
                )

            parsed = parse_json_object(repaired)

        score = parsed.get("score", 50)
        try:
            score = int(float(score))
        except (TypeError, ValueError):
            score = 50
        score = max(0, min(100, score))

        findings = parsed.get("findings", [])
        if not isinstance(findings, list):
            findings = []

        normalized: list[dict[str, str]] = []
        for item in findings[:3]:
            if isinstance(item, dict):
                severity = str(item.get("severity", "info")).lower().strip()
                if severity not in {"critical", "high", "medium", "low", "info"}:
                    severity = "info"
                normalized.append(
                    {
                        "severity": severity,
                        "title": str(item.get("title", "Finding")).strip()[:300],
                        "detail": str(item.get("detail", "")).strip()[:1200],
                        "recommendation": str(item.get("recommendation", "")).strip()[:1200],
                        "evidence": str(item.get("evidence", "")).strip()[:1200],
                    }
                )

        return {
            "agent": agent["name"],
            "score": score,
            "findings": normalized,
        }

    async def run_audit(self, url: str, user: User, company: Company, request: Any = None) -> AsyncGenerator[str, None]:
        audit: Audit | None = None
        results: list[dict[str, Any]] = []
        agents = self._agents()
        total_agents = len(agents)
        if not url.startswith(("http://", "https://")):
            yield self._sse({"type": "error", "message": "Please enter a valid http:// or https:// website URL."})
            return
        try:
            ai_credits = int(getattr(company, "ai_credits", 0) or 0)
            if ai_credits <= 0:
                yield self._sse({"type": "billing_required", "source": "application", "message": "You do not have enough AI credits to run this audit.", "retryable": False})
                return
            api_key = self._get_api_key(company)
            if not api_key:
                yield self._sse({"type": "ai_provider_unavailable", "code": "missing_api_key", "message": "Anthropic AI is not configured. Add a valid API key in Settings.", "retryable": False})
                return
            model = self._get_model_name()
            client = AsyncAnthropic(api_key=api_key)
            ok, message, code, retryable = await self._check_anthropic_availability(client, model)
            if not ok:
                yield self._sse({"type": "ai_provider_unavailable", "code": code, "message": message, "retryable": retryable})
                return
            if request is not None and await request.is_disconnected():
                return

            company.ai_credits = ai_credits - 1
            self._safe_commit()
            audit = Audit(website=url, company_id=company.id, user_id=user.id, status=AuditStatus.RUNNING, started_at=datetime.now(timezone.utc), progress_percentage=0)
            self.db.add(audit)
            self._safe_commit()
            self.db.refresh(audit)
            yield self._sse({"type": "started", "audit_id": str(audit.id), "total_agents": total_agents, "completed_agents": 0, "progress": 0, "message": "Audit started. Real crawler is initializing."})

            async def emit(event: dict[str, Any]) -> None:
                # Placeholder callback; actual events are collected by queue below.
                await asyncio.sleep(0)

            # Use an async queue so crawl progress can be streamed while crawling.
            event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
            async def crawl_emit(event: dict[str, Any]) -> None:
                await event_queue.put(event)
            crawl_task = asyncio.create_task(self._crawl(url, crawl_emit))
            while not crawl_task.done():
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.25)
                    yield self._sse(event)
                except asyncio.TimeoutError:
                    if request is not None and await request.is_disconnected():
                        crawl_task.cancel()
                        return
            crawl = await crawl_task
            while not event_queue.empty():
                yield self._sse(await event_queue.get())

            self._persist_crawl(audit, crawl)
            audit.progress_percentage = 65
            audit.current_stage = "Website Crawler"
            audit.current_task = "Real crawl completed; specialist analysis starting"
            self._safe_commit()
            yield self._sse({
                "type": "crawl_complete", "progress": 65, "audit_id": str(audit.id),
                "metrics": {k: crawl[k] for k in ("pages_discovered","pages_crawled","pages_successful","internal_links","external_links","broken_internal_links","orphan_pages_count","sitemap_found","robots_found","schema_found","duplicate_pages")},
                "message": f"Real crawl complete: {crawl['pages_crawled']} page(s) analyzed.",
            })

            previous: list[dict[str, Any]] = []
            for idx, agent in enumerate(agents):
                if request is not None and await request.is_disconnected():
                    return
                start_progress = 65 + int((idx / total_agents) * 30)
                audit.current_stage = agent["name"]
                audit.current_task = agent["description"]
                audit.progress_percentage = start_progress
                self._safe_commit()
                yield self._sse({"type": "agent_start", "agent": agent["name"], "agent_index": idx, "total_agents": total_agents, "completed_agents": idx, "progress": start_progress, "description": agent["description"]})
                try:
                    result = await self._run_agent(client, model, agent, url, crawl, previous)
                    results.append(result)
                    previous.append(result)
                    end_progress = 65 + int(((idx + 1) / total_agents) * 30)
                    audit.progress_percentage = end_progress
                    audit.current_task = "Completed"
                    self._safe_commit()
                    for finding in result["findings"]:
                        yield self._sse({"type": "log", "agent": agent["name"], "message": f"[{finding['severity'].upper()}] {finding['title']}: {finding['detail']}"})
                    yield self._sse({"type": "agent_complete", "agent": agent["name"], "agent_index": idx, "total_agents": total_agents, "completed_agents": idx + 1, "progress": end_progress, "score": result["score"]})
                except AuthenticationError as exc:
                    code, msg, retry = self._classify_anthropic_error(exc)
                    audit.status = AuditStatus.FAILED
                    audit.error_message = msg
                    self._safe_commit()
                    yield self._sse({"type": "provider_error", "code": code, "agent": agent["name"], "message": msg, "retryable": retry, "audit_id": str(audit.id)})
                    return
                except (RateLimitError, APIConnectionError, APIStatusError) as exc:
                    code, msg, retry = self._classify_anthropic_error(exc)
                    audit.status = AuditStatus.FAILED
                    audit.error_message = msg
                    self._safe_commit()
                    yield self._sse({"type": "provider_error", "code": code, "agent": agent["name"], "message": msg, "retryable": retry, "audit_id": str(audit.id)})
                    return
                except Exception as exc:
                    logger.exception("Audit agent failed: %s", agent["name"])
                    result = {"agent": agent["name"], "score": 0, "findings": [{"severity":"critical","title":"Agent execution failed","detail":str(exc),"recommendation":"Review the server log and rerun the audit.","evidence":""}]}
                    results.append(result)
                    yield self._sse({"type": "agent_error", "agent": agent["name"], "message": str(exc), "progress": 65 + int(((idx + 1) / total_agents) * 30)})

            average_score = round(sum(float(r.get("score", 0)) for r in results) / max(1, len(results)), 2)
            audit.status = AuditStatus.COMPLETED
            audit.completed_at = datetime.now(timezone.utc)
            audit.progress_percentage = 100
            audit.overall_score = average_score if hasattr(audit, "overall_score") else average_score
            audit.current_stage = "Completed"
            audit.current_task = "Audit completed successfully"
            # duration_seconds is a computed read-only property on Audit.
            # completed_at + started_at are persisted; the model calculates
            # duration_seconds automatically. Never assign to the property.
            score_fields = {"Technical SEO Agent":"technical_score","Content SEO Agent":"content_score","Local SEO Agent":"local_seo_score","Schema Agent":"schema_score","EEAT Agent":"eeat_score","Backlink Agent":"backlink_score","AI Search Agent":"ai_search_score","Internal Linking Agent":"internal_linking_score"}
            for r in results:
                field = score_fields.get(r.get("agent"))
                if field and hasattr(audit, field):
                    setattr(audit, field, float(r.get("score", 0)))
            self._safe_commit()

            report_warning = None
            try:
                from services.report_service import ReportService
                ReportService(self.db).generate_report_from_audit(audit, results)
            except Exception as exc:
                logger.exception("Report generation failed for audit %s", audit.id)
                report_warning = f"Audit completed, but report generation failed: {exc}"
                yield self._sse({"type":"warning","message":report_warning})

            yield self._sse({"type":"complete","audit_id":str(audit.id),"completed_agents":total_agents,"total_agents":total_agents,"progress":100,"score":average_score,"crawl_metrics":{k:crawl[k] for k in ("pages_discovered","pages_crawled","pages_successful","internal_links","external_links","broken_internal_links","orphan_pages_count","sitemap_found","robots_found","schema_found","duplicate_pages")},"results":results,"report_warning":report_warning})
        except asyncio.CancelledError:
            if audit is not None:
                audit.status = AuditStatus.CANCELLED
                audit.current_task = "Audit cancelled"
                self._safe_commit()
            raise
        except Exception as exc:
            logger.exception("Unhandled audit streaming error")
            if audit is not None:
                audit.status = AuditStatus.FAILED
                audit.error_message = str(exc)
                audit.current_task = "Audit failed"
                try:
                    self._safe_commit()
                except Exception:
                    self.db.rollback()
            yield self._sse({"type":"error","message":f"Audit failed unexpectedly. Reason: {exc}","audit_id":str(audit.id) if audit else None})