from __future__ import annotations

import asyncio
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse, urldefrag

import httpx
from anthropic import (
    APIConnectionError,
    APIStatusError,
    AsyncAnthropic,
    AuthenticationError,
    RateLimitError,
)
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from config import settings
from models.company import Company
from models.internal_linking import InternalLinkingSuggestion
from services.secret_service import decrypt_secret


# ============================================================
# HTML PARSER
# ============================================================


class _PageParser(HTMLParser):
    """
    Lightweight HTML parser used to extract evidence for internal-linking
    decisions:
    - title
    - H1/H2/H3 headings
    - meta title/description
    - visible text
    - internal hrefs
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)

        self.title_parts: list[str] = []
        self.heading_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self.meta: dict[str, str] = {}

        self._inside_title = False
        self._inside_heading = False
        self._skip_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag_lower = tag.lower()
        attributes = {
            str(key).lower(): value
            for key, value in attrs
        }

        if tag_lower == "title":
            self._inside_title = True

        if tag_lower in {"h1", "h2", "h3"}:
            self._inside_heading = True

        if tag_lower in {"script", "style", "noscript", "svg", "template"}:
            self._skip_depth += 1

        if tag_lower == "meta":
            name = str(
                attributes.get("name")
                or attributes.get("property")
                or ""
            ).strip().lower()
            content = str(
                attributes.get("content")
                or ""
            ).strip()
            if name and content:
                self.meta[name] = content

        if tag_lower == "a":
            href = attributes.get("href")
            if href:
                self.links.append(href.strip())

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if tag_lower == "title":
            self._inside_title = False

        if tag_lower in {"h1", "h2", "h3"}:
            self._inside_heading = False

        if tag_lower in {"script", "style", "noscript", "svg", "template"}:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if not value:
            return

        if self._inside_title:
            self.title_parts.append(value)

        if self._inside_heading:
            self.heading_parts.append(value)

        if self._skip_depth == 0:
            self.text_parts.append(value)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()

    @property
    def headings(self) -> str:
        return " ".join(self.heading_parts).strip()

    @property
    def text(self) -> str:
        text = " ".join(self.text_parts)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


# ============================================================
# INTERNAL LINKING SERVICE
# ============================================================


class InternalLinkingService:
    def __init__(self, db: Session):
        self.db = db
        self._last_source_pages: list[dict[str, Any]] = []

    # ========================================================
    # ANTHROPIC API KEY
    # ========================================================

    def _resolve_anthropic_api_key(
        self,
        company: Company,
    ) -> str:
        """
        Resolve the Anthropic API key using the same architecture
        as the AI Settings system.

        Priority:

        1. Company encrypted Anthropic API key
        2. Global ANTHROPIC_API_KEY environment/config value
        """

        encrypted_key = getattr(
            company,
            "anthropic_api_key_encrypted",
            None,
        )

        if encrypted_key:
            try:
                decrypted_key = decrypt_secret(
                    str(encrypted_key).strip()
                )

                decrypted_key = str(
                    decrypted_key or ""
                ).strip()

                if decrypted_key:
                    return decrypted_key

            except Exception as exc:
                raise ValueError(
                    "The stored Anthropic API key could not be decrypted. "
                    "Please open Settings → AI and save the Anthropic API key again."
                ) from exc

        global_key = getattr(
            settings,
            "ANTHROPIC_API_KEY",
            None,
        )

        if global_key:
            global_key = str(
                global_key
            ).strip()

        if global_key:
            return global_key

        raise ValueError(
            "Claude API key is not configured. "
            "Please open Settings → AI and configure your Anthropic API key."
        )

    # ========================================================
    # MODEL RESOLUTION
    # ========================================================

    async def _resolve_model(
        self,
        client: AsyncAnthropic,
    ) -> str:
        """
        Resolve an available Anthropic model dynamically.

        Priority:

        1. ANTHROPIC_MODEL configured in settings
        2. Current Sonnet model
        3. Any available Sonnet model
        4. First available model
        """

        configured_model = getattr(
            settings,
            "ANTHROPIC_MODEL",
            None,
        )

        if configured_model:
            configured_model = str(
                configured_model
            ).strip()

        try:
            response = await client.models.list(
                limit=100,
            )

            models = list(
                getattr(
                    response,
                    "data",
                    [],
                )
                or []
            )

            if not models:
                raise RuntimeError(
                    "Anthropic returned no available models."
                )

            model_ids = []

            for model in models:
                model_id = getattr(
                    model,
                    "id",
                    None,
                )

                if model_id:
                    model_ids.append(
                        str(model_id)
                    )

            if not model_ids:
                raise RuntimeError(
                    "Anthropic returned models without model IDs."
                )

            # ------------------------------------------------
            # Configured model
            # ------------------------------------------------

            if configured_model:
                if configured_model in model_ids:
                    return configured_model

            # ------------------------------------------------
            # Prefer current Sonnet
            # ------------------------------------------------

            preferred_sonnet_patterns = (
                "claude-sonnet-4",
                "claude-sonnet-3.7",
                "claude-3-7-sonnet",
                "claude-3-5-sonnet",
                "claude-sonnet",
            )

            for pattern in preferred_sonnet_patterns:
                for model_id in model_ids:
                    if pattern in model_id.lower():
                        return model_id

            # ------------------------------------------------
            # Any Sonnet
            # ------------------------------------------------

            for model_id in model_ids:
                if "sonnet" in model_id.lower():
                    return model_id

            # ------------------------------------------------
            # Final fallback
            # ------------------------------------------------

            return model_ids[0]

        except AuthenticationError:
            raise

        except APIConnectionError:
            raise

        except APIStatusError:
            raise

        except Exception as exc:
            # If model discovery fails but a configured model
            # exists, use it.
            if configured_model:
                return configured_model

            raise RuntimeError(
                f"Could not determine an available Anthropic model: {exc}"
            ) from exc

    # ========================================================
    # URL HELPERS
    # ========================================================

    @staticmethod
    def _normalize_url(url: str) -> str:
        """
        Normalize a URL for comparison.
        """

        value = str(
            url or ""
        ).strip()

        if not value:
            return ""

        value = urldefrag(value)[0]

        parsed = urlparse(value)

        if not parsed.scheme:
            return value.rstrip("/")

        normalized = value.rstrip("/")

        return normalized

    @staticmethod
    def _same_domain(
        url_a: str,
        url_b: str,
    ) -> bool:
        """
        Check whether two URLs belong to the same hostname.
        """

        try:
            host_a = (
                urlparse(url_a)
                .hostname
                or ""
            ).lower()

            host_b = (
                urlparse(url_b)
                .hostname
                or ""
            ).lower()

            return host_a == host_b and bool(host_a)

        except Exception:
            return False

    @staticmethod
    def _is_http_url(url: str) -> bool:
        try:
            scheme = (
                urlparse(url)
                .scheme
                .lower()
            )

            return scheme in {
                "http",
                "https",
            }

        except Exception:
            return False

    # ========================================================
    # FETCH WEB PAGE
    # ========================================================

    async def _fetch_page(
        self,
        url: str,
    ) -> dict[str, Any]:
        """
        Fetch a public webpage and extract:

        - title
        - text
        - internal links
        """

        if not self._is_http_url(url):
            return {
                "url": url,
                "title": "",
                "text": "",
                "links": [],
                "error": "URL must use HTTP or HTTPS.",
            }

        timeout = httpx.Timeout(
            20.0,
            connect=8.0,
        )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; BoostRankersAISEOOS/1.0; +https://boostrankers.com)"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
        }

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers=headers,
            ) as client:

                response = await client.get(url)

                response.raise_for_status()

                content_type = (
                    response.headers.get(
                        "content-type",
                        "",
                    )
                    .lower()
                )

                if (
                    "html" not in content_type
                    and "xhtml" not in content_type
                    and not response.text.lstrip().startswith("<")
                ):
                    return {
                        "url": str(response.url),
                        "title": "",
                        "text": "",
                        "links": [],
                        "error": (
                            "The URL did not return an HTML document."
                        ),
                    }

                parser = _PageParser()

                parser.feed(
                    response.text
                )

                final_url = str(
                    response.url
                )

                internal_links: list[str] = []

                for href in parser.links:

                    if not href:
                        continue

                    href = href.strip()

                    if href.startswith(
                        (
                            "#",
                            "mailto:",
                            "tel:",
                            "javascript:",
                            "data:",
                        )
                    ):
                        continue

                    absolute_url = urljoin(
                        final_url,
                        href,
                    )

                    absolute_url = urldefrag(
                        absolute_url
                    )[0]

                    if not self._is_http_url(
                        absolute_url
                    ):
                        continue

                    if not self._same_domain(
                        final_url,
                        absolute_url,
                    ):
                        continue

                    normalized = self._normalize_url(
                        absolute_url
                    )

                    if normalized:
                        internal_links.append(
                            normalized
                        )

                # Remove duplicates while
                # preserving order.
                internal_links = list(
                    dict.fromkeys(
                        internal_links
                    )
                )

                return {
                    "url": final_url,
                    "title": parser.title,
                    "headings": parser.headings[:4000],
                    "meta_title": parser.title[:500],
                    "meta_description": (
                        parser.meta.get("description")
                        or parser.meta.get("og:description")
                        or ""
                    )[:1000],
                    "focus_keyword": (
                        parser.meta.get("keywords")
                        or parser.meta.get("article:section")
                        or ""
                    )[:300],
                    "text": parser.text[:16000],
                    "links": internal_links[:100],
                    "error": None,
                }

        except httpx.HTTPStatusError as exc:
            return {
                "url": url,
                "title": "",
                "text": "",
                "links": [],
                "error": (
                    f"HTTP {exc.response.status_code}"
                ),
            }

        except httpx.RequestError as exc:
            return {
                "url": url,
                "title": "",
                "text": "",
                "links": [],
                "error": str(exc),
            }

        except Exception as exc:
            return {
                "url": url,
                "title": "",
                "text": "",
                "links": [],
                "error": str(exc),
            }

    # ========================================================
    # SITEMAP DISCOVERY
    # ========================================================

    async def _discover_from_sitemap(
        self,
        source_url: str,
        limit: int = 50,
    ) -> list[str]:
        """
        Discover same-domain URLs from sitemap.xml.

        This is especially useful when the user submits only
        one blog post URL.
        """

        parsed = urlparse(
            source_url
        )

        if not parsed.scheme or not parsed.netloc:
            return []

        base = (
            f"{parsed.scheme}://{parsed.netloc}"
        )

        sitemap_urls = [
            f"{base}/sitemap.xml",
            f"{base}/wp-sitemap.xml",
        ]

        timeout = httpx.Timeout(
            15.0,
            connect=6.0,
        )

        headers = {
            "User-Agent": (
                "BoostRankersAISEOOS/1.0"
            ),
            "Accept": (
                "application/xml,text/xml,"
                "application/xhtml+xml,text/html"
            ),
        }

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:

            for sitemap_url in sitemap_urls:

                try:
                    response = await client.get(
                        sitemap_url
                    )

                    if response.status_code >= 400:
                        continue

                    xml_text = response.text

                    root = ET.fromstring(
                        xml_text
                    )

                    discovered: list[str] = []

                    for element in root.iter():

                        tag = element.tag

                        if isinstance(
                            tag,
                            str,
                        ):
                            tag = tag.split(
                                "}"
                            )[-1]

                        if tag != "loc":
                            continue

                        value = (
                            element.text
                            or ""
                        ).strip()

                        if not value:
                            continue

                        normalized = self._normalize_url(
                            value
                        )

                        if not self._is_http_url(
                            normalized
                        ):
                            continue

                        if not self._same_domain(
                            source_url,
                            normalized,
                        ):
                            continue

                        discovered.append(
                            normalized
                        )

                        if len(discovered) >= limit:
                            break

                    if discovered:
                        return list(
                            dict.fromkeys(
                                discovered
                            )
                        )[:limit]

                except Exception:
                    continue

        return []

    # ========================================================
    # SEMANTIC / TARGET EVIDENCE HELPERS
    # ========================================================

    _STOPWORDS = {
        "about", "after", "again", "also", "because", "being", "between",
        "could", "from", "have", "into", "more", "most", "other", "over",
        "same", "should", "some", "such", "than", "that", "their", "there",
        "these", "they", "this", "those", "through", "under", "using",
        "very", "what", "when", "where", "which", "while", "with", "would",
        "your", "you", "our", "for", "and", "the", "are", "was", "were",
        "will", "not", "but", "can", "all", "any", "its", "has", "had",
        "how", "why", "who", "per", "www", "com", "https",
    }

    @classmethod
    def _tokens(cls, value: str) -> set[str]:
        words = re.findall(r"[a-z0-9]{3,}", str(value or "").lower())
        return {
            word
            for word in words
            if word not in cls._STOPWORDS
        }

    @classmethod
    def _intent(cls, page: dict[str, Any]) -> str:
        combined = " ".join(
            [
                str(page.get("title") or ""),
                str(page.get("headings") or ""),
                str(page.get("text") or "")[:5000],
                str(page.get("url") or ""),
            ]
        ).lower()

        if any(term in combined for term in (
            "quote", "book", "booking", "contact us", "get a quote",
            "request a quote", "enquire", "enquiry",
        )):
            return "transactional"

        if any(term in combined for term in (
            "price", "pricing", "cost", "how much", "compare",
            "comparison", "best ", "choose", "review",
        )):
            return "commercial"

        if "/blog/" in str(page.get("url") or "").lower():
            return "informational"

        if any(term in combined for term in (
            "how to", "guide", "tips", "checklist", "explained",
            "what is", "why ", "when to",
        )):
            return "informational"

        return "commercial" if any(term in combined for term in (
            "service", "services", "professional", "cleaning",
            "solution", "solutions",
        )) else "navigational"

    @classmethod
    def _infer_target_type(cls, page: dict[str, Any]) -> str:
        """
        Public-site evidence only. A WordPress REST result should be used
        when available; otherwise this is explicitly marked as an inference.
        """
        url = str(page.get("url") or "").lower()
        if "/blog/" in url:
            return "post"
        return "page"

    @classmethod
    def _semantic_overlap(
        cls,
        source: dict[str, Any],
        target: dict[str, Any],
    ) -> float:
        source_tokens = cls._tokens(
            " ".join(
                [
                    str(source.get("title") or ""),
                    str(source.get("headings") or ""),
                    str(source.get("text") or "")[:9000],
                ]
            )
        )
        target_title = cls._tokens(
            " ".join(
                [
                    str(target.get("title") or ""),
                    str(target.get("headings") or ""),
                ]
            )
        )
        target_body = cls._tokens(
            str(target.get("text") or "")[:9000]
        )

        if not source_tokens or not target_title:
            return 0.0

        title_overlap = len(source_tokens & target_title) / max(
            1,
            len(target_title),
        )
        body_overlap = len(source_tokens & target_body) / max(
            1,
            len(target_body),
        )

        # Title/headings are deliberately weighted more heavily than
        # incidental body-word overlap.
        return min(
            1.0,
            (title_overlap * 0.70) + (body_overlap * 0.30),
        )

    @classmethod
    def _location_overlap(
        cls,
        source: dict[str, Any],
        target: dict[str, Any],
    ) -> bool:
        source_tokens = cls._tokens(
            " ".join(
                [
                    str(source.get("title") or ""),
                    str(source.get("headings") or ""),
                    str(source.get("text") or "")[:5000],
                ]
            )
        )
        target_tokens = cls._tokens(
            " ".join(
                [
                    str(target.get("title") or ""),
                    str(target.get("headings") or ""),
                    str(target.get("url") or ""),
                ]
            )
        )
        locations = {
            "perth", "wa", "western", "australia",
            "melbourne", "sydney", "brisbane", "adelaide",
        }
        return bool((source_tokens & locations) & target_tokens)

    @classmethod
    def _candidate_relevance(
        cls,
        source: dict[str, Any],
        target: dict[str, Any],
    ) -> dict[str, Any]:
        overlap = cls._semantic_overlap(source, target)
        source_intent = cls._intent(source)
        target_intent = cls._intent(target)
        location_match = cls._location_overlap(source, target)

        intent_compatible = (
            source_intent == target_intent
            or (
                source_intent == "informational"
                and target_intent in {"commercial", "informational"}
            )
            or (
                source_intent == "commercial"
                and target_intent in {"commercial", "transactional"}
            )
        )

        # This is an internal candidate gate, not a user-facing SEO score.
        # It prevents Claude from considering obviously unrelated targets.
        eligible = (
            overlap >= 0.035
            and intent_compatible
        )

        if location_match:
            eligible = eligible and overlap >= 0.025

        return {
            "eligible": eligible,
            "semantic_overlap": round(overlap, 4),
            "source_intent": source_intent,
            "target_intent": target_intent,
            "location_match": location_match,
        }

    @classmethod
    def _candidate_summary(
        cls,
        source: dict[str, Any],
        target: dict[str, Any],
    ) -> dict[str, Any]:
        relevance = cls._candidate_relevance(source, target)
        return {
            "url": target.get("url", ""),
            "title": target.get("title", "") or "Unknown",
            "target_type": target.get("target_type")
            or cls._infer_target_type(target),
            "type_evidence": target.get("type_evidence", "inferred from URL structure"),
            "headings": target.get("headings", "")[:1800],
            "meta_description": target.get("meta_description", ""),
            "content_excerpt": target.get("text", "")[:4500],
            "intent": relevance["target_intent"],
            "semantic_overlap": relevance["semantic_overlap"],
            "location_match": relevance["location_match"],
        }

    # ========================================================
    # BUILD ANALYSIS CONTEXT
    # ========================================================

    async def _build_context(
        self,
        urls: list[str],
    ) -> dict[str, Any]:

        clean_urls = [
            self._normalize_url(url)
            for url in urls
            if self._normalize_url(url)
        ]
        clean_urls = list(dict.fromkeys(clean_urls))

        if not clean_urls:
            raise ValueError("At least one valid URL is required.")

        pages = await asyncio.gather(
            *[self._fetch_page(url) for url in clean_urls]
        )

        candidates: list[str] = []

        for page in pages:
            candidates.extend(
                self._normalize_url(link)
                for link in page.get("links", [])
                if self._normalize_url(link)
            )

        # One source URL is enough: discover the site architecture instead
        # of forcing users to manually supply target URLs.
        if len(clean_urls) == 1:
            candidates.extend(
                await self._discover_from_sitemap(
                    clean_urls[0],
                    limit=75,
                )
            )

        # With multiple supplied URLs, those URLs remain eligible targets.
        candidates.extend(clean_urls)

        source_set = set(clean_urls)
        candidates = [
            url
            for url in dict.fromkeys(candidates)
            if url and url not in source_set
            and self._is_http_url(url)
            and self._same_domain(clean_urls[0], url)
        ]

        # Fetch actual target content. URL slugs alone are never enough.
        target_pages = await asyncio.gather(
            *[
                self._fetch_page(url)
                for url in candidates[:75]
            ]
        )

        source_page = pages[0]
        target_candidates: list[dict[str, Any]] = []

        for target in target_pages:
            if target.get("error") or not target.get("url"):
                continue

            target_url = self._normalize_url(
                str(target.get("url") or "")
            )
            if not target_url or target_url in source_set:
                continue

            target["target_type"] = self._infer_target_type(target)
            target["type_evidence"] = (
                "inferred from URL structure; exact WordPress post/page "
                "type is not publicly exposed by this integration"
            )

            relevance = self._candidate_relevance(
                source_page,
                target,
            )
            if relevance["eligible"]:
                target_candidates.append(target)

        # Rank only for candidate ordering; this is an internal retrieval
        # gate and is deliberately not exposed as a fabricated SEO score.
        target_candidates.sort(
            key=lambda item: self._candidate_relevance(
                source_page,
                item,
            )["semantic_overlap"],
            reverse=True,
        )

        target_candidates = target_candidates[:20]

        return {
            "urls": clean_urls,
            "pages": pages,
            "candidates": [
                str(page.get("url"))
                for page in target_candidates
            ],
            "candidate_pages": target_candidates,
        }

    # ========================================================
    # JSON EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_json(
        content: str,
    ) -> dict[str, Any]:
        """
        Parse a Claude response defensively.

        Claude is instructed to return JSON only, but production code
        must not assume that the model will always obey perfectly.
        This parser handles:
        - plain JSON
        - ```json ... ``` fenced JSON
        - harmless text before/after the JSON object
        - trailing commas before } or ]

        It deliberately does NOT invent or reconstruct missing data.
        """

        if not content:
            raise ValueError("Claude returned an empty response.")

        text = str(content).strip()

        # Remove markdown fences anywhere around the response.
        text = re.sub(
            r"^\s*```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\s*```\s*$",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        # Fast path: the whole response is already valid JSON.
        try:
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise ValueError(
                    "Claude returned JSON, but it was not an object."
                )
            return parsed
        except json.JSONDecodeError:
            pass

        # Find a balanced JSON object while respecting quoted strings.
        # Using rfind('}') is unsafe when Claude adds text containing
        # braces, so scan the response structurally instead.
        start = text.find("{")
        if start < 0:
            raise ValueError(
                "Claude returned no JSON object."
            )

        depth = 0
        in_string = False
        escaped = False
        end = None

        for index in range(start, len(text)):
            char = text[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue

            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = index
                    break

        if end is None:
            raise ValueError(
                "Claude returned incomplete JSON. "
                "The response appears to have been truncated."
            )

        candidate = text[start:end + 1].strip()

        # Conservative cleanup for a common model formatting mistake:
        # trailing commas immediately before a closing JSON token.
        candidate = re.sub(
            r",(\s*[}\]])",
            r"\1",
            candidate,
        )

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Claude returned malformed JSON. "
                "Please try the analysis again."
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError(
                "Claude returned JSON in an unexpected format."
            )

        return parsed

    @staticmethod
    def _response_text(response: Any) -> str:
        """Extract text blocks from an Anthropic Messages response."""
        parts: list[str] = []

        for block in getattr(response, "content", []) or []:
            block_text = getattr(block, "text", None)
            if block_text:
                parts.append(str(block_text))

        return "\n".join(parts).strip()

    # ========================================================
    # NORMALIZE AI RESPONSE
    # ========================================================

    def _normalize_ai_response(
        self,
        data: dict[str, Any],
        source_urls: list[str],
        candidate_pages: list[dict[str, Any]],
    ) -> dict[str, Any]:

        analysis = str(data.get("analysis") or "").strip()
        raw_suggestions = data.get("suggestions", [])
        if not isinstance(raw_suggestions, list):
            raw_suggestions = []

        allowed_sources = {
            self._normalize_url(url)
            for url in source_urls
        }
        target_map = {
            self._normalize_url(str(page.get("url") or "")): page
            for page in candidate_pages
            if page.get("url")
        }

        # Supplied source URLs can be targets when multiple source pages
        # were intentionally analyzed together.
        for page in self._last_source_pages:
            normalized = self._normalize_url(str(page.get("url") or ""))
            if normalized and normalized not in target_map:
                target_map[normalized] = page

        suggestions: list[dict[str, Any]] = []

        for item in raw_suggestions:
            if not isinstance(item, dict):
                continue

            source = self._normalize_url(
                str(item.get("source") or "")
            )
            target = self._normalize_url(
                str(item.get("target") or "")
            )
            anchor = str(item.get("anchor") or "").strip()

            if (
                not source
                or not target
                or not anchor
                or source not in allowed_sources
                or source == target
                or target not in target_map
            ):
                continue

            target_page = target_map[target]
            target_title = str(
                target_page.get("title")
                or item.get("target_title")
                or ""
            ).strip()
            target_type = str(
                item.get("target_type")
                or target_page.get("target_type")
                or self._infer_target_type(target_page)
            ).strip()

            reason = str(
                item.get("reason")
                or ""
            ).strip()

            if not reason:
                reason = (
                    "Target content is contextually related to the source "
                    "topic based on its title, headings, and page content."
                )

            suggestions.append(
                {
                    "source": source,
                    "target": target,
                    "target_type": target_type,
                    "target_title": target_title or "Unknown",
                    "anchor": anchor,
                    "reason": reason,
                }
            )

        unique_suggestions: list[dict[str, Any]] = []
        seen_pairs: set[tuple[str, str]] = set()
        seen_anchors: set[tuple[str, str]] = set()

        for suggestion in suggestions:
            pair_key = (
                suggestion["source"],
                suggestion["target"],
            )
            anchor_key = (
                suggestion["source"],
                suggestion["anchor"].lower(),
            )

            if pair_key in seen_pairs or anchor_key in seen_anchors:
                continue

            seen_pairs.add(pair_key)
            seen_anchors.add(anchor_key)
            unique_suggestions.append(suggestion)

        return {
            "analysis": analysis,
            "suggestions": unique_suggestions[:12],
        }

    # ========================================================
    # AI ANALYSIS
    # ========================================================

    async def analyze(
        self,
        urls: list[str],
        company: Company,
    ) -> dict[str, Any]:
        """
        Analyze URLs and generate real AI-powered internal
        linking suggestions using the company's Anthropic key.

        Important:
        - Does NOT create fake suggestions.
        - Does NOT deduct credits when Claude fails.
        - Supports a single submitted URL by discovering
          candidate URLs from the page and sitemap.
        """

        # ----------------------------------------------------
        # Validate credits
        # ----------------------------------------------------

        if (
            getattr(
                company,
                "ai_credits",
                0,
            )
            <= 0
        ):
            raise ValueError(
                "Insufficient AI credits. Please add budget."
            )

        # ----------------------------------------------------
        # Build web context
        # ----------------------------------------------------

        context = await self._build_context(
            urls
        )

        source_urls = context["urls"]
        pages = context["pages"]
        candidate_urls = context["candidates"]
        candidate_pages = context.get("candidate_pages", [])

        # ----------------------------------------------------
        # Resolve the correct encrypted company key.
        # ----------------------------------------------------

        api_key = self._resolve_anthropic_api_key(
            company
        )

        if not api_key.startswith(
            "sk-ant-"
        ):
            raise ValueError(
                "The configured Anthropic API key has an invalid format. "
                "Please open Settings → AI and update it."
            )

        client = AsyncAnthropic(
            api_key=api_key
        )

        try:

            # ------------------------------------------------
            # Resolve available model.
            # ------------------------------------------------

            model = await self._resolve_model(
                client
            )

            # ------------------------------------------------
            # Build page context.
            # ------------------------------------------------

            self._last_source_pages = pages

            page_sections: list[str] = []

            for page in pages:
                page_url = page.get("url", "")
                title = page.get("title", "")
                headings = page.get("headings", "")
                text = page.get("text", "")
                error = page.get("error")

                section = (
                    f"SOURCE URL: {page_url}\n"
                    f"TITLE: {title or 'Unknown'}\n"
                    f"HEADINGS: {headings[:2500]}\n"
                )

                if error:
                    section += f"FETCH STATUS: {error}\n"
                if text:
                    section += f"PAGE CONTENT:\n{text[:8500]}\n"

                page_sections.append(section)

            source_context = "\n\n".join(page_sections)[:32000]

            candidate_pages = context.get("candidate_pages", [])
            candidate_context_parts: list[str] = []

            for candidate in candidate_pages:
                candidate_context_parts.append(
                    json.dumps(
                        self._candidate_summary(
                            pages[0],
                            candidate,
                        ),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )

            candidate_context = "\n".join(candidate_context_parts)
            if not candidate_context:
                candidate_context = "- No sufficiently relevant internal targets were discovered."

            prompt = f"""
