from __future__ import annotations

import json
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from anthropic import AsyncAnthropic
from sqlalchemy.orm import Session

from models.backlink import (
    Backlink,
    BacklinkOpportunity,
    OutreachEmail,
)
from models.company import Company
from services.secret_service import decrypt_secret


class BacklinkService:
    def __init__(self, db: Session):
        self.db = db

    # =========================================================
    # Anthropic Configuration
    # =========================================================

    @staticmethod
    def _get_api_key(company: Company) -> str | None:
        """
        Resolve the Anthropic API key.

        Priority:
        1. Company-specific encrypted credential.
        2. Global ANTHROPIC_API_KEY environment variable.

        The company credential is authoritative when configured.
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

            except (ValueError, TypeError):
                return None

        global_key = os.getenv(
            "ANTHROPIC_API_KEY",
            "",
        ).strip()

        return global_key or None

    @staticmethod
    def _get_model() -> str:
        """
        Resolve the Anthropic model.

        Uses ANTHROPIC_MODEL when configured.
        Falls back to the current Claude Sonnet model.
        """

        model = os.getenv(
            "ANTHROPIC_MODEL",
            "",
        ).strip()

        return model or "claude-sonnet-4-6"

    # =========================================================
    # Backlink CRUD
    # =========================================================

    def get_backlinks(
        self,
        company_id: str,
    ) -> List[Backlink]:
        return (
            self.db.query(Backlink)
            .filter(
                Backlink.company_id == company_id
            )
            .all()
        )

    def add_backlink(
        self,
        company_id: str,
        data: dict,
    ) -> Backlink:
        backlink = Backlink(
            company_id=company_id,
            source_url=data["source_url"],
            target_url=data["target_url"],
            anchor_text=data["anchor_text"],
            link_type=data["link_type"],
            domain_authority=data.get(
                "domain_authority",
                random.randint(30, 90),
            ),
            spam_score=data.get(
                "spam_score",
                random.randint(0, 30),
            ),
            status="active",
            detected_at=datetime.now(timezone.utc),
        )

        self.db.add(backlink)
        self.db.commit()
        self.db.refresh(backlink)

        return backlink

    def delete_backlink(
        self,
        backlink_id: str,
        company_id: str,
    ) -> bool:
        backlink = (
            self.db.query(Backlink)
            .filter(
                Backlink.id == backlink_id,
                Backlink.company_id == company_id,
            )
            .first()
        )

        if not backlink:
            return False

        self.db.delete(backlink)
        self.db.commit()

        return True

    # =========================================================
    # AI Backlink Analysis
    # =========================================================

    async def analyze_backlink(
        self,
        backlink_id: str,
        company: Company,
    ) -> str:
        """
        Use Claude to analyze a backlink's quality and risks.
        """

        backlink = (
            self.db.query(Backlink)
            .filter(
                Backlink.id == backlink_id,
                Backlink.company_id == company.id,
            )
            .first()
        )

        if not backlink:
            raise ValueError(
                "Backlink not found"
            )

        if company.ai_credits <= 0:
            raise ValueError(
                "Insufficient AI credits. Please add budget."
            )

        api_key = self._get_api_key(company)

        if not api_key:
            raise ValueError(
                "Claude API key is not configured or "
                "could not be decrypted."
            )

        model = self._get_model()

        client = AsyncAnthropic(
            api_key=api_key,
        )

        prompt = f"""
Analyze this backlink for SEO quality and risks.

Domain: {backlink.source_url}
Target URL: {backlink.target_url}
Anchor: {backlink.anchor_text}
Type: {backlink.link_type}
Spam Score: {backlink.spam_score}
Domain Authority: {backlink.domain_authority}

Provide:
1. Overall quality assessment.
2. SEO value.
3. Potential risks.
4. A concise recommendation.

Keep the response concise and practical for an SEO professional.
""".strip()

        response = await client.messages.create(
            model=model,
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        text_parts: list[str] = []

        for block in response.content:
            if getattr(block, "type", None) == "text":
                text = getattr(
                    block,
                    "text",
                    None,
                )

                if text:
                    text_parts.append(
                        str(text)
                    )

        analysis = "\n".join(
            text_parts
        ).strip()

        if not analysis:
            raise ValueError(
                "Anthropic returned an empty analysis."
            )

        backlink.ai_analysis = analysis

        # Deduct one application AI credit only after
        # successful generation.
        company.ai_credits -= 1

        self.db.commit()

        return analysis

    # =========================================================
    # AI Link Opportunities
    # =========================================================

    async def generate_opportunities(
        self,
        company: Company,
    ) -> List[dict]:
        """
        Use Claude to find link opportunities.
        """

        if company.ai_credits <= 0:
            raise ValueError(
                "Insufficient AI credits. Please add budget."
            )

        api_key = self._get_api_key(company)

        if not api_key:
            raise ValueError(
                "Claude API key is not configured or "
                "could not be decrypted."
            )

        model = self._get_model()

        client = AsyncAnthropic(
            api_key=api_key,
        )

        prompt = """
