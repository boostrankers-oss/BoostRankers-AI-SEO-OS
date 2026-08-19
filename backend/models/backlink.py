from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class Backlink(BaseModel):
    __tablename__ = "backlinks"

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    anchor_text: Mapped[str] = mapped_column(String(255), nullable=False)
    link_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # dofollow, nofollow, sponsored, ugc

    domain_authority: Mapped[int] = mapped_column(Integer, default=0)
    spam_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
    )  # active, toxic, lost

    ai_analysis: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    company = relationship(
        "Company",
        back_populates="backlinks",
    )


class BacklinkOpportunity(BaseModel):
    __tablename__ = "backlink_opportunities"

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    domain: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    opportunity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # guest_post, resource_page, news_article

    domain_authority: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    relevance: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # high, medium, low

    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
    )  # pending, contacted, success, failed

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    company = relationship(
        "Company",
        back_populates="backlink_opportunities",
    )

    # ------------------------------------------------------------
    # Outreach relationship
    # ------------------------------------------------------------
    #
    # OutreachEmail.opportunity uses:
    #     back_populates="emails"
    #
    # Therefore this relationship MUST exist with exactly
    # the same attribute name.
    #
    emails = relationship(
        "OutreachEmail",
        back_populates="opportunity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OutreachEmail(BaseModel):
    __tablename__ = "outreach_emails"

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    opportunity_id: Mapped[str] = mapped_column(
        ForeignKey("backlink_opportunities.id", ondelete="CASCADE"),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
    )  # draft, sent, opened, replied

    opportunity = relationship(
        "BacklinkOpportunity",
        back_populates="emails",
    )

    company = relationship(
        "Company",
        back_populates="outreach_emails",
    )