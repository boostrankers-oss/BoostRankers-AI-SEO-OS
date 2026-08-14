from __future__ import annotations

import json
import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator, Any
from sqlalchemy.orm import Session
from anthropic import AsyncAnthropic

from models.audit import Audit, AuditStatus
from models.company import Company
from models.user import User
from config import settings
import logging

logger = logging.getLogger(__name__)

class AuditService:
    def __init__(self, db: Session):
        self.db = db

    async def run_audit(
        self,
        url: str,
        user: User,
        company: Company,
        request: Any = None,
    ) -> AsyncGenerator[str, None]:
        """Run a full multi-agent audit with Claude AI."""

        # Check credits
        if company.ai_credits <= 0:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Insufficient AI credits. Please add budget.'})}\n\n"
            return

        # Deduct one credit
        company.ai_credits -= 1
        self.db.commit()

        # Create audit record
        audit = Audit(
            website=url,
            company_id=company.id,
            user_id=user.id,
            status=AuditStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            progress=0,
        )
        self.db.add(audit)
        self.db.commit()

        # Get Claude API key
        api_key = getattr(company, "anthropic_api_key", None) or getattr(settings, "ANTHROPIC_API_KEY", None)
        if not api_key:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Claude API key not configured. Please add in Settings.'})}\n\n"
            return

        client = AsyncAnthropic(api_key=api_key)

        # Agent definitions
        agents = [
            {"name": "Technical SEO Agent", "prompt": "Analyze the site's technical SEO, including crawlability, indexability, canonical tags, redirects, sitemap, robots.txt, and Core Web Vitals. Provide 3 key findings."},
            {"name": "Content SEO Agent", "prompt": "Analyze content quality, keyword usage, headings, readability, thin content, and duplicate content. Provide 3 key findings."},
            {"name": "Local SEO Agent", "prompt": "Analyze local search presence: NAP consistency, Google Business Profile, local citations, reviews, and local keywords. Provide 3 key findings."},
            {"name": "Schema Agent", "prompt": "Analyze structured data: validate schema markup, identify missing schemas, and suggest improvements for rich snippets. Provide 3 key findings."},
            {"name": "EEAT Agent", "prompt": "Analyze Experience, Expertise, Authoritativeness, and Trust signals: author bios, contact info, privacy policy, external references, and trust badges. Provide 3 key findings."},
            {"name": "Internal Linking Agent", "prompt": "Analyze internal link structure: orphan pages, deep linking, anchor text distribution, and link equity flow. Provide 3 key findings."},
            {"name": "Competitor Agent", "prompt": "Analyze competitive landscape: keyword gaps, backlink gaps, content gaps, and authority gaps. Provide 3 key findings."},
            {"name": "Backlink Agent", "prompt": "Analyze backlink profile: total backlinks, referring domains, toxic links, anchor text diversity, and domain authority. Provide 3 key findings."},
            {"name": "AI Search Agent", "prompt": "Analyze AI search optimization: LLM visibility, entity recognition, semantic coverage, and AI snippet presence. Provide 3 key findings."},
            {"name": "Reporting Agent", "prompt": "Compile all findings into a comprehensive executive summary with actionable recommendations. Provide a 5-point summary."},
        ]

        total_agents = len(agents)
        results = []

        for idx, agent in enumerate(agents):
            progress = int((idx / total_agents) * 100)
            yield f"data: {json.dumps({'type': 'agent_start', 'agent': agent['name'], 'progress': progress})}\n\n"
            await asyncio.sleep(0.1)

            try:
                response = await client.messages.create(
                    model="claude-3-sonnet-20241022",
                    max_tokens=1024,
                    messages=[
                        {"role": "system", "content": f"You are an SEO auditing agent specializing in {agent['name']}. Always respond with a JSON object containing 'findings' (array of strings) and 'score' (integer 0-100)."},
                        {"role": "user", "content": f"Website URL: {url}\nTask: {agent['prompt']}"}
                    ]
                )
                content = response.content[0].text
                try:
                    parsed = json.loads(content)
                    findings = parsed.get("findings", ["Analysis complete."])
                    score = parsed.get("score", 50)
                except:
                    findings = [content[:200] + "..."]
                    score = 50

                for log in findings:
                    yield f"data: {json.dumps({'type': 'log', 'agent': agent['name'], 'message': log})}\n\n"
                    await asyncio.sleep(0.05)

                results.append({"agent": agent['name'], "findings": findings, "score": score})

            except Exception as e:
                error_msg = str(e)
                yield f"data: {json.dumps({'type': 'error', 'agent': agent['name'], 'message': error_msg})}\n\n"
                results.append({"agent": agent['name'], "findings": [error_msg], "score": 0})

            # Update progress
            audit.progress = int(((idx + 1) / total_agents) * 100)
            self.db.commit()

        # Complete audit
        avg_score = sum(r["score"] for r in results) / len(results) if results else 0
        audit.status = AuditStatus.COMPLETED
        audit.completed_at = datetime.now(timezone.utc)
        audit.progress = 100
        audit.overall_score = avg_score
        self.db.commit()

        # Generate report via report service
        try:
            from services.report_service import ReportService
            report_service = ReportService(self.db)
            report_service.generate_report_from_audit(audit)
        except Exception as e:
            logger.error(f"Report generation failed: {e}")

        yield f"data: {json.dumps({'type': 'complete', 'results': results, 'score': avg_score})}\n\n"