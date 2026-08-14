from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class User(BaseModel):
    """
    Production-ready User model.
    """

    __tablename__ = "users"

    # -------------------------------------------------------------
    # Company
    # -------------------------------------------------------------

    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # -------------------------------------------------------------
    # Role (future RBAC)
    # -------------------------------------------------------------

    role_id: Mapped[str | None] = mapped_column(
        ForeignKey("roles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Keep existing role for backward compatibility
    role: Mapped[str] = mapped_column(
        String(50),
        default="Client",
        nullable=False,
        index=True,
    )

    # -------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    job_title: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    # -------------------------------------------------------------
    # Account Status
    # -------------------------------------------------------------

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

    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # -------------------------------------------------------------
    # Security
    # -------------------------------------------------------------

    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # -------------------------------------------------------------
    # MFA Ready
    # -------------------------------------------------------------

    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    mfa_secret: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # -------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------

    company = relationship(
        "Company",
        back_populates="users",
    )

    role_ref = relationship(
        "Role",
        back_populates="users",
    )

    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    audit_logs = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # -------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    # -------------------------------------------------------------
    # Indexes
    # -------------------------------------------------------------

    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_company", "company_id"),
        Index("idx_user_role", "role"),
        Index("idx_user_active", "is_active"),
    )