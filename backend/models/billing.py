from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import BaseModel


def _uuid() -> str:
    return str(uuid.uuid4())


class BillingSettings(BaseModel):
    __tablename__ = "billing_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    single_workspace_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=5000)
    agency_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=15000)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    billing_cycle: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    upi_id: Mapped[str] = mapped_column(String(255), nullable=False)
    account_holder_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_number: Mapped[str] = mapped_column(String(50), nullable=False)
    ifsc_code: Mapped[str] = mapped_column(String(20), nullable=False)
    micr_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    swift_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Subscription(BaseModel):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False)
    plan_code: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    billing_cycle: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_billing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grandfathered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PaymentTransaction(BaseModel):
    __tablename__ = "payment_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id: Mapped[str | None] = mapped_column(ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    plan_code: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False, default="upi")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    transaction_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    bank_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    proof_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
