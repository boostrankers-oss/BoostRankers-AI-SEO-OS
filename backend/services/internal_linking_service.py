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
    Lightweight HTML parser used to extract:

    - page title
    - visible text
    - internal hrefs
    """

    def __init__(self) -> None:
        super().__init__(
            convert_charrefs=True,
        )

        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[str] = []

        self._inside_title = False
        self._skip_text = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag_lower = tag.lower()

        if tag_lower == "title":
            self._inside_title = True

        if tag_lower in {
            "script",
            "style",
            "noscript",
            "svg",
        }:
            self._skip_text = True

        if tag_lower == "a":
            attributes = dict(attrs)
            href = attributes.get("href")

            if href:
                self.links.append(href.strip())

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if tag_lower == "title":
            self._inside_title = False

        if tag_lower in {
            "script",
            "style",
            "noscript",
            "svg",
        }:
            self._skip_text = False

    def handle_data(self, data: str) -> None:
        value = data.strip()

        if not value:
            return

        if self._inside_title:
            self.title_parts.append(value)

        if not self._skip_text:
            self.text_parts.append(value)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()

    @property
    def text(self) -> str:
        text = " ".join(self.text_parts)

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()


# ============================================================
# INTERNAL LINKING SERVICE
# ============================================================


class InternalLinkingService:
    def __init__(self, db: Session):
        self.db = db

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
                    "text": parser.text[:12000],
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

        clean_urls = list(
            dict.fromkeys(
                clean_urls
            )
        )

        if not clean_urls:
            raise ValueError(
                "At least one valid URL is required."
            )

        pages = await asyncio.gather(
            *[
                self._fetch_page(url)
                for url in clean_urls
            ]
        )

        candidates: list[str] = []

        # ----------------------------------------------------
        # Extract links already found on supplied pages
        # ----------------------------------------------------

        for page in pages:

            for link in page.get(
                "links",
                [],
            ):

                normalized = self._normalize_url(
                    link
                )

                if normalized:
                    candidates.append(
                        normalized
                    )

        # ----------------------------------------------------
        # If only one URL was supplied, use sitemap
        # discovery to find possible target pages.
        # ----------------------------------------------------

        if len(clean_urls) == 1:

            sitemap_candidates = (
                await self._discover_from_sitemap(
                    clean_urls[0],
                    limit=75,
                )
            )

            candidates.extend(
                sitemap_candidates
            )

        # ----------------------------------------------------
        # Supplied URLs themselves are candidates.
        # ----------------------------------------------------

        candidates.extend(
            clean_urls
        )

        # ----------------------------------------------------
        # Deduplicate and remove source URLs.
        # ----------------------------------------------------

        source_set = {
            self._normalize_url(url)
            for url in clean_urls
        }

        candidates = [
            url
            for url in dict.fromkeys(
                candidates
            )
            if url
            and url not in source_set
        ]

        # Keep context manageable.
        candidates = candidates[:100]

        return {
            "urls": clean_urls,
            "pages": pages,
            "candidates": candidates,
        }

    # ========================================================
    # JSON EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_json(
        content: str,
    ) -> dict[str, Any]:
        """
        Parse JSON even when Claude accidentally wraps it
        in markdown code fences or surrounding text.
        """

        if not content:
            raise ValueError(
                "Claude returned an empty response."
            )

        text = content.strip()

        # Remove markdown fences.
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

        text = text.strip()

        try:
            parsed = json.loads(
                text
            )

            if not isinstance(
                parsed,
                dict,
            ):
                raise ValueError(
                    "Claude returned JSON, but it was not an object."
                )

            return parsed

        except json.JSONDecodeError:
            pass

        # ----------------------------------------------------
        # Try to locate the first JSON object.
        # ----------------------------------------------------

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            raise ValueError(
                "Claude returned an invalid JSON response."
            )

        candidate = text[
            start : end + 1
        ]

        try:
            parsed = json.loads(
                candidate
            )

        except json.JSONDecodeError as exc:
            raise ValueError(
                "Claude returned an invalid JSON response."
            ) from exc

        if not isinstance(
            parsed,
            dict,
        ):
            raise ValueError(
                "Claude returned JSON in an unexpected format."
            )

        return parsed

    # ========================================================
    # NORMALIZE AI RESPONSE
    # ========================================================

    def _normalize_ai_response(
        self,
        data: dict[str, Any],
        source_urls: list[str],
        candidate_urls: list[str],
    ) -> dict[str, Any]:

        analysis = data.get(
            "analysis",
            "",
        )

        if analysis is None:
            analysis = ""

        analysis = str(
            analysis
        ).strip()

        raw_suggestions = data.get(
            "suggestions",
            [],
        )

        if not isinstance(
            raw_suggestions,
            list,
        ):
            raw_suggestions = []

        allowed_sources = {
            self._normalize_url(url)
            for url in source_urls
        }

        allowed_targets = {
            self._normalize_url(url)
            for url in candidate_urls
        }

        # If multiple URLs were supplied, they can also be
        # valid targets.
        allowed_targets.update(
            self._normalize_url(url)
            for url in source_urls
        )

        suggestions: list[dict[str, str]] = []

        for item in raw_suggestions:

            if not isinstance(
                item,
                dict,
            ):
                continue

            source = self._normalize_url(
                str(
                    item.get(
                        "source",
                        "",
                    )
                    or ""
                )
            )

            target = self._normalize_url(
                str(
                    item.get(
                        "target",
                        "",
                    )
                    or ""
                )
            )

            anchor = str(
                item.get(
                    "anchor",
                    "",
                )
                or ""
            ).strip()

            if not source or not target or not anchor:
                continue

            # ------------------------------------------------
            # Source must be one of the URLs supplied by user.
            # ------------------------------------------------

            if source not in allowed_sources:
                continue

            # ------------------------------------------------
            # Never allow self-links.
            # ------------------------------------------------

            if source == target:
                continue

            # ------------------------------------------------
            # Target should be a discovered/known URL.
            # ------------------------------------------------

            if target not in allowed_targets:
                continue

            suggestions.append(
                {
                    "source": source,
                    "target": target,
                    "anchor": anchor,
                }
            )

        # Remove duplicate suggestions.
        unique_suggestions = []
        seen = set()

        for suggestion in suggestions:

            key = (
                suggestion["source"],
                suggestion["target"],
                suggestion["anchor"].lower(),
            )

            if key in seen:
                continue

            seen.add(key)
            unique_suggestions.append(
                suggestion
            )

        return {
            "analysis": analysis,
            "suggestions": unique_suggestions[
                :50
            ],
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

            page_sections: list[str] = []

            for page in pages:

                page_url = page.get(
                    "url",
                    "",
                )

                title = page.get(
                    "title",
                    "",
                )

                text = page.get(
                    "text",
                    "",
                )

                error = page.get(
                    "error",
                    None,
                )

                section = (
                    f"SOURCE URL: {page_url}\n"
                    f"TITLE: {title or 'Unknown'}\n"
                )

                if error:
                    section += (
                        f"FETCH STATUS: {error}\n"
                    )

                if text:
                    section += (
                        "PAGE CONTENT:\n"
                        f"{text[:8000]}\n"
                    )

                page_sections.append(
                    section
                )

            source_context = "\n\n".join(
                page_sections
            )

            candidate_context = "\n".join(
                f"- {url}"
                for url in candidate_urls
            )

            if not candidate_context:
                candidate_context = (
                    "- No internal target URLs were discovered automatically."
                )

            source_context = source_context[
                :30000
            ]

            # ------------------------------------------------
            # Strong structured prompt.
            # ------------------------------------------------

            prompt = f"""
