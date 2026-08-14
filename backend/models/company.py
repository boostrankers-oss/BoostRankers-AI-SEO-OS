from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,   # ✅ Added Integer
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class Company(BaseModel):
    __tablename__ = "companies"

    # ------------------------------------------------------------------
    # Basic Information
    # ------------------------------------------------------------------

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        unique=True,
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        unique=True,
        index=True,
    )

    legal_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Contact
    # ------------------------------------------------------------------

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    website: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    domain: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Address
    # ------------------------------------------------------------------

    address_line1: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    address_line2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    postal_code: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    timezone: Mapped[str] = mapped_column(
        String(100),
        default="UTC",
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="USD",
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Branding
    # ------------------------------------------------------------------

    logo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    favicon_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    primary_color: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    secondary_color: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    subscription_plan: Mapped[str] = mapped_column(
        String(50),
        default="free",
        nullable=False,
    )

    subscription_status: Mapped[str] = mapped_column(
        String(50),
        default="trial",
        nullable=False,
    )

    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    api_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    webhook_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    max_users: Mapped[int] = mapped_column(
        default=5,
        nullable=False,
    )

    max_projects: Mapped[int] = mapped_column(
        default=10,
        nullable=False,
    )

    # ------------------------------------------------------------------
    # AI Credits (NEW)
    # ------------------------------------------------------------------

    ai_credits: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    users = relationship(
        "User",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    clients = relationship(
        "Client",
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    audit_logs = relationship(
        "AuditLog",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    reports = relationship(
        "Report",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    
    internal_linking_suggestions = relationship(
    "InternalLinkingSuggestion",
    back_populates="company",
    cascade="all, delete-orphan",
    )
    
    competitors = relationship("Competitor", back_populates="company", cascade="all, delete-orphan")
    
    backlinks = relationship("Backlink", back_populates="company", cascade="all, delete-orphan")
    backlink_opportunities = relationship("BacklinkOpportunity", back_populates="company", cascade="all, delete-orphan")
    outreach_emails = relationship("OutreachEmail", back_populates="company", cascade="all, delete-orphan")

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------

    __table_args__ = (
        Index("idx_company_slug", "slug"),
        Index("idx_company_email", "email"),
        Index("idx_company_plan", "subscription_plan"),
        Index("idx_company_active", "is_active"),
    )
