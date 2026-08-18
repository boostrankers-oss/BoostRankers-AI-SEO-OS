from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from models.audit import Audit


class ReportBuilder:
    """
    Build a complete Markdown SEO report from a completed Audit
    and the actual results returned by the audit agents.
    """

    AGENT_ORDER = [
        "Technical SEO Agent",
        "Content SEO Agent",
        "Local SEO Agent",
        "Schema Agent",
        "EEAT Agent",
        "Internal Linking Agent",
        "Competitor Agent",
        "Backlink Agent",
        "AI Search Agent",
        "Reporting Agent",
    ]

    @staticmethod
    def _safe(value: Any, default: str = "") -> str:
        if value is None:
            return default

        if isinstance(value, str):
            return value.strip()

        return str(value)

    @staticmethod
    def _extract_findings(result: Any) -> list[str]:
        """
        Normalize common audit-agent result structures into findings.
        """

        if result is None:
            return []

        if isinstance(result, dict):
            findings = result.get("findings")

            if isinstance(findings, list):
                return [
                    str(item).strip()
                    for item in findings
                    if str(item).strip()
                ]

            if isinstance(findings, str) and findings.strip():
                return [findings.strip()]

            # Some implementations may return nested data.
            for key in ("result", "content", "output", "response"):
                nested = result.get(key)

                if isinstance(nested, dict):
                    nested_findings = ReportBuilder._extract_findings(
                        nested
                    )

                    if nested_findings:
                        return nested_findings

                if isinstance(nested, str) and nested.strip():
                    parsed = ReportBuilder._parse_json_text(nested)

                    if parsed:
                        parsed_findings = ReportBuilder._extract_findings(
                            parsed
                        )

                        if parsed_findings:
                            return parsed_findings

                    return [nested.strip()]

            return []

        if isinstance(result, list):
            output: list[str] = []

            for item in result:
                if isinstance(item, str) and item.strip():
                    output.append(item.strip())

                elif isinstance(item, dict):
                    output.extend(
                        ReportBuilder._extract_findings(item)
                    )

            return output

        if isinstance(result, str):
            text = result.strip()

            if not text:
                return []

            parsed = ReportBuilder._parse_json_text(text)

            if parsed is not None:
                return ReportBuilder._extract_findings(parsed)

            return [text]

        return []

    @staticmethod
    def _extract_score(result: Any) -> float | None:
        if isinstance(result, dict):
            value = result.get("score")

            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass

            for key in ("result", "data", "output"):
                nested = result.get(key)

                nested_score = ReportBuilder._extract_score(
                    nested
                )

                if nested_score is not None:
                    return nested_score

        return None

    @staticmethod
    def _parse_json_text(value: str) -> Any | None:
        """
        Parse normal JSON responses and fenced ```json responses.
        """

        text = value.strip()

        if not text:
            return None

        candidates = [text]

        if text.startswith("```"):
            lines = text.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            candidates.append("\n".join(lines).strip())

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except (json.JSONDecodeError, TypeError):
                continue

        return None

    @classmethod
    def _normalize_results(
        cls,
        results: Any,
    ) -> dict[str, dict[str, Any]]:
        """
        Convert the audit result container into:

        {
            "Technical SEO Agent": {
                "score": 42,
                "findings": [...]
            }
        }
        """

        normalized: dict[str, dict[str, Any]] = {}

        if results is None:
            return normalized

        if isinstance(results, dict):
            for key, value in results.items():
                agent_name = str(key)

                normalized[agent_name] = {
                    "score": cls._extract_score(value),
                    "findings": cls._extract_findings(value),
                    "raw": value,
                }

            return normalized

        if isinstance(results, list):
            for item in results:
                if not isinstance(item, dict):
                    continue

                agent_name = (
                    item.get("agent")
                    or item.get("name")
                    or item.get("agent_name")
                )

                if not agent_name:
                    continue

                normalized[str(agent_name)] = {
                    "score": cls._extract_score(item),
                    "findings": cls._extract_findings(item),
                    "raw": item,
                }

        return normalized

    @classmethod
    def build_markdown(
        cls,
        audit: Audit,
        results: Any | None = None,
    ) -> tuple[str, str]:
        """
        Return:
            markdown_content,
            executive_summary
        """

        normalized = cls._normalize_results(results)

        score = float(audit.overall_score or 0)

        critical = int(
            getattr(audit, "critical_issues", 0) or 0
        )

        high = int(
            getattr(audit, "high_priority_issues", 0) or 0
        )

        medium = int(
            getattr(audit, "medium_priority_issues", 0) or 0
        )

        low = int(
            getattr(audit, "low_priority_issues", 0) or 0
        )

        issue_count = (
            critical
            + high
            + medium
            + low
        )

        completed_at = getattr(
            audit,
            "completed_at",
            None,
        )

        if isinstance(completed_at, datetime):
            audit_date = completed_at.astimezone(
                timezone.utc
            ).strftime("%d %B %Y, %H:%M UTC")
        else:
            audit_date = datetime.now(
                timezone.utc
            ).strftime("%d %B %Y, %H:%M UTC")

        summary = (
            f"Overall SEO score: **{score:.1f}/100**. "
            f"The audit identified **{issue_count}** tracked issues, "
            f"including **{critical} critical** and "
            f"**{high} high-priority** issues."
        )

        lines: list[str] = []

        lines.append(
            f"# SEO Audit Report — {cls._safe(audit.website, 'Website')}"
        )
        lines.append("")
        lines.append("## Audit Overview")
        lines.append("")
        lines.append(f"- **Website:** {cls._safe(audit.website)}")
        lines.append(
            f"- **Audit date:** {audit_date}"
        )
        lines.append(
            f"- **Overall score:** {score:.1f}/100"
        )
        lines.append(
            f"- **Pages discovered:** {int(getattr(audit, 'pages_discovered', 0) or 0)}"
        )
        lines.append(
            f"- **Pages crawled:** {int(getattr(audit, 'pages_crawled', 0) or 0)}"
        )
        lines.append(
            f"- **Pages successful:** {int(getattr(audit, 'pages_successful', 0) or 0)}"
        )
        lines.append(
            f"- **Pages failed:** {int(getattr(audit, 'pages_failed', 0) or 0)}"
        )
        lines.append("")
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(summary)
        lines.append("")

        if audit.warning_message:
            lines.append(
                f"> **Audit warning:** {audit.warning_message}"
            )
            lines.append("")

        lines.append("## Issue Summary")
        lines.append("")
        lines.append(
            f"- Critical: **{critical}**"
        )
        lines.append(
            f"- High priority: **{high}**"
        )
        lines.append(
            f"- Medium priority: **{medium}**"
        )
        lines.append(
            f"- Low priority: **{low}**"
        )
        lines.append("")

        # Scores available directly on Audit.
        audit_scores = [
            (
                "Technical SEO",
                getattr(audit, "technical_score", 0),
            ),
            (
                "Content SEO",
                getattr(audit, "content_score", 0),
            ),
            (
                "Local SEO",
                getattr(audit, "local_seo_score", 0),
            ),
            (
                "Schema",
                getattr(audit, "schema_score", 0),
            ),
            (
                "EEAT",
                getattr(audit, "eeat_score", 0),
            ),
            (
                "AI Search",
                getattr(audit, "ai_search_score", 0),
            ),
        ]

        lines.append("## Scorecard")
        lines.append("")
        lines.append("| Area | Score |")
        lines.append("|---|---:|")

        for name, area_score in audit_scores:
            try:
                numeric_score = float(
                    area_score or 0
                )
            except (TypeError, ValueError):
                numeric_score = 0

            lines.append(
                f"| {name} | {numeric_score:.1f}/100 |"
            )

        lines.append("")

        # Agent sections.
        for agent_name in cls.AGENT_ORDER:
            data = normalized.get(agent_name)

            if data is None:
                # Try case-insensitive matching.
                for existing_name, existing_data in normalized.items():
                    if existing_name.lower() == agent_name.lower():
                        data = existing_data
                        break

            if data is None:
                data = {
                    "score": None,
                    "findings": [],
                }

            agent_score = data.get("score")
            findings = data.get("findings") or []

            lines.append(f"## {agent_name}")
            lines.append("")

            if agent_score is not None:
                try:
                    lines.append(
                        f"**Agent score:** {float(agent_score):.1f}/100"
                    )
                except (TypeError, ValueError):
                    lines.append(
                        f"**Agent score:** {agent_score}"
                    )

                lines.append("")

            if findings:
                for finding in findings:
                    lines.append(
                        f"- {finding}"
                    )

                lines.append("")
            else:
                lines.append(
                    "_No structured findings were returned by this agent._"
                )
                lines.append("")

        lines.append("## Recommended Action Plan")
        lines.append("")
        lines.append(
            "### Immediate — 0 to 30 Days"
        )
        lines.append("")
        lines.append(
            "1. Resolve critical technical and indexability issues."
        )
        lines.append(
            "2. Address high-priority content, schema and local SEO findings."
        )
        lines.append(
            "3. Fix broken links, canonical, sitemap and robots issues identified by the audit."
        )
        lines.append("")

        lines.append(
            "### Growth — 31 to 60 Days"
        )
        lines.append("")
        lines.append(
            "1. Expand service and location content around high-intent search demand."
        )
        lines.append(
            "2. Strengthen internal linking and topical authority."
        )
        lines.append(
            "3. Improve E-E-A-T and local trust signals."
        )
        lines.append("")

        lines.append(
            "### Authority — 61 to 90 Days"
        )
        lines.append("")
        lines.append(
            "1. Build relevant, authoritative backlinks."
        )
        lines.append(
            "2. Expand AI-search/entity visibility."
        )
        lines.append(
            "3. Re-run the audit and compare score movement."
        )
        lines.append("")

        lines.append("## Audit Metrics")
        lines.append("")
        lines.append(
            f"- Internal links: {int(getattr(audit, 'internal_links', 0) or 0)}"
        )
        lines.append(
            f"- External links: {int(getattr(audit, 'external_links', 0) or 0)}"
        )
        lines.append(
            f"- Broken internal links: {int(getattr(audit, 'broken_internal_links', 0) or 0)}"
        )
        lines.append(
            f"- Broken external links: {int(getattr(audit, 'broken_external_links', 0) or 0)}"
        )
        lines.append(
            f"- Sitemap found: {'Yes' if getattr(audit, 'sitemap_found', False) else 'No'}"
        )
        lines.append(
            f"- Sitemap valid: {'Yes' if getattr(audit, 'sitemap_valid', False) else 'No'}"
        )
        lines.append(
            f"- Robots.txt found: {'Yes' if getattr(audit, 'robots_txt_found', False) else 'No'}"
        )
        lines.append(
            f"- Schema detected: {'Yes' if getattr(audit, 'schema_found', False) else 'No'}"
        )
        lines.append(
            f"- Local SEO score: {float(getattr(audit, 'local_seo_score', 0) or 0):.1f}/100"
        )
        lines.append(
            f"- EEAT score: {float(getattr(audit, 'eeat_score', 0) or 0):.1f}/100"
        )
        lines.append(
            f"- AI Search score: {float(getattr(audit, 'ai_search_score', 0) or 0):.1f}/100"
        )
        lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(
            "Generated by Boost Rankers AI SEO OS."
        )

        return "\n".join(lines), summary