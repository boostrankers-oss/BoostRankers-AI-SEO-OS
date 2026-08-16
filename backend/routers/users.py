from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps.current_user import get_current_user
from database.database import get_db
from models.company import Company
from models.user import User


router = APIRouter()


# ============================================================
# Super Admin Authorization
# ============================================================

def require_super_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access required.",
        )

    return current_user


# ============================================================
# Current User
# ============================================================

@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role,
        "company_id": current_user.company_id,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "is_superuser": current_user.is_superuser,
        "last_login": (
            current_user.last_login.isoformat()
            if current_user.last_login
            else None
        ),
        "created_at": (
            current_user.created_at.isoformat()
            if current_user.created_at
            else None
        ),
    }


# ============================================================
# Super Admin - All Users
# ============================================================

@router.get("")
def list_users(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    users = db.scalars(
        select(User)
        .order_by(User.created_at.desc())
    ).all()

    return [
        {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "company_id": user.company_id,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "is_superuser": user.is_superuser,
            "last_login": (
                user.last_login.isoformat()
                if user.last_login
                else None
            ),
            "created_at": (
                user.created_at.isoformat()
                if user.created_at
                else None
            ),
        }
        for user in users
    ]


# ============================================================
# Super Admin - Platform Statistics
# ============================================================

@router.get("/stats")
def get_user_stats(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    now = datetime.now(UTC)

    start_of_today = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    start_of_month = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    total_users = db.scalar(
        select(func.count(User.id))
    ) or 0

    active_users = db.scalar(
        select(func.count(User.id))
        .where(User.is_active.is_(True))
    ) or 0

    inactive_users = db.scalar(
        select(func.count(User.id))
        .where(User.is_active.is_(False))
    ) or 0

    verified_users = db.scalar(
        select(func.count(User.id))
        .where(User.is_verified.is_(True))
    ) or 0

    unverified_users = db.scalar(
        select(func.count(User.id))
        .where(User.is_verified.is_(False))
    ) or 0

    total_companies = db.scalar(
        select(func.count(Company.id))
    ) or 0

    active_companies = db.scalar(
        select(func.count(Company.id))
        .where(Company.is_active.is_(True))
    ) or 0

    inactive_companies = db.scalar(
        select(func.count(Company.id))
        .where(Company.is_active.is_(False))
    ) or 0

    new_users_today = db.scalar(
        select(func.count(User.id))
        .where(User.created_at >= start_of_today)
    ) or 0

    new_users_this_month = db.scalar(
        select(func.count(User.id))
        .where(User.created_at >= start_of_month)
    ) or 0

    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "verified_users": verified_users,
        "unverified_users": unverified_users,
        "total_companies": total_companies,
        "active_companies": active_companies,
        "inactive_companies": inactive_companies,
        "new_users_today": new_users_today,
        "new_users_this_month": new_users_this_month,
    }