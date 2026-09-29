from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from urllib.parse import quote

import qrcode
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.billing import BillingSettings, PaymentTransaction, Subscription
from models.company import Company

DEFAULT_SINGLE_PRICE = Decimal("5000.00")
DEFAULT_AGENCY_PRICE = Decimal("15000.00")
DEFAULT_TRIAL_DAYS = 1
DEFAULT_CURRENCY = "INR"
DEFAULT_UPI_ID = "mdarif921@ybl"
DEFAULT_ACCOUNT_HOLDER = "MD ARIF ALAM"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_settings(db: Session) -> BillingSettings:
    settings = db.get(BillingSettings, 1)
    if settings:
        return settings

    settings = BillingSettings(
        id=1,
        single_workspace_price=DEFAULT_SINGLE_PRICE,
        agency_price=DEFAULT_AGENCY_PRICE,
        currency=DEFAULT_CURRENCY,
        billing_cycle="monthly",
        trial_days=DEFAULT_TRIAL_DAYS,
        upi_id=DEFAULT_UPI_ID,
        account_holder_name=DEFAULT_ACCOUNT_HOLDER,
        account_number="50100497971201",
        ifsc_code="HDFC0000609",
        micr_code="110240098",
        swift_code="HDFCINBBDEL",
    )
    db.add(settings)
    db.flush()
    return settings


def plan_details(db: Session, plan_code: str) -> tuple[str, Decimal, BillingSettings]:
    settings = get_settings(db)
    if plan_code == "single_workspace":
        return "Single Workspace", Decimal(settings.single_workspace_price), settings
    if plan_code == "agency":
        return "Agency", Decimal(settings.agency_price), settings
    raise ValueError("Unsupported plan.")


def initialize_new_signup(db: Session, company: Company, account_type: str) -> Subscription:
    """Initialize billing only for a newly created workspace.

    Existing companies are deliberately handled elsewhere and remain unchanged.
    """
    normalized = "agency" if account_type == "agency" else "client"
    plan_code = "agency" if normalized == "agency" else "single_workspace"
    _, amount, settings = plan_details(db, plan_code)
    now = utcnow()
    trial_end = now + timedelta(days=settings.trial_days)

    company.subscription_plan = plan_code
    company.subscription_status = "trial"

    subscription = Subscription(
        company_id=company.id,
        account_type=normalized,
        plan_code=plan_code,
        amount=amount,
        currency=settings.currency,
        billing_cycle=settings.billing_cycle,
        status="trial",
        trial_started_at=now,
        trial_ends_at=trial_end,
        grandfathered=False,
    )
    db.add(subscription)
    db.flush()
    return subscription


def activate_subscription(db: Session, payment: PaymentTransaction, verified_by: str | None) -> Subscription:
    now = utcnow()
    subscription = db.get(Subscription, payment.subscription_id) if payment.subscription_id else None
    if subscription is None:
        raise ValueError("Subscription not found for payment.")

    subscription.status = "active"
    subscription.started_at = now
    subscription.expires_at = now + timedelta(days=30)
    subscription.next_billing_date = subscription.expires_at

    company = db.get(Company, payment.company_id)
    if company:
        company.subscription_plan = subscription.plan_code
        company.subscription_status = "active"
        company.is_active = True

    payment.status = "verified"
    payment.verified_at = now
    payment.paid_at = payment.paid_at or now
    payment.verified_by = verified_by
    db.flush()
    return subscription


def make_upi_qr(db: Session, plan_code: str) -> dict:
    _, amount, settings = plan_details(db, plan_code)
    amount_text = f"{amount:.2f}"
    upi_uri = (
        "upi://pay"
        f"?pa={quote(settings.upi_id, safe='')}"
        f"&pn={quote(settings.account_holder_name, safe='')}"
        f"&am={amount_text}"
        f"&cu={settings.currency}"
    )

    image = qrcode.make(upi_uri)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    return {
        "plan_code": plan_code,
        "amount": amount,
        "currency": settings.currency,
        "upi_id": settings.upi_id,
        "upi_uri": upi_uri,
        "qr_data_url": f"data:image/png;base64,{encoded}",
    }
