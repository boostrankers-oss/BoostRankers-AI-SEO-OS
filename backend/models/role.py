from __future__ import annotations

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class Role(BaseModel):
    """
    Role model for RBAC.
    Examples:
    - Super Admin
    - Agency Admin
    - Manager
    - SEO Executive
    - Client
    """

    __tablename__ = "roles"

    # ---------------------------------------------------------
    # Basic Information
    # ---------------------------------------------------------

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
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
        default=False,
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

    users = relationship(
        "User",
        back_populates="role_ref",
    )

    permissions = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles",
        lazy="selectin",
    )

    # ---------------------------------------------------------
    # Indexes
    # ---------------------------------------------------------

    __table_args__ = (
        Index("idx_role_name", "name"),
        Index("idx_role_active", "is_active"),
    )

    def __str__(self) -> str:
        return self.display_name