You are an expert technical SEO internal-linking strategist.

Your job is to recommend ONLY contextual internal links supported by
REAL SOURCE CONTENT and REAL TARGET CONTENT.

SOURCE URLS:
{chr(10).join(f"- {url}" for url in source_urls)}

SOURCE PAGE CONTEXT:
{source_context}

VERIFIED TARGET PAGE EVIDENCE:
Each target below was actually fetched from the same domain. Do not infer
target content from a URL slug when the supplied evidence says otherwise.

{candidate_context}

STRICT RULES:
1. A source MUST be one of SOURCE URLS.
2. A target MUST be one of the VERIFIED TARGET PAGE EVIDENCE URLs.
3. Never invent, rewrite, shorten, normalize, or guess a URL.
4. Never use an external domain.
5. Never create a self-link.
6. Use a target only when its actual title/headings/content support a
   meaningful next step for the reader.
7. Do NOT recommend a generic service page merely because it exists.
8. Do NOT recommend carpet, school, gym, medical, warehouse or other
   specialist services unless the source actually discusses that topic
   or a closely connected need.
9. Respect search intent. Informational sources should not be stuffed with
   unrelated transactional/service links.
10. Prefer a closely related supporting article when it is more useful than
    a service page.
11. Anchor text must be natural, descriptive, and supported by the source
    context. Do not force exact-match keywords.
