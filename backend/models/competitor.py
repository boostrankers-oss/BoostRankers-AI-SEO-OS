from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel


class Competitor(BaseModel):
    __tablename__ = "competitors"

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    traffic: Mapped[str | None] = mapped_column(String(50), nullable=True)
    keywords: Mapped[int] = mapped_column(Integer, default=0)
    backlinks: Mapped[int] = mapped_column(Integer, default=0)
    da: Mapped[int] = mapped_column(Integer, default=0)
    gap: Mapped[int] = mapped_column(Integer, default=0)
    analysis: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    company = relationship("Company", back_populates="competitors")