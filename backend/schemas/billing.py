from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PlanResponse(BaseModel):
    code: str
    name: str
    amount: Decimal
    currency: str
    billing_cycle: str
    trial_days: int


class BillingSettingsResponse(BaseModel):
    single_workspace_price: Decimal
    agency_price: Decimal
    currency: str
    billing_cycle: str
    trial_days: int
    upi_id: str
    account_holder_name: str
    account_number: str
    ifsc_code: str
    micr_code: str | None
    swift_code: str | None
    bank_name: str | None


class BillingSettingsUpdate(BaseModel):
    single_workspace_price: Decimal = Field(..., gt=0)
    agency_price: Decimal = Field(..., gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    billing_cycle: str = Field(default="monthly", min_length=1, max_length=20)
    trial_days: int = Field(default=1, ge=0, le=30)
    upi_id: str = Field(..., min_length=3, max_length=255)
    account_holder_name: str = Field(..., min_length=2, max_length=255)
    account_number: str = Field(..., min_length=4, max_length=50)
    ifsc_code: str = Field(..., min_length=4, max_length=20)
    micr_code: str | None = Field(default=None, max_length=20)
    swift_code: str | None = Field(default=None, max_length=20)
    bank_name: str | None = Field(default=None, max_length=255)


class PaymentCreate(BaseModel):
    plan_code: str = Field(..., pattern="^(single_workspace|agency)$")
    payment_method: str = Field(default="upi", pattern="^(upi|bank_transfer)$")
    transaction_reference: str | None = Field(default=None, max_length=255)
    bank_reference: str | None = Field(default=None, max_length=255)
    proof_url: str | None = None


class PaymentResponse(BaseModel):
    id: str
    company_id: str
    subscription_id: str | None
    plan_code: str
    amount: Decimal
    currency: str
    payment_method: str
    status: str
    transaction_reference: str | None
    bank_reference: str | None
    paid_at: datetime | None
    verified_at: datetime | None


class SubscriptionResponse(BaseModel):
    id: str | None
    company_id: str
    account_type: str | None
    plan_code: str | None
    amount: Decimal | None
    currency: str | None
    billing_cycle: str | None
    status: str
    trial_started_at: datetime | None
    trial_ends_at: datetime | None
    started_at: datetime | None
    expires_at: datetime | None
    next_billing_date: datetime | None
    grandfathered: bool = False


class QRResponse(BaseModel):
    plan_code: str
    amount: Decimal
    currency: str
    upi_id: str
    upi_uri: str
    qr_data_url: str
