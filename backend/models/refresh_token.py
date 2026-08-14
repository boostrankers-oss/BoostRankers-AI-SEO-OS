from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class RefreshToken(BaseModel):
    """
    Stores refresh tokens issued to authenticated users.

    Supports:
    - Multiple devices
    - Token rotation
    - Logout from single device
    - Logout from all devices
    - Device tracking
    - Session management
    """

    __tablename__ = "refresh_tokens"

    # ---------------------------------------------------------
    # Owner
    # ---------------------------------------------------------

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Token
    # ---------------------------------------------------------

    token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    token_family: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # ---------------------------------------------------------
    # Device Information
    # ---------------------------------------------------------

    device_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    device_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    operating_system: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    browser: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # ---------------------------------------------------------
    # Expiration
    # ---------------------------------------------------------

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ---------------------------------------------------------
    # Security
    # ---------------------------------------------------------

    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    revoke_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    replaced_by_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------

    user = relationship(
        "User",
        back_populates="refresh_tokens",
    )

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at.replace(tzinfo=None)

    @property
    def is_valid(self) -> bool:
        return (
            not self.is_revoked
            and not self.is_expired
        )

    # ---------------------------------------------------------
    # Indexes
    # ---------------------------------------------------------

    __table_args__ = (
        Index("idx_refresh_user", "user_id"),
        Index("idx_refresh_token", "token"),
        Index("idx_refresh_expiry", "expires_at"),
        Index("idx_refresh_revoked", "is_revoked"),
    )

    def revoke(self, reason: str = "manual") -> None:
        """
        Revoke this refresh token.
        """
        self.is_revoked = True
        self.revoked_at = datetime.utcnow()
        self.revoke_reason = reason

    def __repr__(self) -> str:
        return (
            f"<RefreshToken(user_id={self.user_id}, "
            f"revoked={self.is_revoked})>"
        )