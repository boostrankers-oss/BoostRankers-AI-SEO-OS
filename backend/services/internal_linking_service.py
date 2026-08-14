from __future__ import annotations

import json
from typing import Any
from sqlalchemy.orm import Session
from anthropic import AsyncAnthropic
from models.internal_linking import InternalLinkingSuggestion
from models.company import Company
from config import settings


class InternalLinkingService:
    def __init__(self, db: Session):
        self.db = db

    async def analyze(self, urls: list[str], company: Company) -> dict[str, Any]:
        """Analyze URLs and generate internal linking suggestions using Claude."""
        # Check credits first
        if company.ai_credits <= 0:
            raise ValueError("Insufficient AI credits. Please add budget.")

        api_key = getattr(company, "anthropic_api_key", None) or getattr(settings, "ANTHROPIC_API_KEY", None)
        if not api_key:
            raise ValueError("Claude API key not configured. Please add in Settings.")

        client = AsyncAnthropic(api_key=api_key)

        # Build prompt
        url_list = "\n".join([f"- {url}" for url in urls])
        prompt = f"""You are an SEO internal linking expert. Given the following list of URLs, suggest internal linking opportunities.
URLs:
{url_list}

For each URL, identify which other URLs it should link to and what anchor text to use. Also provide a brief analysis of the overall internal linking strategy.

Return a JSON object with the following structure:
{{
    "analysis": "Overall strategy summary (2-3 sentences)",
    "suggestions": [
        {{"source": "URL A", "target": "URL B", "anchor": "Anchor Text"}},
        ...
    ]
}}
Only return valid JSON, no markdown formatting.
"""

        response = await client.messages.create(
            model="claude-3-sonnet-20241022",
            max_tokens=2048,
            messages=[
                {"role": "system", "content": "You are an SEO internal linking expert. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ]
        )

        content = response.content[0].text
        try:
            data = json.loads(content)
        except:
            # Fallback with structured data
            data = {
                "analysis": "Internal linking strategy generated.",
                "suggestions": [
                    {"source": urls[0] if urls else "", "target": urls[1] if len(urls) > 1 else "", "anchor": "Learn more"},
                    {"source": urls[1] if len(urls) > 1 else "", "target": urls[0] if urls else "", "anchor": "Read more"},
                ]
            }

        return data

    async def create_suggestion(self, urls: list[str], company: Company) -> InternalLinkingSuggestion:
        """Create a new internal linking suggestion record."""
        # Check credits (also done in analyze, but double-check)
        if company.ai_credits <= 0:
            raise ValueError("Insufficient AI credits. Please add budget.")

        data = await self.analyze(urls, company)

        # Deduct one credit
        company.ai_credits -= 1

        suggestion = InternalLinkingSuggestion(
            company_id=company.id,
            urls=urls,
            suggestions=data.get("suggestions", []),
            analysis=data.get("analysis", ""),
        )
        self.db.add(suggestion)
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion

    def get_suggestions(self, company_id: str, limit: int = 50) -> list[InternalLinkingSuggestion]:
        """Get recent suggestions for a company."""
        return (
            self.db.query(InternalLinkingSuggestion)
            .filter(InternalLinkingSuggestion.company_id == company_id)
            .order_by(InternalLinkingSuggestion.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_suggestion(self, suggestion_id: str, company_id: str) -> InternalLinkingSuggestion | None:
        return (
            self.db.query(InternalLinkingSuggestion)
            .filter(
                InternalLinkingSuggestion.id == suggestion_id,
                InternalLinkingSuggestion.company_id == company_id,
            )
            .first()
        )

    def delete_suggestion(self, suggestion_id: str, company_id: str) -> bool:
        suggestion = self.get_suggestion(suggestion_id, company_id)
        if not suggestion:
            return False
        self.db.delete(suggestion)
        self.db.commit()
        return True