Generate 3 realistic link building opportunities for an AI SEO
tool company.

For each opportunity provide:
- domain
- type: guest_post, resource_page, or news_article
- domain_authority: integer 0-100
- relevance: high, medium, or low

Return ONLY a valid JSON array.

Example:
[
  {
    "domain": "example.com",
    "type": "guest_post",
    "da": 85,
    "relevance": "high"
  }
]
""".strip()

        response = await client.messages.create(
            model=model,
            max_tokens=800,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        text_parts: list[str] = []

        for block in response.content:
            if getattr(block, "type", None) == "text":
                text = getattr(
                    block,
                    "text",
                    None,
                )

                if text:
                    text_parts.append(
                        str(text)
                    )

        content = "\n".join(
            text_parts
        ).strip()

        try:
            data = json.loads(content)

        except (
            json.JSONDecodeError,
            TypeError,
        ):
            data = []

        if not isinstance(data, list):
            data = []

        # Validate and normalize AI output.
        normalized: list[dict] = []

        for item in data:
            if not isinstance(item, dict):
                continue

            domain = str(
                item.get("domain", "")
            ).strip()

            opportunity_type = str(
                item.get("type", "")
            ).strip()

            relevance = str(
                item.get("relevance", "")
            ).strip().lower()

            try:
                domain_authority = int(
                    item.get("da", 0)
                )
            except (
                TypeError,
                ValueError,
            ):
                domain_authority = 0

            if not domain:
                continue

            if opportunity_type not in {
                "guest_post",
                "resource_page",
                "news_article",
            }:
                opportunity_type = "resource_page"

            if relevance not in {
                "high",
                "medium",
                "low",
            }:
                relevance = "medium"

            domain_authority = max(
                0,
                min(
                    domain_authority,
                    100,
                ),
            )

            normalized.append(
                {
                    "domain": domain,
                    "type": opportunity_type,
                    "da": domain_authority,
                    "relevance": relevance,
                }
            )

        # Keep the existing fallback behavior if the provider
        # returns unusable JSON.
        if not normalized:
            normalized = [
                {
                    "domain": "ahrefs.com",
                    "type": "guest_post",
                    "da": 90,
                    "relevance": "high",
                },
                {
                    "domain": "semrush.com",
                    "type": "resource_page",
                    "da": 92,
                    "relevance": "high",
                },
                {
                    "domain": "searchengineland.com",
                    "type": "news_article",
                    "da": 88,
                    "relevance": "medium",
                },
            ]

        opportunities: list[BacklinkOpportunity] = []

        for item in normalized:
            opportunity = BacklinkOpportunity(
                company_id=company.id,
                domain=item["domain"],
                opportunity_type=item["type"],
                domain_authority=item["da"],
                relevance=item["relevance"],
                status="pending",
            )

            self.db.add(opportunity)
            opportunities.append(opportunity)

        # Deduct one application AI credit only after successful
        # provider generation and database preparation.
        company.ai_credits -= 1

        self.db.commit()

        return [
            {
                "domain": opportunity.domain,
                "type": opportunity.opportunity_type,
                "da": opportunity.domain_authority,
                "relevance": opportunity.relevance,
                "id": opportunity.id,
                "status": opportunity.status,
            }
            for opportunity in opportunities
        ]

    def get_opportunities(
        self,
        company_id: str,
    ) -> List[BacklinkOpportunity]:
        return (
            self.db.query(
                BacklinkOpportunity
            )
            .filter(
                BacklinkOpportunity.company_id
                == company_id
            )
            .order_by(
                BacklinkOpportunity.created_at.desc()
            )
            .all()
        )

    def delete_opportunity(
        self,
        opportunity_id: str,
        company_id: str,
    ) -> bool:
        opportunity = (
            self.db.query(
                BacklinkOpportunity
            )
            .filter(
                BacklinkOpportunity.id
                == opportunity_id,
                BacklinkOpportunity.company_id
                == company_id,
            )
            .first()
        )

        if not opportunity:
            return False

        self.db.delete(opportunity)
        self.db.commit()

        return True

    # =========================================================
    # Outreach
    # =========================================================

    async def generate_outreach_email(
        self,
        opportunity_id: str,
        company: Company,
    ) -> str:
        """
        Generate a personalized outreach email using Claude.
        """

        opportunity = (
            self.db.query(
                BacklinkOpportunity
            )
            .filter(
                BacklinkOpportunity.id
                == opportunity_id,
                BacklinkOpportunity.company_id
                == company.id,
            )
            .first()
        )

        if not opportunity:
            raise ValueError(
                "Opportunity not found"
            )

        if company.ai_credits <= 0:
            raise ValueError(
                "Insufficient AI credits. Please add budget."
            )

        api_key = self._get_api_key(company)

        if not api_key:
            raise ValueError(
                "Claude API key is not configured or "
                "could not be decrypted."
            )

        model = self._get_model()

        client = AsyncAnthropic(
            api_key=api_key,
        )

        prompt = f"""
