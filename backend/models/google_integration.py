from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import BaseModel


class GoogleIntegration(BaseModel):
    """Encrypted Google OAuth connection for one tenant/company and provider."""

    __tablename__ = "google_integrations"

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    access_token_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    refresh_token_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    token_type: Mapped[str] = mapped_column(
        String(30),
        default="Bearer",
        nullable=False,
    )

    scope: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    account_email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    selected_property: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "provider",
            name="uq_google_integrations_company_provider",
        ),
        Index(
            "ix_google_integrations_company_provider",
            "company_id",
            "provider",
        ),
    )
