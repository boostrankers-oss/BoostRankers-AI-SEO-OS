from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from anthropic import (
    APIConnectionError,
    APIStatusError,
    AsyncAnthropic,
    AuthenticationError,
    RateLimitError,
)
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from models.company import Company
from models.competitor import Competitor
from services.secret_service import decrypt_secret


class CompetitorService:
    """
    Production competitor intelligence service.

    Responsibilities:
    - Company-scoped competitor CRUD.
    - Public website inspection.
    - Structured Anthropic competitive analysis.
    - 30/60/90 day strategy generation.
    - Safe handling of unavailable third-party SEO metrics.
    - No fabricated traffic/backlink/keyword/domain-authority data.
    """

    MAX_PAGES = 8
    MAX_LINKS_PER_PAGE = 25
    MAX_TEXT_LENGTH = 18000

    def __init__(self, db: Session):
        self.db = db

    # =========================================================
    # CRUD
    # =========================================================

    def get_competitors(
        self,
        company_id: str,
    ) -> list[Competitor]:
        return (
            self.db.query(Competitor)
            .filter(
                Competitor.company_id == company_id
            )
            .order_by(
                Competitor.created_at.desc()
            )
            .all()
        )

    def get_competitor(
        self,
        competitor_id: str,
        company_id: str,
    ) -> Competitor | None:
        return (
            self.db.query(Competitor)
            .filter(
                Competitor.id == competitor_id,
                Competitor.company_id == company_id,
            )
            .first()
        )

    def delete_competitor(
        self,
        competitor_id: str,
        company_id: str,
    ) -> bool:
        competitor = self.get_competitor(
            competitor_id,
            company_id,
        )

        if not competitor:
            return False

        self.db.delete(competitor)
        self.db.commit()

        return True

    # =========================================================
    # Anthropic configuration
    # =========================================================

    @staticmethod
    def _get_api_key(
        company: Company,
    ) -> str | None:
        """
        Resolve the company-specific encrypted Anthropic key.

        Fallback to the environment key only when no company key
        is available.
        """

        encrypted_key = getattr(
            company,
            "anthropic_api_key_encrypted",
            None,
        )

        if encrypted_key:
            try:
                api_key = decrypt_secret(
                    str(encrypted_key).strip()
                ).strip()

                if api_key:
                    return api_key

            except (
                ValueError,
                TypeError,
            ):
                return None

        global_key = os.getenv(
            "ANTHROPIC_API_KEY",
            "",
        ).strip()

        return global_key or None

    @staticmethod
    def _get_model() -> str:
        configured = os.getenv(
            "ANTHROPIC_MODEL",
            "",
        ).strip()

        return configured or "claude-sonnet-4-6"

    @classmethod
    def _create_client(
        cls,
        company: Company,
    ) -> tuple[AsyncAnthropic, str]:
        api_key = cls._get_api_key(company)

        if not api_key:
            raise ValueError(
                "Claude API key is not configured. "
                "Please add a valid Anthropic API key in Settings."
            )

        return (
            AsyncAnthropic(
                api_key=api_key,
            ),
            cls._get_model(),
        )

    # =========================================================
    # URL helpers
    # =========================================================

    @staticmethod
    def _normalize_domain(
        value: str,
    ) -> str:
        value = str(
            value or ""
        ).strip()

        if not value:
            raise ValueError(
                "Domain is required."
            )

        if not re.match(
            r"^https?://",
            value,
            flags=re.IGNORECASE,
        ):
            value = f"https://{value}"

        parsed = urlparse(value)

        if parsed.scheme.lower() not in {
            "http",
            "https",
        }:
            raise ValueError(
                "Only HTTP and HTTPS URLs are supported."
            )

        if not parsed.netloc:
            raise ValueError(
                "Please provide a valid website domain."
            )

        hostname = (
            parsed.hostname or ""
        ).lower()

        if hostname in {
            "localhost",
            "127.0.0.1",
            "::1",
        } or hostname.endswith(
            ".localhost"
        ):
            raise ValueError(
                "Localhost URLs are not allowed."
            )

        return (
            f"{parsed.scheme.lower()}://"
            f"{parsed.netloc}"
        ).rstrip("/")

    @staticmethod
    def _same_domain(
        base_url: str,
        candidate: str,
    ) -> bool:
        base_host = (
            urlparse(base_url).hostname
            or ""
        ).lower()

        candidate_host = (
            urlparse(candidate).hostname
            or ""
        ).lower()

        if not base_host or not candidate_host:
            return False

        return (
            candidate_host == base_host
            or candidate_host.endswith(
                f".{base_host}"
            )
        )

    # =========================================================
    # Website crawler
    # =========================================================

    async def _crawl_website(
        self,
        domain: str,
    ) -> dict[str, Any]:
        """
        Collect facts directly available from the public website.

        This does NOT pretend to be an Ahrefs/Semrush backlink or
        ranking database.
        """

        base_url = self._normalize_domain(
            domain
        )

        visited: set[str] = set()
        queue: list[str] = [
            f"{base_url}/"
        ]

        pages: list[dict[str, Any]] = []

        total_internal_links = 0
        total_external_links = 0

        seen_words: set[str] = set()

        timeout = httpx.Timeout(
            connect=10.0,
            read=20.0,
            write=20.0,
            pool=20.0,
        )

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={
                "User-Agent": (
                    "BoostRankersBot/1.0 "
                    "(SEO competitor analysis)"
                )
            },
        ) as client:

            while (
                queue
                and len(pages) < self.MAX_PAGES
            ):
                current = queue.pop(0)

                normalized_url = (
                    current
                    .split("#", 1)[0]
                    .rstrip("/")
                    or current
                )

                if normalized_url in visited:
                    continue

                visited.add(
                    normalized_url
                )

                try:
                    response = await client.get(
                        normalized_url
                    )
                except httpx.HTTPError:
                    continue

                content_type = (
                    response.headers.get(
                        "content-type",
                        "",
                    )
                    .lower()
                )

                if (
                    "text/html"
                    not in content_type
                ):
                    continue

                soup = BeautifulSoup(
                    response.text,
                    "html.parser",
                )

                title = ""

                if soup.title:
                    title = soup.title.get_text(
                        " ",
                        strip=True,
                    )

                meta_description = ""

                meta = soup.find(
                    "meta",
                    attrs={
                        "name": re.compile(
                            r"^description$",
                            re.I,
                        )
                    },
                )

                if meta:
                    meta_description = (
                        meta.get(
                            "content",
                            "",
                        )
                        or ""
                    ).strip()

                canonical = ""

                canonical_tag = soup.find(
                    "link",
                    attrs={
                        "rel": lambda value: (
                            "canonical" in value
                            if isinstance(
                                value,
                                list,
                            )
                            else value
                            == "canonical"
                        )
                    },
                )

                if canonical_tag:
                    canonical = (
                        canonical_tag.get(
                            "href",
                            "",
                        )
                        or ""
                    ).strip()

                h1 = [
                    item.get_text(
                        " ",
                        strip=True,
                    )
                    for item in soup.find_all(
                        "h1"
                    )
                ]

                h2 = [
                    item.get_text(
                        " ",
                        strip=True,
                    )
                    for item in soup.find_all(
                        "h2"
                    )
                ]

                h3 = [
                    item.get_text(
                        " ",
                        strip=True,
                    )
                    for item in soup.find_all(
                        "h3"
                    )
                ]

                links: list[str] = []

                for anchor in soup.find_all(
                    "a",
                    href=True,
                )[: self.MAX_LINKS_PER_PAGE]:

                    href = str(
                        anchor.get(
                            "href",
                            "",
                        )
                    ).strip()

                    if not href:
                        continue

                    absolute = urljoin(
                        normalized_url,
                        href,
                    )

                    if not absolute.startswith(
                        (
                            "http://",
                            "https://",
                        )
                    ):
                        continue

                    links.append(
                        absolute.split(
                            "#",
                            1,
                        )[0]
                    )

                internal_links = [
                    link
                    for link in links
                    if self._same_domain(
                        base_url,
                        link,
                    )
                ]

                external_links = [
                    link
                    for link in links
                    if not self._same_domain(
                        base_url,
                        link,
                    )
                ]

                total_internal_links += len(
                    internal_links
                )

                total_external_links += len(
                    external_links
                )

                for link in internal_links:

                    if (
                        link not in visited
                        and link not in queue
                        and (
                            len(queue)
                            + len(visited)
                        )
                        < self.MAX_PAGES * 3
                    ):
                        queue.append(
                            link
                        )

                body = soup.get_text(
                    " ",
                    strip=True,
                )

                body = re.sub(
                    r"\s+",
                    " ",
                    body,
                ).strip()

                body = body[
                    : self.MAX_TEXT_LENGTH
                ]

                words = re.findall(
                    r"\b[a-zA-Z][a-zA-Z\-]{3,}\b",
                    body.lower(),
                )

                seen_words.update(
                    words
                )

                pages.append(
                    {
                        "url": str(
                            response.url
                        ),
                        "status_code": response.status_code,
                        "title": title,
                        "meta_description": meta_description,
                        "canonical": canonical,
                        "h1": h1[:10],
                        "h2": h2[:20],
                        "h3": h3[:20],
                        "internal_links": len(
                            internal_links
                        ),
                        "external_links": len(
                            external_links
                        ),
                        "word_count": len(
                            words
                        ),
                    }
                )

        metrics = {
            "internal_links": total_internal_links,
            "external_links": total_external_links,
            "unique_content_terms": len(
                seen_words
            ),
            "missing_title": sum(
                1
                for page in pages
                if not page["title"]
            ),
            "missing_meta_description": sum(
                1
                for page in pages
                if not page["meta_description"]
            ),
            "missing_h1": sum(
                1
                for page in pages
                if not page["h1"]
            ),
            "missing_canonical": sum(
                1
                for page in pages
                if not page["canonical"]
            ),
            "broken_links": 0,
        }

        return {
            "site": base_url,
            "pages_crawled": len(
                pages
            ),
            "pages": pages,
            "metrics": metrics,
            "data_availability": {
                "traffic": False,
                "ranking_keywords": False,
                "backlinks": False,
                "domain_authority": False,
                "keyword_gap": False,
            },
        }

    # =========================================================
    # Robust JSON parser
    # =========================================================

    @staticmethod
    def _parse_json(
        content: str,
    ) -> dict[str, Any]:
        """
        Parse a JSON object returned by Anthropic.

        Structured Outputs is the primary protection. This parser remains
        as a defensive fallback for older SDK/API configurations and for
        legacy records.
        """

        text = str(content or "").strip()

        if not text:
            raise ValueError(
                "Anthropic returned an empty response."
            )

        # Remove common markdown fences.
        fenced = re.findall(
            r"```(?:json)?\s*(.*?)```",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        candidates: list[str] = []

        for block in fenced:
            clean = block.strip()
            if clean:
                candidates.append(clean)

        candidates.append(text)

        # Also try the first JSON object embedded in surrounding prose.
        first_open = text.find("{")
        if first_open >= 0:
            decoder = json.JSONDecoder()
            try:
                parsed, _ = decoder.raw_decode(
                    text[first_open:]
                )
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass

        seen: set[str] = set()

        for candidate in candidates:
            candidate = candidate.strip()

            if not candidate or candidate in seen:
                continue

            seen.add(candidate)

            # Handle responses such as: json\n{...}
            candidate = re.sub(
                r"^\s*json\s*(?=\{)",
                "",
                candidate,
                flags=re.IGNORECASE,
            ).strip()

            try:
                parsed = json.loads(candidate)

                if isinstance(parsed, dict):
                    return parsed

            except (
                json.JSONDecodeError,
                TypeError,
            ):
                continue

        preview = (
            text[:1000]
            .replace("\r", " ")
            .replace("\n", " ")
        )

        raise ValueError(
            "Anthropic returned invalid JSON. "
            f"Response preview: {preview}"
        )

    @staticmethod
    def _strategy_schema() -> dict[str, Any]:
        """
        JSON Schema used with Anthropic Structured Outputs.

        Every object explicitly disables additional properties because
        Anthropic Structured Outputs requires that for object schemas.
        """
        string_array = {
            "type": "array",
            "items": {"type": "string"},
        }

        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "executive_summary": {"type": "string"},
                "competitive_position": {"type": "string"},
                "strengths": string_array,
                "weaknesses": string_array,
                "content_gaps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "topic": {"type": "string"},
                            "reason": {"type": "string"},
                            "priority": {"type": "string"},
                            "recommended_asset": {"type": "string"},
                        },
                        "required": [
                            "topic",
                            "reason",
                            "priority",
                            "recommended_asset",
                        ],
                    },
                },
                "keyword_strategy": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "target_terms": string_array,
                        "long_tail_opportunities": string_array,
                        "intent_clusters": string_array,
                        "gap_status": {"type": "string"},
                    },
                    "required": [
                        "target_terms",
                        "long_tail_opportunities",
                        "intent_clusters",
                        "gap_status",
                    ],
                },
                "technical_strategy": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "issue": {"type": "string"},
                            "impact": {"type": "string"},
                            "recommendation": {"type": "string"},
                            "priority": {"type": "string"},
                        },
                        "required": [
                            "issue",
                            "impact",
                            "recommendation",
                            "priority",
                        ],
                    },
                },
                "local_seo_strategy": string_array,
                "serp_strategy": string_array,
                "backlink_strategy": string_array,
                "ai_search_strategy": string_array,
                "conversion_strategy": string_array,
                "quick_wins": string_array,
                "action_plan": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "days_0_30": string_array,
                        "days_31_60": string_array,
                        "days_61_90": string_array,
                    },
                    "required": [
                        "days_0_30",
                        "days_31_60",
                        "days_61_90",
                    ],
                },
                "kpis": string_array,
            },
            "required": [
                "executive_summary",
                "competitive_position",
                "strengths",
                "weaknesses",
                "content_gaps",
                "keyword_strategy",
                "technical_strategy",
                "local_seo_strategy",
                "serp_strategy",
                "backlink_strategy",
                "ai_search_strategy",
                "conversion_strategy",
                "quick_wins",
                "action_plan",
                "kpis",
            ],
        }

    # =========================================================
    # Strategy generation
    # =========================================================

    async def _generate_strategy(
        self,
        company: Company,
        competitor_domain: str,
        target_domain: str | None,
        website_data: dict[str, Any],
    ) -> dict[str, Any]:

        client, model = (
            self._create_client(
                company
            )
        )

        target_text = (
            target_domain
            or "Not provided"
        )

        prompt = f"""
You are a senior SEO competitive-intelligence strategist.

COMPETITOR
{competitor_domain}

TARGET WEBSITE
{target_text}

DIRECT WEBSITE EVIDENCE
{json.dumps(
    website_data,
    ensure_ascii=False,
)}

Produce a professional competitive SEO strategy.

IMPORTANT DATA POLICY:
- Never invent verified organic traffic.
- Never invent ranking keyword counts.
- Never invent backlink counts.
- Never invent Domain Authority.
- Never claim a measured keyword gap unless a connected SEO data
  provider supplied that data.
- Use only the supplied website evidence for factual observations.
- Clearly distinguish direct evidence from strategic inference.
- The target website was supplied for strategic positioning, not as
  evidence that you crawled it.
- Do not claim that a page, metric, backlink, ranking or technical
  condition was verified unless it exists in the supplied evidence.

OUTPUT QUALITY:
- Keep the executive summary concise but useful.
- Keep lists focused and actionable; normally 3-7 items per list.
- Keep each recommendation concise enough to fit a production dashboard.
- Make the 30/60/90-day plan specific and executable.
- KPIs must be measurable without pretending that unavailable
  third-party metrics are verified.

Return the requested structured object only.
""".strip()

        schema = self._strategy_schema()

        async def request_strategy(
            max_tokens: int,
        ) -> tuple[dict[str, Any], str]:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=(
                    "You are a senior SEO competitive-intelligence "
                    "strategist. Follow the supplied structured output "
                    "schema exactly. Never fabricate SEO metrics."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": schema,
                    }
                },
            )

            stop_reason = str(
                getattr(
                    response,
                    "stop_reason",
                    "",
                )
                or ""
            )

            text_parts: list[str] = []

            for block in response.content:
                if getattr(
                    block,
                    "type",
                    None,
                ) != "text":
                    continue

                block_text = getattr(
                    block,
                    "text",
                    None,
                )

                if block_text:
                    text_parts.append(
                        str(block_text)
                    )

            content = "\n".join(
                text_parts
            ).strip()

            if stop_reason == "refusal":
                raise ValueError(
                    "Anthropic refused to generate the competitor strategy."
                )

            if stop_reason == "max_tokens":
                raise RuntimeError(
                    "Anthropic reached the output token limit before "
                    "completing the competitor strategy."
                )

            strategy = self._parse_json(
                content
            )

            return strategy, stop_reason

        try:
            # Structured Outputs prevents the exact malformed JSON problem
            # currently shown in the Uvicorn traceback.
            try:
                strategy, _ = await request_strategy(
                    max_tokens=9000
                )
            except RuntimeError as exc:
                # A long strategy can still hit the output ceiling. Retry
                # once with a larger budget instead of returning a 502.
                if "output token limit" not in str(exc).lower():
                    raise

                strategy, _ = await request_strategy(
                    max_tokens=14000
                )

            if not strategy.get(
                "executive_summary"
            ):
                strategy["executive_summary"] = (
                    "Competitive analysis completed."
                )

            # Strategy generation consumes one AI credit only after a
            # complete successful provider response has been received.
            company.ai_credits -= 1
            self.db.commit()

            return strategy

        except AuthenticationError:
            self.db.rollback()

            raise ValueError(
                "Anthropic rejected the API key while generating "
                "the competitive strategy. Please update the key in Settings."
            )

        except RateLimitError:
            self.db.rollback()

            raise ValueError(
                "Anthropic usage quota or rate limit was reached. "
                "Please check your billing and usage."
            )

        except APIConnectionError:
            self.db.rollback()

            raise ValueError(
                "Could not connect to Anthropic. Please try again."
            )

        except APIStatusError as exc:
            self.db.rollback()

            status_code = getattr(
                exc,
                "status_code",
                None,
            )

            if status_code == 402:
                raise ValueError(
                    "Anthropic billing is required for competitor strategy generation."
                )

            if status_code == 403:
                raise ValueError(
                    "Anthropic rejected the request because the account "
                    "or API key lacks permission."
                )

            if status_code == 404:
                raise ValueError(
                    f"The configured Anthropic model '{model}' is unavailable."
                )

            raise ValueError(
                "Anthropic returned an error while generating "
                "the competitive strategy."
            )

        except ValueError as exc:
            self.db.rollback()

            print(
                "Competitor strategy parsing failed:",
                str(exc),
            )

            raise

        except RuntimeError as exc:
            self.db.rollback()

            print(
                "Competitor strategy output failed:",
                str(exc),
            )

            raise ValueError(
                "Anthropic could not complete the competitor strategy. "
                "Please try again."
            )

        except Exception as exc:
            self.db.rollback()

            print(
                "Competitor strategy generation failed:",
                str(exc),
            )

            raise ValueError(
                "The competitive strategy could not be generated."
            )

    # =========================================================
    # Add competitor
    # =========================================================

    async def add_competitor(
        self,
        domain: str,
        company: Company,
        target_domain: str | None = None,
    ) -> Competitor:

        competitor_domain = (
            self._normalize_domain(
                domain
            )
        )

        normalized_target = None

        if target_domain:
            normalized_target = (
                self._normalize_domain(
                    target_domain
                )
            )

            if (
                normalized_target
                == competitor_domain
            ):
                raise ValueError(
                    "Target website and competitor website must be different."
                )

        if company.ai_credits <= 0:
            raise ValueError(
                "Insufficient AI credits. Please add budget."
            )

        # -----------------------------------------------------
        # Crawl competitor
        # -----------------------------------------------------

        website_data = (
            await self._crawl_website(
                competitor_domain
            )
        )

        # -----------------------------------------------------
        # Generate strategy
        # -----------------------------------------------------

        strategy = (
            await self._generate_strategy(
                company=company,
                competitor_domain=competitor_domain,
                target_domain=normalized_target,
                website_data=website_data,
            )
        )

        # -----------------------------------------------------
        # We intentionally DO NOT fabricate these values.
        # -----------------------------------------------------

        traffic = "Not connected"
        keywords = 0
        backlinks = 0
        da = 0
        gap = 0

        details = {
            "version": 2,
            "competitor": {
                "domain": competitor_domain,
            },
            "target": {
                "domain": normalized_target,
            },
            "verified_metrics": {
                "traffic": None,
                "ranking_keywords": None,
                "backlinks": None,
                "domain_authority": None,
                "keyword_gap": None,
            },
            "website_evidence": website_data,
            "strategy": strategy,
        }

        serialized_details = json.dumps(
            details,
            ensure_ascii=False,
        )

        competitor = Competitor(
            company_id=company.id,
            domain=competitor_domain,
            traffic=traffic,
            keywords=keywords,
            backlinks=backlinks,
            da=da,
            gap=gap,
            analysis=serialized_details,
        )

        self.db.add(
            competitor
        )

        self.db.commit()
        self.db.refresh(
            competitor
        )

        return competitor

    # =========================================================
    # Structured analysis helper
    # =========================================================

    @staticmethod
    def parse_details(
        analysis: str | None,
    ) -> dict[str, Any]:
        if not analysis:
            return {}

        try:
            parsed = json.loads(
                analysis
            )

            if isinstance(
                parsed,
                dict,
            ):
                return parsed

        except (
            json.JSONDecodeError,
            TypeError,
        ):
            pass

        # Support old records containing plain text.
        return {
            "version": 1,
            "strategy": {
                "executive_summary": analysis,
                "competitive_position": "",
                "strengths": [],
                "weaknesses": [],
                "content_gaps": [],
                "keyword_strategy": {
                    "target_terms": [],
                    "long_tail_opportunities": [],
                    "intent_clusters": [],
                    "gap_status": (
                        "legacy_record"
                    ),
                },
                "technical_strategy": [],
                "local_seo_strategy": [],
                "serp_strategy": [],
                "backlink_strategy": [],
                "ai_search_strategy": [],
                "conversion_strategy": [],
                "quick_wins": [],
                "action_plan": {
                    "days_0_30": [],
                    "days_31_60": [],
                    "days_61_90": [],
                },
                "kpis": [],
            },
        }