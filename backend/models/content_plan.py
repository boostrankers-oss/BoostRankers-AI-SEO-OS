from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import BaseModel


class ContentPlan(BaseModel):
    """Persisted 90-day AI content calendar."""

    __tablename__ = "content_plans"

    company_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    topic: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    items: Mapped[list] = mapped_column(JSON, nullable=False)
    item_count: Mapped[int] = mapped_column(nullable=False, default=90)