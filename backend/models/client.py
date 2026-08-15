from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import BaseModel


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Client(BaseModel):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Business
    # =========================================================

    business_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    legal_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    website: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    industry: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )

    business_type: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    company_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    logo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # =========================================================
    # Contact
    # =========================================================

    contact_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    designation: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    secondary_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    whatsapp: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # =========================================================
    # Address
    # =========================================================

    address_line1: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    address_line2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    state: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    postal_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    timezone: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="UTC",
        server_default="UTC",
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="USD",
        server_default="USD",
    )

    # =========================================================
    # SEO
    # =========================================================

    primary_keyword: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    target_location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    target_country: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    target_language: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="en",
        server_default="en",
    )

    cms: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    hosting_provider: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    google_business_profile: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # =========================================================
    # Integrations
    # =========================================================

    google_search_console_connected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    google_analytics_connected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    google_tag_manager_connected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    bing_webmaster_connected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # =========================================================
    # SEO Scores
    # =========================================================

    overall_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    technical_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    content_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    eeat_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    local_seo_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    backlinks_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    keyword_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    schema_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    core_web_vitals_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    ai_search_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
        server_default="0",
    )

    # =========================================================
    # SEO Statistics
    # =========================================================

    total_keywords: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    ranked_keywords: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    total_backlinks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    referring_domains: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    total_audits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    critical_issues: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    warnings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    passed_checks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # =========================================================
    # Status / Subscription
    # =========================================================

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )

    priority: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="normal",
        server_default="normal",
    )

    subscription_plan: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="free",
        server_default="free",
    )

    billing_cycle: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="monthly",
        server_default="monthly",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    # =========================================================
    # Audit Dates
    # =========================================================

    first_audit_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True),
    nullable=True,
    )

    last_audit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    next_audit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =========================================================
    # Metadata
    # =========================================================

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tags: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # =========================================================
    # Relationships
    # =========================================================

    company = relationship(
        "Company",
        back_populates="clients",
    )

    reports = relationship(
        "Report",
        back_populates="client",
        cascade="all, delete-orphan",
    )