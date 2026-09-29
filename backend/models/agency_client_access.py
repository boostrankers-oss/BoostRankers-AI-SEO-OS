from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class AgencyClientAccess(Base):
    """Explicit agency-to-client authorization without changing client ownership."""

    __tablename__ = "agency_client_access"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    agency_company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    granted_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("agency_company_id", "client_id", name="uq_agency_client_access"),
        Index("ix_agency_client_access_agency", "agency_company_id"),
        Index("ix_agency_client_access_client", "client_id"),
        Index("ix_agency_client_access_status", "status"),
    )