12. Do not repeat the same anchor for the same source.
13. Do not return duplicate source→target pairs.
14. If no target is genuinely useful, return an empty suggestions array.
15. Return at most 8 suggestions.
16. For every suggestion provide target_type, target_title, and a concise
    evidence-based reason.
17. Do not invent focus keywords. No WordPress focus-keyword data is supplied
    to this analysis.
18. Do not claim a numeric relevance score.
19. Return ONLY one valid JSON object.

Return exactly:
{{
  "analysis": "Brief evidence-based summary of the strongest topical relationships.",
  "suggestions": [
    {{
      "source": "https://example.com/source/",
      "target": "https://example.com/target/",
      "target_type": "page",
      "target_title": "Verified target title",
      "anchor": "natural contextual anchor",
      "reason": "Why this target is useful based on the source and target evidence."
    }}
  ]
}}
"""
            # ------------------------------------------------
            # Claude request.
            #
            # We intentionally keep the requested output small.
            # A large candidate set can otherwise cause Claude to hit
            # max_tokens in the middle of a JSON object.
            # ------------------------------------------------

            async def _request_json(
                request_prompt: str,
                max_tokens: int,
            ) -> dict[str, Any]:
                response = await client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=(
                        "You are a professional SEO internal-linking "
                        "expert. For this request, output ONLY one "
                        "syntactically valid JSON object. Never use "
                        "Markdown or code fences."
                    ),
                    messages=[
                        {
                            "role": "user",
                            "content": request_prompt,
                        }
                    ],
                )

                content = self._response_text(response)

                if not content:
                    raise ValueError(
                        "Claude returned an empty response."
                    )

                stop_reason = getattr(
                    response,
                    "stop_reason",
                    None,
                )

                try:
                    return self._extract_json(content)
                except ValueError as exc:
                    # Give the caller a precise error when Claude stopped
                    # because its output token budget was exhausted.
                    if stop_reason == "max_tokens":
                        raise ValueError(
                            "Claude's JSON response was truncated because "
                            "the output limit was reached."
                        ) from exc
                    raise

            try:
                data = await _request_json(
                    prompt,
                    max_tokens=2048,
                )
            except ValueError as first_error:
                # One controlled retry with an even smaller output contract.
                # This handles occasional model formatting/truncation without
                # fabricating or repairing missing recommendations.
                retry_prompt = prompt + """

