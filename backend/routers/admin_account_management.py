from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.database import get_db
from models.company import Company
from models.client import Client
from models.user import User
from api.deps.current_user import require_super_admin

router = APIRouter(
    prefix="/admin/accounts",
    tags=["Super Admin Account Management"],
)


class AccountStatusRequest(BaseModel):
    is_active: bool


class AccountTypeRequest(BaseModel):
    account_type: str = Field(pattern="^(client|agency)$")


def _account_type(db: Session, company_id: str) -> str:
    roles = db.scalars(
        select(User.role).where(
            User.company_id == company_id,
            User.is_active.is_(True),
        )
    ).all()
    if "agency_admin" in roles or "manager" in roles or "seo_specialist" in roles:
        return "agency"
    return "client"


def _serialize_company(db: Session, company: Company) -> dict:
    users = db.scalars(
        select(User).where(User.company_id == company.id)
    ).all()
    client_count = db.scalar(
        select(func.count(Client.id)).where(Client.company_id == company.id)
    ) or 0
    return {
        "company_id": company.id,
        "company_name": company.name,
        "account_type": _account_type(db, company.id),
        "is_active": bool(company.is_active),
        "client_count": int(client_count),
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "role": u.role,
                "is_active": bool(u.is_active),
            }
            for u in users
        ],
    }


@router.get("")
def list_accounts(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    companies = db.scalars(
        select(Company).order_by(Company.created_at.desc())
    ).all()
    return [_serialize_company(db, company) for company in companies]


@router.patch("/{company_id}/status")
def set_account_status(
    company_id: str,
    request: AccountStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found.")

    users = db.scalars(
        select(User).where(User.company_id == company_id)
    ).all()

    if any(u.id == current_user.id for u in users):
        raise HTTPException(
            status_code=400,
            detail="The Super Admin account cannot be disabled from this endpoint.",
        )

    company.is_active = request.is_active
    for user in users:
        user.is_active = request.is_active

    db.commit()
    db.refresh(company)

    return {
        "success": True,
        "message": "Account activated." if request.is_active else "Account deactivated.",
        "account": _serialize_company(db, company),
    }


@router.post("/{company_id}/convert")
def convert_account_type(
    company_id: str,
    request: AccountTypeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found.")

    users = db.scalars(
        select(User).where(
            User.company_id == company_id,
            User.is_active.is_(True),
        )
    ).all()

    if any(u.id == current_user.id or u.role == "super_admin" for u in users):
        raise HTTPException(
            status_code=400,
            detail="A Super Admin workspace cannot be converted.",
        )

    target = request.account_type
    current = _account_type(db, company_id)

    if target == current:
        return {
            "success": True,
            "message": f"Account is already configured as {target}.",
            "account": _serialize_company(db, company),
        }

    if not users:
        raise HTTPException(status_code=400, detail="Account has no active user.")

    if target == "client":
        clients = db.scalars(
            select(Client).where(Client.company_id == company_id)
        ).all()

        if len(clients) != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Agency cannot be converted to a single-client account "
                    "while it has multiple client records."
                ),
            )

        if len(users) != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Agency cannot be converted to a single-client account "
                    "while it has multiple active users."
                ),
            )

        users[0].role = "client"
        clients[0].email = users[0].email

    else:
        # Client -> Agency keeps the existing company and client record.
        # The account can then add more clients through the normal Clients API.
        primary = next(
            (u for u in users if u.role == "client"),
            users[0],
        )
        primary.role = "agency_admin"

    db.commit()
    db.refresh(company)

    return {
        "success": True,
        "message": f"Account converted to {target}.",
        "account": _serialize_company(db, company),
    }
