from __future__ import annotations

from sqlalchemy import (
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class AuditLog(BaseModel):
    """
    Records important system and user actions.

    Examples:
    - User Login
    - User Logout
    - Password Reset
    - Client Created
    - SEO Audit Started
    - Report Generated
    - Settings Updated
    - API Key Changed
    """

    __tablename__ = "audit_logs"

    # ---------------------------------------------------------
    # User / Company
    # ---------------------------------------------------------

    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ---------------------------------------------------------
    # Action
    # ---------------------------------------------------------

    module: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    resource_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # ---------------------------------------------------------
    # Request Information
    # ---------------------------------------------------------

    method: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    endpoint: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status_code: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    # ---------------------------------------------------------
    # Client Information
    # ---------------------------------------------------------

    ip_address: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    device: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    browser: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    operating_system: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    # ---------------------------------------------------------
    # Result
    # ---------------------------------------------------------

    success: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ---------------------------------------------------------
    # Extra Data
    # ---------------------------------------------------------

    metadata_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------

    user = relationship(
        "User",
        back_populates="audit_logs",
    )

    company = relationship(
        "Company",
        lazy="joined",
    )
    
    company = relationship(
        "Company",
        back_populates="audit_logs",
    )

    # ---------------------------------------------------------
    # Indexes
    # ---------------------------------------------------------

    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_company", "company_id"),
        Index("idx_audit_module", "module"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_success", "success"),
        Index("idx_audit_created", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(module='{self.module}', "
            f"action='{self.action}', "
            f"success={self.success})>"
        )