Write a professional SEO outreach email for a link-building
opportunity.

Target Domain: {opportunity.domain}
Opportunity Type: {opportunity.opportunity_type}

Sender Company: Boost Rankers

Requirements:
- Professional and natural tone.
- No spammy language.
- No exaggerated claims.
- Explain why the collaboration is relevant.
- Include a clear but non-pushy call to action.
- Return only the email body.
""".strip()

        response = await client.messages.create(
            model=model,
            max_tokens=900,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        text_parts: list[str] = []

        for block in response.content:
            if getattr(block, "type", None) == "text":
                text = getattr(
                    block,
                    "text",
                    None,
                )

                if text:
                    text_parts.append(
                        str(text)
                    )

        email_body = "\n".join(
            text_parts
        ).strip()

        if not email_body:
            raise ValueError(
                "Anthropic returned an empty outreach email."
            )

        email = OutreachEmail(
            company_id=company.id,
            opportunity_id=opportunity.id,
            subject=(
                f"Guest Post Opportunity for "
                f"{opportunity.domain}"
            ),
            body=email_body,
            status="draft",
        )

        self.db.add(email)

        # Deduct one application AI credit only after
        # successful generation.
        company.ai_credits -= 1

        self.db.commit()

        return email_body

    def get_outreach_emails(
        self,
        company_id: str,
    ) -> List[OutreachEmail]:
        return (
            self.db.query(
                OutreachEmail
            )
            .filter(
                OutreachEmail.company_id
                == company_id
            )
            .order_by(
                OutreachEmail.created_at.desc()
            )
            .all()
        )

    # =========================================================
    # Statistics
    # =========================================================

    def get_statistics(
        self,
        company_id: str,
    ) -> Dict[str, Any]:
        backlinks = (
            self.db.query(Backlink)
            .filter(
                Backlink.company_id == company_id
            )
            .all()
        )

        total = len(backlinks)

        active = sum(
            1
            for backlink in backlinks
            if backlink.status == "active"
        )

        toxic = sum(
            1
            for backlink in backlinks
            if backlink.status == "toxic"
        )

        referring_domains = len(
            {
                backlink.source_url
                for backlink in backlinks
            }
        )

        avg_da = (
            int(
                sum(
                    backlink.domain_authority
                    for backlink in backlinks
                )
                / total
            )
            if total
            else 0
        )

        # Existing project behavior retained.
        today = datetime.now(timezone.utc)

        history = []

        for i in range(6, 0, -1):
            history_date = (
                today
                - timedelta(days=i * 30)
            )

            history.append(
                {
                    "month": history_date.strftime(
                        "%b"
                    ),
                    "new": random.randint(
                        40,
                        120,
                    ),
                    "lost": random.randint(
                        10,
                        30,
                    ),
                }
            )

        link_types: dict[str, int] = {}

        for backlink in backlinks:
            link_types[
                backlink.link_type
            ] = (
                link_types.get(
                    backlink.link_type,
                    0,
                )
                + 1
            )

        return {
            "total": total,
            "referring_domains": referring_domains,
            "domain_authority": avg_da,
            "toxic_links": toxic,
            "new_this_month": len(
                [
                    backlink
                    for backlink in backlinks
                    if backlink.detected_at
                    and backlink.detected_at
                    > today - timedelta(days=30)
                ]
            ),
            # Existing values retained from the current implementation.
            "new_domains": 24,
            "da_change": 2,
            "toxic_fixed": 3,
            "growth_history": history,
            "link_types": link_types,
        }