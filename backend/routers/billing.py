from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps.current_user import get_current_user, require_super_admin
from database.database import get_db
from models.billing import BillingSettings, PaymentTransaction, Subscription
from models.company import Company
from models.user import User
from schemas.billing import (
    BillingSettingsResponse,
    BillingSettingsUpdate,
    PaymentCreate,
    PaymentResponse,
    PlanResponse,
    QRResponse,
    SubscriptionResponse,
)
from services.billing_service import activate_subscription, get_settings, make_upi_qr, plan_details

router = APIRouter(prefix="/billing", tags=["Billing"])
admin_router = APIRouter(prefix="/admin/billing", tags=["Super Admin Billing"])


def _settings_response(settings: BillingSettings) -> BillingSettingsResponse:
    return BillingSettingsResponse.model_validate(settings, from_attributes=True)


def _subscription_response(subscription: Subscription | None, company_id: str, company: Company | None) -> SubscriptionResponse:
    if subscription:
        return SubscriptionResponse.model_validate(subscription, from_attributes=True)
    return SubscriptionResponse(
        id=None,
        company_id=company_id,
        account_type=None,
        plan_code=getattr(company, "subscription_plan", None),
        amount=None,
        currency=None,
        billing_cycle=None,
        status=getattr(company, "subscription_status", "unknown"),
        trial_started_at=None,
        trial_ends_at=getattr(company, "trial_ends_at", None),
        started_at=None,
        expires_at=None,
        next_billing_date=None,
        grandfathered=True,
    )


@router.get("/plans", response_model=list[PlanResponse])
def plans(db: Session = Depends(get_db)):
    settings = get_settings(db)
    return [
        PlanResponse(code="single_workspace", name="Single Workspace", amount=settings.single_workspace_price, currency=settings.currency, billing_cycle=settings.billing_cycle, trial_days=settings.trial_days),
        PlanResponse(code="agency", name="Agency", amount=settings.agency_price, currency=settings.currency, billing_cycle=settings.billing_cycle, trial_days=settings.trial_days),
    ]


@router.get("/me", response_model=SubscriptionResponse)
def my_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.company_id:
        raise HTTPException(status_code=400, detail="User is not assigned to a workspace.")
    company = db.get(Company, current_user.company_id)
    subscription = db.scalar(select(Subscription).where(Subscription.company_id == current_user.company_id).order_by(Subscription.created_at.desc()))
    return _subscription_response(subscription, current_user.company_id, company)


@router.get("/settings", response_model=BillingSettingsResponse)
def public_payment_settings(db: Session = Depends(get_db)):
    return _settings_response(get_settings(db))


@router.get("/qr/{plan_code}", response_model=QRResponse)
def payment_qr(plan_code: str, db: Session = Depends(get_db)):
    try:
        return make_upi_qr(db, plan_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    request: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.company_id:
        raise HTTPException(status_code=400, detail="User is not assigned to a workspace.")

    company = db.get(Company, current_user.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    name, amount, settings = plan_details(db, request.plan_code)
    subscription = db.scalar(
        select(Subscription)
        .where(Subscription.company_id == company.id, Subscription.plan_code == request.plan_code)
        .order_by(Subscription.created_at.desc())
    )
    if subscription is None:
        raise HTTPException(status_code=400, detail="No subscription exists for this workspace and plan.")

    payment = PaymentTransaction(
        company_id=company.id,
        subscription_id=subscription.id,
        plan_code=request.plan_code,
        amount=amount,
        currency=settings.currency,
        payment_method=request.payment_method,
        status="pending",
        transaction_reference=request.transaction_reference,
        bank_reference=request.bank_reference,
        proof_url=request.proof_url,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@admin_router.get("/settings", response_model=BillingSettingsResponse, dependencies=[Depends(require_super_admin)])
def admin_get_settings(db: Session = Depends(get_db)):
    return _settings_response(get_settings(db))


@admin_router.put("/settings", response_model=BillingSettingsResponse, dependencies=[Depends(require_super_admin)])
def admin_update_settings(
    request: BillingSettingsUpdate,
    db: Session = Depends(get_db),
):
    settings = get_settings(db)
    for field, value in request.model_dump().items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return _settings_response(settings)


@admin_router.get("/payments", response_model=list[PaymentResponse], dependencies=[Depends(require_super_admin)])
def admin_payments(db: Session = Depends(get_db)):
    return db.scalars(select(PaymentTransaction).order_by(PaymentTransaction.created_at.desc()).limit(500)).all()


@admin_router.post("/payments/{payment_id}/verify", response_model=SubscriptionResponse, dependencies=[Depends(require_super_admin)])
def admin_verify_payment(
    payment_id: str,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    payment = db.get(PaymentTransaction, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found.")
    if payment.status == "verified":
        subscription = db.get(Subscription, payment.subscription_id) if payment.subscription_id else None
        company = db.get(Company, payment.company_id)
        return _subscription_response(subscription, payment.company_id, company)
    if payment.status != "pending":
        raise HTTPException(status_code=409, detail=f"Payment is {payment.status}.")

    try:
        subscription = activate_subscription(db, payment, current_user.id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _subscription_response(subscription, payment.company_id, db.get(Company, payment.company_id))
