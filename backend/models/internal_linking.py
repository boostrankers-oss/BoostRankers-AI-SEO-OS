from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class InternalLinkingSuggestion(BaseModel):
    __tablename__ = "internal_linking_suggestions"

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    urls: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    suggestions: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    company = relationship("Company", back_populates="internal_linking_suggestions")