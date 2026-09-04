from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps.current_user import get_current_user
from database.session import get_db
from models.content_plan import ContentPlan
from models.user import User

router = APIRouter()


class ContentPlanCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    start_date: date
    items: list[dict[str, Any]] = Field(min_length=90, max_length=90)


def _scope_filter(current_user: User):
    if current_user.company_id:
        return ContentPlan.company_id == current_user.company_id
    return ContentPlan.created_by == current_user.id


def _serialize(plan: ContentPlan, include_items: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": plan.id,
        "topic": plan.topic,
        "start_date": plan.start_date.isoformat(),
        "item_count": plan.item_count,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }
    if include_items:
        data["items"] = plan.items
    return data


@router.get("/content-plans")
def list_content_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plans = db.scalars(
        select(ContentPlan)
        .where(_scope_filter(current_user), ContentPlan.deleted_at.is_(None))
        .order_by(ContentPlan.created_at.desc())
    ).all()
    return {"success": True, "plans": [_serialize(p, False) for p in plans]}


@router.get("/content-plans/{plan_id}")
def get_content_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.scalar(
        select(ContentPlan).where(
            ContentPlan.id == plan_id,
            _scope_filter(current_user),
            ContentPlan.deleted_at.is_(None),
        )
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Content plan not found.")
    return {"success": True, "plan": _serialize(plan, True)}


@router.post("/content-plans")
def create_content_plan(
    request: ContentPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required.")

    for index, item in enumerate(request.items, start=1):
        if not str(item.get("title", "")).strip() or not str(item.get("keyword", "")).strip():
            raise HTTPException(
                status_code=400,
                detail=f"Content item {index} is missing a title or keyword.",
            )

    plan = ContentPlan(
        company_id=current_user.company_id,
        created_by=current_user.id,
        updated_by=current_user.id,
        topic=topic,
        start_date=request.start_date,
        items=request.items,
        item_count=90,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return {
        "success": True,
        "message": "90-day content plan saved.",
        "plan": _serialize(plan, True),
    }


@router.delete("/content-plans/{plan_id}")
def delete_content_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.scalar(
        select(ContentPlan).where(
            ContentPlan.id == plan_id,
            _scope_filter(current_user),
            ContentPlan.deleted_at.is_(None),
        )
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Content plan not found.")

    plan.deleted_at = datetime.now(UTC)
    plan.updated_by = current_user.id
    db.commit()
    return {"success": True, "message": "Content plan deleted."}
