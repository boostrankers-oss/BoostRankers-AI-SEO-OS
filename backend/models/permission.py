from __future__ import annotations

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class Permission(BaseModel):
    """
    Permission model for Role-Based Access Control (RBAC).

    Examples:
        users.read
        users.create
        users.update
        users.delete

        audits.run
        reports.export

        settings.update
    """

    __tablename__ = "permissions"

    # ---------------------------------------------------------
    # Identity
    # ---------------------------------------------------------

    name: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

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

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ---------------------------------------------------------
    # Status
    # ---------------------------------------------------------

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------

    roles = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions",
        lazy="selectin",
    )

    # ---------------------------------------------------------
    # Indexes
    # ---------------------------------------------------------

    __table_args__ = (
        Index("idx_permission_name", "name"),
        Index("idx_permission_module", "module"),
        Index("idx_permission_action", "action"),
        Index("idx_permission_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Permission(name='{self.name}')>"