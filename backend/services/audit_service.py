from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from anthropic import (
    APIConnectionError,
    APIStatusError,
    AsyncAnthropic,
    AuthenticationError,
    RateLimitError,
)

from sqlalchemy.orm import Session

from config import settings
from models.audit import Audit, AuditStatus
from models.company import Company
from models.user import User


logger = logging.getLogger(__name__)


class AuditService:
    """
    Production audit orchestration service.

    Responsibilities:
    - Validate application AI credits.
    - Validate Anthropic configuration before consuming credits.
    - Distinguish invalid API keys from billing/quota/rate-limit failures.
    - Create and persist Audit records.
    - Stream SSE progress to the frontend.
    - Stop immediately when the Anthropic provider is unavailable.
    - Execute all configured SEO agents.
    - Persist progress using Audit.progress_percentage.
    - Finalize the audit safely.
    - Generate the final report.
    """

    def __init__(self, db: Session):
        self.db = db

    # =========================================================
    # SSE
    # =========================================================

    @staticmethod
    def _sse(payload: dict[str, Any]) -> str:
        """
        Convert a dictionary into a valid SSE event.
        """
        return f"data: {json.dumps(payload, default=str)}\n\n"

    # =========================================================
    # DB helpers
    # =========================================================

    def _safe_commit(self) -> None:
        """
        Commit the current transaction safely.
        """
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _safe_rollback(self) -> None:
        try:
            self.db.rollback()
        except Exception:
            logger.exception("Database rollback failed.")

    # =========================================================
    # Provider configuration
    # =========================================================

    @staticmethod
    def _get_api_key(company: Company) -> str | None:
        """
        Resolve the Anthropic API key.

        Company-specific key has priority over the global key.
        """
        company_key = getattr(company, "anthropic_api_key", None)

        if company_key:
            company_key = str(company_key).strip()

        if company_key:
            return company_key

        global_key = getattr(settings, "ANTHROPIC_API_KEY", None)

        if global_key:
            global_key = str(global_key).strip()

        return global_key or None

    @staticmethod
    def _get_model_name() -> str:
        """
        Prefer explicit configuration.

        Set ANTHROPIC_MODEL in .env/settings so the deployed
        application does not depend on a hard-coded model.
        """
        configured = getattr(settings, "ANTHROPIC_MODEL", None)

        if configured:
            return str(configured).strip()

        # Fallback retained for existing installations.
        return "claude-sonnet-4-20250514"

    # =========================================================
    # Provider error classification
    # =========================================================

    @staticmethod
    def _classify_anthropic_error(exc: Exception) -> tuple[str, str, bool]:
        """
        Return:
            (error_code, user_message, retryable)
        """

        if isinstance(exc, APIStatusError):
            status_code = getattr(exc, "status_code", None)

            body = getattr(exc, "body", None)

            provider_message = str(exc)

            if isinstance(body, dict):
                error = body.get("error")

                if isinstance(error, dict):
                    provider_message = str(
                        error.get(
                            "message",
                            provider_message,
                        )
                    )

            normalized_message = provider_message.lower()

            billing_markers = (
                "credit balance is too low",
                "insufficient credits",
                "purchase credits",
                "plans & billing",
                "upgrade or purchase credits",
                "billing",
            )

            if any(
                marker in normalized_message
                for marker in billing_markers
            ):
                return (
                    "billing_required",
                    (
                        "Anthropic AI is unavailable because the "
                        "Anthropic credit balance is too low. "
                        "Please add credits or upgrade your Anthropic "
                        "plan, then run the audit again."
                    ),
                    True,
                )

            if status_code == 402:
                return (
                    "billing_required",
                    (
                        "Anthropic billing is required. "
                        "Please add credits or update your billing."
                    ),
                    True,
                )

            if status_code == 403:
                return (
                    "provider_forbidden",
                    (
                        "The Anthropic account or API key does not "
                        "have permission to perform this request."
                    ),
                    False,
                )

            if status_code == 429:
                return (
                    "rate_limit_or_quota",
                    (
                        "Anthropic usage quota or rate limit was reached. "
                        "Please try again later or check billing."
                    ),
                    True,
                )

            if status_code and status_code >= 500:
                return (
                    "provider_server_error",
                    "Anthropic is temporarily unavailable. Please try again.",
                    True,
                )

            return (
                "provider_error",
                f"Anthropic error: {provider_message}",
                True,
            )

        if isinstance(exc, AuthenticationError):
            return (
                "invalid_api_key",
                (
                    "Anthropic rejected the API key. "
                    "Please open Settings and enter a valid Anthropic API key."
                ),
                False,
            )

        if isinstance(exc, RateLimitError):
            return (
                "rate_limit_or_quota",
                (
                    "Anthropic is currently limiting this API request or "
                    "the account has reached its usage quota. "
                    "Please check your Anthropic usage and billing, then try again."
                ),
                True,
            )

        if isinstance(exc, APIConnectionError):
            return (
                "provider_connection_error",
                (
                    "The application could not connect to Anthropic. "
                    "Please check your internet connection and try again."
                ),
                True,
            )

        if isinstance(exc, APIStatusError):
            status_code = getattr(exc, "status_code", None)

            if status_code == 402:
                return (
                    "provider_billing",
                    (
                        "Anthropic billing is required before this AI audit "
                        "can run. Please add funds or update your Anthropic "
                        "billing, then try again."
                    ),
                    True,
                )

            if status_code == 403:
                return (
                    "provider_forbidden",
                    (
                        "The Anthropic account is not permitted to use this "
                        "API request. Please check the API key, workspace, "
                        "permissions, and billing settings."
                    ),
                    False,
                )

            if status_code and status_code >= 500:
                return (
                    "provider_server_error",
                    (
                        "Anthropic is temporarily unavailable. "
                        "Please try again shortly."
                    ),
                    True,
                )

        return (
            "provider_error",
            (
                "Anthropic could not process the AI request. "
                f"Provider error: {str(exc)}"
            ),
            True,
        )

    # =========================================================
    # Provider preflight
    # =========================================================

    async def _check_anthropic_availability(
        self,
        client: AsyncAnthropic,
        model: str,
    ) -> tuple[bool, str, str | None, bool]:
        """
        Perform a minimal Anthropic request before creating the audit.

        Returns:
            available,
            user_message,
            error_code,
            retryable
        """

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=8,
                system=(
                    "You are a health-check endpoint for an SEO application. "
                    "Reply with exactly: OK"
                ),
                messages=[
                    {
                        "role": "user",
                        "content": "Reply with OK.",
                    }
                ],
            )

            if not response:
                return (
                    False,
                    "Anthropic returned an empty health-check response.",
                    "provider_empty_response",
                    True,
                )

            return True, "", None, False

        except Exception as exc:
            code, message, retryable = self._classify_anthropic_error(exc)

            logger.warning(
                "Anthropic preflight failed: code=%s retryable=%s error=%s",
                code,
                retryable,
                exc,
            )

            return False, message, code, retryable

    # =========================================================
    # Agent configuration
    # =========================================================

    @staticmethod
    def _agents() -> list[dict[str, str]]:
        return [
            {
                "name": "Technical SEO Agent",
                "prompt": (
                    "Analyze the site's technical SEO, including "
                    "crawlability, indexability, canonical tags, redirects, "
                    "sitemap, robots.txt, HTTP status handling, and Core Web "
                    "Vitals. Provide 3 important findings."
                ),
            },
            {
                "name": "Content SEO Agent",
                "prompt": (
                    "Analyze content quality, keyword usage, headings, "
                    "readability, thin content, duplicate content, topical "
                    "coverage, and content depth. Provide 3 important findings."
                ),
            },
            {
                "name": "Local SEO Agent",
                "prompt": (
                    "Analyze local search presence including NAP "
                    "consistency, Google Business Profile, citations, "
                    "reviews, local landing pages, and local keyword "
                    "targeting. Provide 3 important findings."
                ),
            },
            {
                "name": "Schema Agent",
                "prompt": (
                    "Analyze structured data and schema.org implementation. "
                    "Identify missing schemas, invalid schemas, rich-result "
                    "opportunities, and entity relationships. Provide 3 "
                    "important findings."
                ),
            },
            {
                "name": "EEAT Agent",
                "prompt": (
                    "Analyze Experience, Expertise, Authoritativeness, and "
                    "Trust signals including author information, contact "
                    "details, policies, references, credentials, and trust "
                    "elements. Provide 3 important findings."
                ),
            },
            {
                "name": "Internal Linking Agent",
                "prompt": (
                    "Analyze internal linking structure, orphan pages, "
                    "click depth, anchor text distribution, topical "
                    "relationships, and link equity flow. Provide 3 important "
                    "findings."
                ),
            },
            {
                "name": "Competitor Agent",
                "prompt": (
                    "Analyze competitive SEO opportunities including keyword "
                    "gaps, content gaps, backlink gaps, SERP weaknesses, and "
                    "authority differences. Provide 3 important findings."
                ),
            },
            {
                "name": "Backlink Agent",
                "prompt": (
                    "Analyze backlink profile quality, referring domains, "
                    "anchor text diversity, authority, relevance, and "
                    "potential toxic-link patterns. Provide 3 important findings."
                ),
            },
            {
                "name": "AI Search Agent",
                "prompt": (
                    "Analyze AI-search readiness including entity signals, "
                    "semantic coverage, answer-engine optimization, "
                    "machine-readable information, and visibility in AI "
                    "search experiences. Provide 3 important findings."
                ),
            },
            {
                "name": "Reporting Agent",
                "prompt": (
                    "Compile the audit findings into an executive-level "
                    "summary. Highlight the most important problems, "
                    "priorities, opportunities, and recommended next actions. "
                    "Provide a 5-point summary."
                ),
            },
        ]

    # =========================================================
    # Main audit
    # =========================================================

    async def run_audit(
        self,
        url: str,
        user: User,
        company: Company,
        request: Any = None,
    ) -> AsyncGenerator[str, None]:

        audit: Audit | None = None
        results: list[dict[str, Any]] = []

        agents = self._agents()
        total_agents = len(agents)

        try:
            # -------------------------------------------------
            # Validate application credits
            # -------------------------------------------------

            ai_credits = int(getattr(company, "ai_credits", 0) or 0)

            if ai_credits <= 0:
                yield self._sse(
                    {
                        "type": "billing_required",
                        "source": "application",
                        "message": (
                            "You do not have enough AI credits to run "
                            "this audit. Please add AI credits or upgrade "
                            "your Boost Rankers plan."
                        ),
                        "retryable": False,
                    }
                )
                return

            # -------------------------------------------------
            # Validate API key before consuming app credit
            # -------------------------------------------------

            api_key = self._get_api_key(company)

            if not api_key:
                yield self._sse(
                    {
                        "type": "ai_provider_unavailable",
                        "code": "missing_api_key",
                        "message": (
                            "Anthropic AI is not configured. "
                            "Please add a valid Anthropic API key in Settings."
                        ),
                        "retryable": False,
                    }
                )
                return

            model = self._get_model_name()

            # -------------------------------------------------
            # Create Anthropic client
            # -------------------------------------------------

            client = AsyncAnthropic(
                api_key=api_key,
            )

            # -------------------------------------------------
            # Provider preflight BEFORE consuming credit
            # -------------------------------------------------

            (
                provider_available,
                provider_message,
                provider_error_code,
                provider_retryable,
            ) = await self._check_anthropic_availability(
                client,
                model,
            )

            if not provider_available:
                yield self._sse(
                    {
                        "type": "ai_provider_unavailable",
                        "code": provider_error_code,
                        "message": provider_message,
                        "retryable": provider_retryable,
                    }
                )
                return

            # -------------------------------------------------
            # Client disconnect check
            # -------------------------------------------------

            if request is not None:
                try:
                    if await request.is_disconnected():
                        return
                except Exception:
                    pass

            # -------------------------------------------------
            # NOW consume one application AI credit
            # -------------------------------------------------

            company.ai_credits = ai_credits - 1
            self._safe_commit()

            # -------------------------------------------------
            # Create audit record
            # -------------------------------------------------

            audit = Audit(
                website=url,
                company_id=company.id,
                user_id=user.id,
                status=AuditStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
                progress_percentage=0,
            )

            self.db.add(audit)
            self._safe_commit()
            self.db.refresh(audit)

            # -------------------------------------------------
            # Initial SSE event
            # -------------------------------------------------

            yield self._sse(
                {
                    "type": "started",
                    "audit_id": str(audit.id),
                    "total_agents": total_agents,
                    "completed_agents": 0,
                    "progress": 0,
                    "message": "Audit started successfully.",
                }
            )

            await asyncio.sleep(0)

            # -------------------------------------------------
            # Agent loop
            # -------------------------------------------------

            for idx, agent in enumerate(agents):

                # Check client disconnect
                if request is not None:
                    try:
                        if await request.is_disconnected():
                            logger.info(
                                "Client disconnected during audit %s",
                                audit.id,
                            )
                            return
                    except Exception:
                        pass

                # Current agent progress BEFORE execution
                progress = int(
                    (idx / total_agents) * 100
                )

                audit.current_stage = agent["name"]
                audit.current_task = agent["prompt"]
                audit.progress_percentage = progress

                try:
                    self._safe_commit()
                except Exception:
                    self._safe_rollback()
                    raise

                yield self._sse(
                    {
                        "type": "agent_start",
                        "agent": agent["name"],
                        "agent_index": idx,
                        "total_agents": total_agents,
                        "completed_agents": idx,
                        "progress": progress,
                    }
                )

                await asyncio.sleep(0)

                # -------------------------------------------------
                # Execute Claude agent
                # -------------------------------------------------

                try:
                    response = await client.messages.create(
                        model=model,
                        max_tokens=1200,
                        system=(
                            "You are an expert SEO auditing agent. "
                            "Return ONLY valid JSON in this exact shape: "
                            "{\"findings\": [\"...\"], \"score\": 0}. "
                            "The score must be an integer between 0 and 100. "
                            "Findings must be concise, evidence-based, and "
                            "actionable. Do not invent technical facts that "
                            "cannot be inferred from the provided information."
                        ),
                        messages=[
                            {
                                "role": "user",
                                "content": (
                                    f"Website URL: {url}\n\n"
                                    f"Specialist: {agent['name']}\n\n"
                                    f"Task: {agent['prompt']}\n\n"
                                    "Return JSON only."
                                ),
                            }
                        ],
                    )

                    content_parts: list[str] = []

                    for block in response.content:
                        if getattr(block, "type", None) == "text":
                            content_parts.append(block.text)

                    content = "".join(content_parts).strip()

                    if not content:
                        raise RuntimeError(
                            "Anthropic returned an empty response."
                        )

                    # ---------------------------------------------
                    # Parse structured result
                    # ---------------------------------------------

                    try:
                        parsed = json.loads(content)

                        findings = parsed.get(
                            "findings",
                            [],
                        )

                        score = parsed.get(
                            "score",
                            50,
                        )

                        if not isinstance(findings, list):
                            findings = [str(findings)]

                        findings = [
                            str(item).strip()
                            for item in findings
                            if str(item).strip()
                        ]

                        if not findings:
                            findings = [
                                "No specific findings were returned."
                            ]

                        score = int(score)
                        score = max(0, min(100, score))

                    except (
                        json.JSONDecodeError,
                        TypeError,
                        ValueError,
                    ):
                        # Graceful fallback when Claude returns text.
                        findings = [
                            content[:2000]
                        ]
                        score = 50

                    # ---------------------------------------------
                    # Stream findings
                    # ---------------------------------------------

                    for finding in findings:
                        yield self._sse(
                            {
                                "type": "log",
                                "agent": agent["name"],
                                "message": finding,
                            }
                        )

                        await asyncio.sleep(0)

                    results.append(
                        {
                            "agent": agent["name"],
                            "findings": findings,
                            "score": score,
                        }
                    )

                    # ---------------------------------------------
                    # Completed agent
                    # ---------------------------------------------

                    completed_agents = idx + 1

                    progress = int(
                        (completed_agents / total_agents) * 100
                    )

                    audit.progress_percentage = progress
                    audit.current_stage = agent["name"]
                    audit.current_task = "Completed"

                    try:
                        self._safe_commit()
                    except Exception:
                        self._safe_rollback()
                        raise

                    yield self._sse(
                        {
                            "type": "agent_complete",
                            "agent": agent["name"],
                            "agent_index": idx,
                            "total_agents": total_agents,
                            "completed_agents": completed_agents,
                            "progress": progress,
                            "score": score,
                        }
                    )

                except AuthenticationError as exc:
                    # -------------------------------------------------
                    # INVALID API KEY
                    # Stop immediately. Do NOT execute remaining agents.
                    # -------------------------------------------------

                    code, message, retryable = (
                        self._classify_anthropic_error(exc)
                    )

                    logger.error(
                        "Anthropic authentication failed during audit %s",
                        getattr(audit, "id", None),
                    )

                    if audit is not None:
                        audit.status = AuditStatus.FAILED
                        audit.error_message = message
                        audit.current_task = "Anthropic authentication failed"

                        try:
                            self._safe_commit()
                        except Exception:
                            self._safe_rollback()

                    yield self._sse(
                        {
                            "type": "provider_error",
                            "code": code,
                            "agent": agent["name"],
                            "message": message,
                            "retryable": retryable,
                            "audit_id": str(audit.id) if audit else None,
                        }
                    )

                    return

                except RateLimitError as exc:
                    # -------------------------------------------------
                    # QUOTA / RATE LIMIT
                    # Stop immediately.
                    # -------------------------------------------------

                    code, message, retryable = (
                        self._classify_anthropic_error(exc)
                    )

                    logger.warning(
                        "Anthropic rate limit/quota during audit %s",
                        getattr(audit, "id", None),
                    )

                    if audit is not None:
                        audit.status = AuditStatus.FAILED
                        audit.error_message = message
                        audit.current_task = "Anthropic quota/rate limit"

                        try:
                            self._safe_commit()
                        except Exception:
                            self._safe_rollback()

                    yield self._sse(
                        {
                            "type": "provider_error",
                            "code": code,
                            "agent": agent["name"],
                            "message": message,
                            "retryable": retryable,
                            "audit_id": str(audit.id) if audit else None,
                        }
                    )

                    return

                except Exception as exc:
                    # -------------------------------------------------
                    # Other agent-specific error
                    # -------------------------------------------------

                    logger.exception(
                        "Audit agent failed: %s",
                        agent["name"],
                    )

                    error_message = str(exc)

                    findings = [
                        f"Agent error: {error_message}"
                    ]

                    results.append(
                        {
                            "agent": agent["name"],
                            "findings": findings,
                            "score": 0,
                        }
                    )

                    # Don't kill the entire audit for one ordinary
                    # agent failure.
                    yield self._sse(
                        {
                            "type": "agent_error",
                            "agent": agent["name"],
                            "message": error_message,
                            "progress": int(
                                ((idx + 1) / total_agents) * 100
                            ),
                        }
                    )

                    audit.current_task = (
                        f"{agent['name']} failed; continuing audit"
                    )

                    audit.progress_percentage = int(
                        ((idx + 1) / total_agents) * 100
                    )

                    try:
                        self._safe_commit()
                    except Exception:
                        self._safe_rollback()
                        raise

            # -------------------------------------------------
            # Final score
            # -------------------------------------------------

            average_score = (
                sum(
                    float(result["score"])
                    for result in results
                )
                / len(results)
                if results
                else 0.0
            )

            average_score = round(
                max(0.0, min(100.0, average_score)),
                2,
            )

            # -------------------------------------------------
            # Complete audit
            # -------------------------------------------------

            audit.status = AuditStatus.COMPLETED
            audit.completed_at = datetime.now(timezone.utc)
            audit.progress_percentage = 100
            audit.overall_score = average_score
            audit.current_stage = "Completed"
            audit.current_task = "Audit completed successfully"

            started_at = audit.started_at

            if started_at:
                duration = (
                    datetime.now(timezone.utc) - started_at
                ).total_seconds()

                if hasattr(audit, "duration_seconds"):
                    try:
                        # Only write when the model attribute is
                        # actually writable.
                        audit.duration_seconds = int(
                            max(0, duration)
                        )
                    except Exception:
                        logger.warning(
                            "Could not persist duration_seconds."
                        )

            self._safe_commit()

            # -------------------------------------------------
            # Generate report
            # -------------------------------------------------

            report_warning: str | None = None

            try:
                from services.report_service import ReportService

                report_service = ReportService(self.db)

                report_service.generate_report_from_audit(
                    audit
                )

            except Exception as exc:
                logger.exception(
                    "Report generation failed for audit %s",
                    audit.id,
                )

                report_warning = (
                    "Audit completed, but report generation failed. "
                    f"Reason: {exc}"
                )

                yield self._sse(
                    {
                        "type": "warning",
                        "message": report_warning,
                    }
                )

            # -------------------------------------------------
            # Final event
            # -------------------------------------------------

            yield self._sse(
                {
                    "type": "complete",
                    "audit_id": str(audit.id),
                    "completed_agents": total_agents,
                    "total_agents": total_agents,
                    "progress": 100,
                    "score": average_score,
                    "results": results,
                    "report_warning": report_warning,
                }
            )

        except asyncio.CancelledError:
            logger.info(
                "Audit stream cancelled. audit=%s",
                getattr(audit, "id", None),
            )

            if audit is not None:
                audit.status = AuditStatus.CANCELLED
                audit.current_task = "Audit cancelled"

                try:
                    self._safe_commit()
                except Exception:
                    self._safe_rollback()

            raise

        except Exception as exc:
            # -----------------------------------------------------
            # Unexpected audit-level failure
            # -----------------------------------------------------

            logger.exception(
                "Unhandled audit streaming error."
            )

            if audit is not None:
                audit.status = AuditStatus.FAILED
                audit.error_message = str(exc)
                audit.current_task = "Audit failed"

                try:
                    self._safe_commit()
                except Exception:
                    self._safe_rollback()

            yield self._sse(
                {
                    "type": "error",
                    "message": (
                        "Audit failed unexpectedly. "
                        f"Reason: {exc}"
                    ),
                    "audit_id": str(audit.id) if audit else None,
                }
            )
