from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any, Dict, List
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from anthropic import AsyncAnthropic
from sqlalchemy.orm import Session

from config import settings
from services.secret_service import decrypt_secret
from models.backlink import Backlink, BacklinkOpportunity, OutreachEmail
from models.company import Company

logger = logging.getLogger(__name__)


class _LinkParser(HTMLParser):
    """Small dependency-free HTML parser used for backlink verification."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self._active_link: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        values = {k.lower(): (v or "") for k, v in attrs}
        self._active_link = {
            "href": values.get("href", ""),
            "rel": values.get("rel", ""),
            "text": "",
        }
        self.links.append(self._active_link)

    def handle_data(self, data: str) -> None:
        if self._active_link is not None:
            self._active_link["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a":
            self._active_link = None


class BacklinkService:
    def __init__(self, db: Session):
        self.db = db

    # ============================================================
    # URL / verification helpers
    # ============================================================

    @staticmethod
    def _validate_public_https_url(value: str, field_name: str) -> str:
        value = (value or "").strip()
        parsed = urlsplit(value)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise ValueError(f"{field_name} must be a valid HTTPS URL.")
        if parsed.username or parsed.password:
            raise ValueError(f"{field_name} must not contain credentials.")
        return value

    @staticmethod
    def _canonical_url(value: str) -> str:
        parsed = urlsplit(value.strip())
        path = parsed.path.rstrip("/") or "/"
        return urlunsplit(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                path,
                parsed.query,
                "",
            )
        )

    @staticmethod
    def _link_type(rel: str) -> str:
        tokens = {item.lower() for item in re.split(r"\s+", rel.strip()) if item}
        if "sponsored" in tokens:
            return "Sponsored"
        if "ugc" in tokens:
            return "UGC"
        if "nofollow" in tokens:
            return "Nofollow"
        return "Dofollow"

    async def verify_backlink(
        self,
        source_url: str,
        target_url: str,
        anchor_text: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a public page and verify that it contains the target link."""
        source_url = self._validate_public_https_url(source_url, "Source URL")
        target_url = self._validate_public_https_url(target_url, "Target URL")

        headers = {
            "User-Agent": (
                "BoostRankersBot/1.0 (+https://boostrankers.com/; "
                "backlink-verification)"
            ),
            "Accept": "text/html,application/xhtml+xml",
        }

        timeout = httpx.Timeout(20.0, connect=10.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await client.get(source_url)

        if response.status_code >= 400:
            return {
                "verified": False,
                "status": "not_found",
                "http_status": response.status_code,
                "final_url": str(response.url),
                "link_type": None,
                "anchor_text": None,
                "reason": f"Source page returned HTTP {response.status_code}.",
            }

        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type and "xhtml" not in content_type:
            return {
                "verified": False,
                "status": "not_found",
                "http_status": response.status_code,
                "final_url": str(response.url),
                "link_type": None,
                "anchor_text": None,
                "reason": "Source URL did not return an HTML document.",
            }

        parser = _LinkParser()
        try:
            parser.feed(response.text)
        except Exception as exc:
            logger.warning("Backlink HTML parsing failed for %s: %s", source_url, exc)
            return {
                "verified": False,
                "status": "verification_failed",
                "http_status": response.status_code,
                "final_url": str(response.url),
                "link_type": None,
                "anchor_text": None,
                "reason": "Unable to parse the source HTML.",
            }

        expected = self._canonical_url(target_url)
        requested_anchor = (anchor_text or "").strip().casefold()

        for link in parser.links:
            href = link.get("href", "").strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            absolute = urljoin(str(response.url), href)
            if self._canonical_url(absolute) != expected:
                continue

            detected_type = self._link_type(link.get("rel", ""))
            detected_anchor = " ".join(link.get("text", "").split())
            anchor_matches = (
                not requested_anchor
                or requested_anchor in detected_anchor.casefold()
            )
            return {
                "verified": True,
                "status": "active",
                "http_status": response.status_code,
                "final_url": str(response.url),
                "link_type": detected_type,
                "anchor_text": detected_anchor or (anchor_text or ""),
                "anchor_match": anchor_matches,
                "reason": "Target URL was found in a live HTML link.",
            }

        return {
            "verified": False,
            "status": "not_found",
            "http_status": response.status_code,
            "final_url": str(response.url),
            "link_type": None,
            "anchor_text": None,
            "reason": "The target URL was not found in the source page HTML.",
        }

    # ============================================================
    # Backlink CRUD / tracking
    # ============================================================

    def get_backlinks(self, company_id: str) -> List[Backlink]:
        return (
            self.db.query(Backlink)
            .filter(Backlink.company_id == company_id)
            .order_by(Backlink.detected_at.desc())
            .all()
        )

    async def add_backlink(self, company_id: str, data: dict) -> Backlink:
        """Track an existing backlink only after live verification."""
        verification = await self.verify_backlink(
            data["source_url"],
            data["target_url"],
            data.get("anchor_text"),
        )

        if not verification["verified"]:
            raise ValueError(
                "Backlink was not verified: " + verification["reason"]
            )

        backlink = Backlink(
            company_id=company_id,
            source_url=data["source_url"],
            target_url=data["target_url"],
            anchor_text=verification.get("anchor_text") or data.get("anchor_text", ""),
            link_type=verification.get("link_type") or "Dofollow",
            domain_authority=0,
            spam_score=0,
            status="active",
            detected_at=datetime.now(timezone.utc),
        )
        self.db.add(backlink)
        self.db.commit()
        self.db.refresh(backlink)
        return backlink

    async def publish_wordpress_backlink(
        self,
        company_id: str,
        data: dict,
    ) -> dict[str, Any]:
        """Create a real WordPress post on a site the user controls/authorizes.

        Credentials are used only for this request and are never stored.
        The backlink is inserted into our database only after the published
        page is independently fetched and the target link is verified.
        """
        wp_site = self._validate_public_https_url(data["wordpress_site"], "WordPress site")
        target_url = self._validate_public_https_url(data["target_url"], "Target URL")
        username = (data.get("wordpress_username") or "").strip()
        app_password = (data.get("wordpress_application_password") or "").strip()
        title = (data.get("title") or "").strip()
        content = (data.get("content") or "").strip()
        anchor_text = (data.get("anchor_text") or "").strip()
        publish_status = (data.get("status") or "publish").strip().lower()

        if not username or not app_password:
            raise ValueError("WordPress username and Application Password are required.")
        if not title:
            raise ValueError("Post title is required.")
        if len(content) < 300:
            raise ValueError("Post content must contain at least 300 characters.")
        if not anchor_text:
            raise ValueError("Anchor text is required.")
        if publish_status not in {"publish", "draft", "pending"}:
            raise ValueError("WordPress status must be publish, draft, or pending.")

        # Application Passwords are the WordPress-supported external REST API
        # credential. The secret is intentionally never persisted by this app.
        auth = base64.b64encode(
            f"{username}:{app_password}".encode("utf-8")
        ).decode("ascii")
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "BoostRankersAISEOOS/1.0",
        }

        api_url = wp_site.rstrip("/") + "/wp-json/wp/v2/posts"
        html_link = (
            f'<a href="{target_url}" rel="noopener">'
            f"{anchor_text}</a>"
        )
        # Place the backlink at the end of user-provided content. The user is
        # responsible for having authorization to publish on the WordPress site.
        publish_content = content + "\n\n<p>" + html_link + "</p>"

        payload = {
            "title": title,
            "content": publish_content,
            "status": publish_status,
        }

        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            try:
                me = await client.get(
                    wp_site.rstrip("/") + "/wp-json/wp/v2/users/me",
                    params={"context": "edit"},
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                raise ValueError(f"Could not connect to WordPress: {exc}") from exc

            if me.status_code >= 400:
                raise ValueError(
                    f"WordPress authentication failed (HTTP {me.status_code}). "
                    "Use a WordPress Application Password, not the normal account password."
                )

            try:
                created = await client.post(api_url, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                raise ValueError(f"Could not publish to WordPress: {exc}") from exc

            if created.status_code >= 400:
                detail = created.text[:500]
                raise ValueError(
                    f"WordPress rejected the post (HTTP {created.status_code}): {detail}"
                )

            try:
                post = created.json()
            except ValueError as exc:
                raise ValueError("WordPress returned an invalid JSON response.") from exc

            source_url = post.get("link")
            post_id = post.get("id")
            if not source_url or not post_id:
                raise ValueError("WordPress did not return a published post URL/ID.")

        # A draft/pending post is not a live backlink. Do not record it as one.
        if publish_status != "publish":
            return {
                "success": True,
                "publication_status": publish_status,
                "published_url": source_url,
                "post_id": post_id,
                "verified": False,
                "message": (
                    "WordPress content was created, but it is not a live backlink "
                    "until the post is published."
                ),
            }

        # Give WordPress a short moment to expose the new post, then verify it
        # independently using a public unauthenticated request.
        verification = None
        last_error = None
        for attempt in range(3):
            try:
                verification = await self.verify_backlink(
                    source_url,
                    target_url,
                    anchor_text,
                )
                if verification["verified"]:
                    break
            except Exception as exc:
                last_error = str(exc)
            if attempt < 2:
                await asyncio.sleep(2)

        if not verification or not verification["verified"]:
            return {
                "success": True,
                "publication_status": "published",
                "published_url": source_url,
                "post_id": post_id,
                "verified": False,
                "message": (
                    "WordPress published the post, but the public page could not "
                    "yet be verified as containing the backlink. It was not added "
                    "to the backlink profile."
                ),
                "verification": verification or {"reason": last_error},
            }

        backlink = Backlink(
            company_id=company_id,
            source_url=source_url,
            target_url=target_url,
            anchor_text=anchor_text,
            link_type=verification.get("link_type") or "Dofollow",
            domain_authority=0,
            spam_score=0,
            status="active",
            detected_at=datetime.now(timezone.utc),
        )
        self.db.add(backlink)
        self.db.commit()
        self.db.refresh(backlink)

        return {
            "success": True,
            "publication_status": "published",
            "published_url": source_url,
            "post_id": post_id,
            "verified": True,
            "verification": verification,
            "backlink": backlink,
            "message": "Real WordPress backlink published and independently verified.",
        }

    def delete_backlink(self, backlink_id: str, company_id: str) -> bool:
        backlink = self.db.query(Backlink).filter(
            Backlink.id == backlink_id,
            Backlink.company_id == company_id,
        ).first()
        if not backlink:
            return False
        self.db.delete(backlink)
        self.db.commit()
        return True

    # ============================================================
    # AI analysis
    # ============================================================

    async def analyze_backlink(self, backlink_id: str, company: Company) -> str:
        backlink = self.db.query(Backlink).filter(
            Backlink.id == backlink_id,
            Backlink.company_id == company.id,
        ).first()
        if not backlink:
            raise ValueError("Backlink not found")

        if company.ai_credits <= 0:
            raise ValueError("Insufficient AI credits. Please add budget.")

        encrypted_key = getattr(company, "anthropic_api_key_encrypted", None)
        api_key = decrypt_secret(encrypted_key) if encrypted_key else getattr(settings, "ANTHROPIC_API_KEY", None)
        if not api_key:
            raise ValueError("Claude API key not configured.")

        client = AsyncAnthropic(api_key=api_key)
        model = getattr(settings, "ANTHROPIC_MODEL", None) or "claude-sonnet-4-6"

        prompt = f"""Analyze this verified backlink for SEO quality and risk.
Source URL: {backlink.source_url}
Target URL: {backlink.target_url}
Anchor: {backlink.anchor_text}
Detected link type: {backlink.link_type}

Do not invent Domain Authority, traffic, spam score, or ranking data.
Explain the likely SEO value and any risks in 2-4 concise sentences."""

        response = await client.messages.create(
            model=model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        analysis = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )
        backlink.ai_analysis = analysis
        company.ai_credits -= 1
        self.db.commit()
        return analysis

    # ============================================================
    # Opportunities
    # ============================================================

    async def generate_opportunities(self, company: Company) -> List[dict]:
        if company.ai_credits <= 0:
            raise ValueError("Insufficient AI credits. Please add budget.")

        encrypted_key = getattr(company, "anthropic_api_key_encrypted", None)
        api_key = decrypt_secret(encrypted_key) if encrypted_key else getattr(settings, "ANTHROPIC_API_KEY", None)
        if not api_key:
            raise ValueError("Claude API key not configured.")

        client = AsyncAnthropic(api_key=api_key)
        model = getattr(settings, "ANTHROPIC_MODEL", None) or "claude-sonnet-4-6"
        company_domain = getattr(company, "domain", None) or getattr(company, "website", None) or ""

        prompt = f"""Create backlink prospecting ideas for this company/domain: {company_domain}

Return ONLY a JSON array of opportunity ideas. Do not invent or claim that any
site has agreed to publish a link. Opportunities must be framed as prospects
that still require permission or editorial acceptance.

Each object must contain:
- domain
- type (guest_post, resource_page, partner, directory, local_citation, news_article)
- relevance (high, medium, low)
- notes

Do not fabricate Domain Authority or traffic metrics."""

        response = await client.messages.create(
            model=model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        content = "".join(block.text for block in response.content if hasattr(block, "text")).strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("Claude returned invalid opportunity JSON. No fake opportunities were inserted.") from exc

        if not isinstance(data, list):
            raise ValueError("Claude returned an invalid opportunity structure.")

        company.ai_credits -= 1
        opportunities: list[BacklinkOpportunity] = []
        for item in data[:10]:
            domain = str(item.get("domain", "")).strip()
            opportunity_type = str(item.get("type", "")).strip()
            relevance = str(item.get("relevance", "medium")).strip().lower()
            notes = str(item.get("notes", "")).strip()
            if not domain or not opportunity_type:
                continue
            if relevance not in {"high", "medium", "low"}:
                relevance = "medium"
            opp = BacklinkOpportunity(
                company_id=company.id,
                domain=domain,
                opportunity_type=opportunity_type,
                domain_authority=0,
                relevance=relevance,
                status="pending",
                notes=notes,
            )
            self.db.add(opp)
            opportunities.append(opp)

        self.db.commit()
        return [
            {
                "domain": o.domain,
                "type": o.opportunity_type,
                "da": None,
                "relevance": o.relevance,
                "id": o.id,
                "status": o.status,
                "notes": o.notes,
            }
            for o in opportunities
        ]

    def get_opportunities(self, company_id: str) -> List[BacklinkOpportunity]:
        return self.db.query(BacklinkOpportunity).filter(
            BacklinkOpportunity.company_id == company_id
        ).order_by(BacklinkOpportunity.created_at.desc()).all()

    def delete_opportunity(self, opportunity_id: str, company_id: str) -> bool:
        opp = self.db.query(BacklinkOpportunity).filter(
            BacklinkOpportunity.id == opportunity_id,
            BacklinkOpportunity.company_id == company_id,
        ).first()
        if not opp:
            return False
        self.db.delete(opp)
        self.db.commit()
        return True

    # ============================================================
    # Outreach
    # ============================================================

    async def generate_outreach_email(self, opportunity_id: str, company: Company) -> str:
        opp = self.db.query(BacklinkOpportunity).filter(
            BacklinkOpportunity.id == opportunity_id,
            BacklinkOpportunity.company_id == company.id,
        ).first()
        if not opp:
            raise ValueError("Opportunity not found")

        if company.ai_credits <= 0:
            raise ValueError("Insufficient AI credits. Please add budget.")

        encrypted_key = getattr(company, "anthropic_api_key_encrypted", None)
        api_key = decrypt_secret(encrypted_key) if encrypted_key else getattr(settings, "ANTHROPIC_API_KEY", None)
        if not api_key:
            raise ValueError("Claude API key not configured.")

        client = AsyncAnthropic(api_key=api_key)
        model = getattr(settings, "ANTHROPIC_MODEL", None) or "claude-sonnet-4-6"

        prompt = f"""Write a professional backlink outreach email.
Prospect domain: {opp.domain}
Opportunity type: {opp.opportunity_type}
Company: {getattr(company, 'name', 'the company')}

Do not claim that the prospect has agreed to publish a link.
Keep it concise and personalized."""

        response = await client.messages.create(
            model=model,
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
        email_body = "".join(block.text for block in response.content if hasattr(block, "text"))

        email = OutreachEmail(
            company_id=company.id,
            opportunity_id=opp.id,
            subject=f"Content collaboration opportunity for {opp.domain}",
            body=email_body,
            status="draft",
        )
        self.db.add(email)
        company.ai_credits -= 1
        self.db.commit()
        self.db.refresh(email)
        return email

    def get_outreach_emails(self, company_id: str) -> List[OutreachEmail]:
        return self.db.query(OutreachEmail).filter(
            OutreachEmail.company_id == company_id
        ).order_by(OutreachEmail.created_at.desc()).all()

    def update_outreach_email(
        self,
        outreach_id: str,
        company_id: str,
        subject: str,
        body: str,
    ) -> OutreachEmail:
        email = self.db.query(OutreachEmail).filter(
            OutreachEmail.id == outreach_id,
            OutreachEmail.company_id == company_id,
        ).first()
        if not email:
            raise ValueError("Outreach email not found")
        if email.status == "sent":
            raise ValueError("Sent outreach emails cannot be edited.")
        subject = (subject or "").strip()
        body = (body or "").strip()
        if not subject:
            raise ValueError("Email subject is required.")
        if not body:
            raise ValueError("Email body is required.")
        email.subject = subject[:255]
        email.body = body
        self.db.commit()
        self.db.refresh(email)
        return email

    async def send_outreach_email(
        self,
        outreach_id: str,
        company: Company,
        recipient_email: str,
    ) -> OutreachEmail:
        """Send a generated outreach email through the configured SMTP account.

        SMTP credentials come from the existing application EmailSettings and are
        never stored in the outreach record. The recipient address is supplied
        for the send operation and is not persisted because the current schema
        does not contain a recipient_email column.
        """
        import re

        recipient_email = (recipient_email or "").strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", recipient_email):
            raise ValueError("A valid recipient email address is required.")

        email = self.db.query(OutreachEmail).filter(
            OutreachEmail.id == outreach_id,
            OutreachEmail.company_id == company.id,
        ).first()
        if not email:
            raise ValueError("Outreach email not found")
        if email.status == "sent":
            raise ValueError("This outreach email has already been sent.")

        smtp = settings.email
        username = (smtp.username or "").strip()
        password = smtp.password.get_secret_value() if smtp.password else ""
        sender = (smtp.sender or username or "").strip()
        if not smtp.smtp_host or not username or not password or not sender:
            raise ValueError(
                "SMTP is not configured. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, "
                "and SMTP_SENDER before sending outreach emails."
            )

        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = recipient_email
        msg["Subject"] = email.subject
        msg["Reply-To"] = sender
        msg.set_content(email.body)

        def _send() -> None:
            if smtp.smtp_port == 465:
                with smtplib.SMTP_SSL(smtp.smtp_host, smtp.smtp_port, timeout=30) as server:
                    server.login(username, password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(smtp.smtp_host, smtp.smtp_port, timeout=30) as server:
                    server.ehlo()
                    if smtp.use_tls:
                        server.starttls()
                        server.ehlo()
                    server.login(username, password)
                    server.send_message(msg)

        try:
            await asyncio.to_thread(_send)
        except (smtplib.SMTPException, OSError) as exc:
            logger.exception("Outreach email send failed for %s", outreach_id)
            raise ValueError(f"SMTP could not send the email: {exc}") from exc

        email.status = "sent"
        email.sent_at = datetime.now(timezone.utc)
        opportunity = self.db.query(BacklinkOpportunity).filter(
            BacklinkOpportunity.id == email.opportunity_id,
            BacklinkOpportunity.company_id == company.id,
        ).first()
        if opportunity and opportunity.status == "pending":
            opportunity.status = "contacted"
        self.db.commit()
        self.db.refresh(email)
        return email

    # ============================================================
    # Statistics - database-backed only
    # ============================================================

    def get_statistics(self, company_id: str) -> Dict[str, Any]:
        backlinks = self.db.query(Backlink).filter(Backlink.company_id == company_id).all()
        total = len(backlinks)
        toxic = sum(1 for b in backlinks if b.status == "toxic")
        referring_domains = len({urlsplit(b.source_url).netloc.lower() for b in backlinks if b.source_url})
        known_da = [b.domain_authority for b in backlinks if b.domain_authority and b.domain_authority > 0]
        avg_da = int(sum(known_da) / len(known_da)) if known_da else None
        today = datetime.now(timezone.utc)
        month_ago = today - timedelta(days=30)
        new_this_month = sum(1 for b in backlinks if b.detected_at and b.detected_at >= month_ago)

        link_types: dict[str, int] = {}
        for b in backlinks:
            link_types[b.link_type] = link_types.get(b.link_type, 0) + 1

        return {
            "total": total,
            "referring_domains": referring_domains,
            "domain_authority": avg_da,
            "toxic_links": toxic,
            "new_this_month": new_this_month,
            "new_domains": None,
            "da_change": None,
            "toxic_fixed": None,
            "growth_history": [],
            "link_types": link_types,
        }