IMPORTANT RETRY:
Return NO MORE THAN 6 suggestions.
Keep "analysis" under 250 characters.
The entire response must be a compact JSON object.
"""

                try:
                    data = await _request_json(
                        retry_prompt,
                        max_tokens=2048,
                    )
                except ValueError as retry_error:
                    raise ValueError(
                        "Claude could not return valid structured JSON "
                        "for this internal-linking analysis. "
                        f"First attempt: {first_error}. "
                        f"Retry: {retry_error}"
                    ) from retry_error

            # ------------------------------------------------
            # Validate/normalize suggestions.
            # ------------------------------------------------

            result = self._normalize_ai_response(
                data,
                source_urls,
                candidate_pages,
            )

            return result

        except AuthenticationError as exc:

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "invalid_api_key",
                    "message": (
                        "Anthropic rejected the configured API key. "
                        "Open Settings → AI and update or test the "
                        "Anthropic API key."
                    ),
                },
            ) from exc

        except RateLimitError as exc:

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "rate_limited",
                    "message": (
                        "Anthropic rate limit reached. "
                        "Please wait and try again."
                    ),
                },
            ) from exc

        except APIConnectionError as exc:

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "anthropic_connection_error",
                    "message": (
                        "Could not connect to Anthropic. "
                        "Please try again."
                    ),
                },
            ) from exc

        except APIStatusError as exc:

            status_code = getattr(
                exc,
                "status_code",
                502,
            )

            raise HTTPException(
                status_code=(
                    status_code
                    if 400 <= status_code < 600
                    else 502
                ),
                detail={
                    "code": "anthropic_api_error",
                    "message": (
                        "Anthropic returned an API error."
                    ),
                },
            ) from exc

        except HTTPException:
            raise

        except ValueError:
            raise

        except Exception as exc:

            raise ValueError(
                f"Internal linking AI generation failed: {exc}"
            ) from exc

        finally:
            await client.close()

    # ========================================================
    # CREATE DATABASE SUGGESTION
    # ========================================================

    async def create_suggestion(
        self,
        urls: list[str],
        company: Company,
    ) -> InternalLinkingSuggestion:
        """
        Generate an AI suggestion and save it.

        AI credits are deducted only after successful AI
        generation.
        """

        if (
            getattr(
                company,
                "ai_credits",
                0,
            )
            <= 0
        ):
            raise ValueError(
                "Insufficient AI credits. Please add budget."
            )

        # ----------------------------------------------------
        # Generate AI result.
        #
        # If Claude fails, this raises and NO credit is
        # deducted.
        # ----------------------------------------------------

        data = await self.analyze(
            urls,
            company,
        )

        suggestions = data.get(
            "suggestions",
            [],
        )

        analysis = data.get(
            "analysis",
            "",
        )

        # ----------------------------------------------------
        # Deduct exactly one credit after successful AI call.
        # ----------------------------------------------------

        company.ai_credits -= 1

        suggestion = InternalLinkingSuggestion(
            company_id=company.id,
            urls=urls,
            suggestions=suggestions,
            analysis=analysis,
        )

        try:

            self.db.add(
                suggestion
            )

            self.db.add(
                company
            )

            self.db.commit()

            self.db.refresh(
                suggestion
            )

        except Exception:
            self.db.rollback()

            # Restore the credit in memory because the database
            # transaction failed.
            company.ai_credits += 1

            raise

        return suggestion

    # ========================================================
    # GET SUGGESTIONS
    # ========================================================

    def get_suggestions(
        self,
        company_id: str,
        limit: int = 50,
    ) -> list[InternalLinkingSuggestion]:
        """
        Get recent internal linking suggestions for a company.
        """

        return (
            self.db.query(
                InternalLinkingSuggestion
            )
            .filter(
                InternalLinkingSuggestion.company_id
                == company_id
            )
            .order_by(
                InternalLinkingSuggestion.created_at.desc()
            )
            .limit(
                limit
            )
            .all()
        )

    # ========================================================
    # GET SINGLE SUGGESTION
    # ========================================================

    def get_suggestion(
        self,
        suggestion_id: str,
        company_id: str,
    ) -> InternalLinkingSuggestion | None:
        """
        Get one suggestion belonging to the current company.
        """

        return (
            self.db.query(
                InternalLinkingSuggestion
            )
            .filter(
                InternalLinkingSuggestion.id
                == suggestion_id,
                InternalLinkingSuggestion.company_id
                == company_id,
            )
            .first()
        )

    # ========================================================
    # DELETE SUGGESTION
    # ========================================================

    def delete_suggestion(
        self,
        suggestion_id: str,
        company_id: str,
    ) -> bool:
        """
        Delete a suggestion belonging to the current company.
        """

        suggestion = self.get_suggestion(
            suggestion_id,
            company_id,
        )

        if not suggestion:
            return False

        self.db.delete(
            suggestion
        )

        self.db.commit()

        return True