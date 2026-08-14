from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
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
        String(36), primary_key=True, default=generate_uuid
    )
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    company = relationship("Company", back_populates="clients")
    
    reports = relationship(
    "Report",
    back_populates="client",
    cascade="all, delete-orphan",
    )

    # ✅ ADD THIS LINE
    reports = relationship(
        "Report",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    # ... all the existing fields (business_name, website, etc.) remain unchanged ...
    business_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # ... etc.