You are an expert technical SEO and internal-linking strategist.

Your task is to identify REAL, useful internal-linking opportunities.

SOURCE URLS:
{chr(10).join(f"- {url}" for url in source_urls)}

DISCOVERED INTERNAL TARGET URLS:
{candidate_context}

SOURCE PAGE CONTEXT:
{source_context}

RULES:

1. Only recommend links between URLs provided in SOURCE URLS and
   DISCOVERED INTERNAL TARGET URLS.

2. Never invent URLs.

3. Never use an external domain.

4. Never recommend a URL that is not present in the discovered
   candidate list.

5. Never recommend a source URL linking to itself.

6. Anchor text must be natural, descriptive, and relevant to the
   target page.

7. Avoid repetitive exact-match keyword anchors.

8. Prefer contextual links that genuinely help the reader.

9. Prioritize commercially and topically important pages when
   the page context supports doing so.

10. If there are no suitable internal-linking opportunities,
    return an empty suggestions array rather than inventing one.

11. Return ONLY valid JSON.

Return exactly this structure:

{{
  "analysis": "A concise SEO analysis explaining the strongest
  internal linking opportunities and why they are useful.",
  "suggestions": [
    {{
      "source": "https://example.com/source-page/",
      "target": "https://example.com/target-page/",
      "anchor": "natural contextual anchor text"
    }}
  ]
}}
"""

            # ------------------------------------------------
            # Claude request.
            # ------------------------------------------------

            response = await client.messages.create(
                model=model,
                max_tokens=4096,
                system=(
                    "You are a professional SEO internal-linking "
                    "expert. Return only valid JSON when requested."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            # ------------------------------------------------
            # Extract text response safely.
            # ------------------------------------------------

            response_parts: list[str] = []

            for block in getattr(
                response,
                "content",
                [],
            ):

                block_text = getattr(
                    block,
                    "text",
                    None,
                )

                if block_text:
                    response_parts.append(
                        block_text
                    )

            content = "\n".join(
                response_parts
            ).strip()

            if not content:
                raise ValueError(
                    "Claude returned an empty response."
                )

            # ------------------------------------------------
            # Parse JSON.
            # ------------------------------------------------

            data = self._extract_json(
                content
            )

            # ------------------------------------------------
            # Validate/normalize suggestions.
            # ------------------------------------------------

            result = self._normalize_ai_response(
                data,
                source_urls,
                candidate_urls,
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