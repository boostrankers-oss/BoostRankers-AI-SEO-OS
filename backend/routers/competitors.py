from __future__ import annotations

import json

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy.orm import Session

from api.deps.current_user import get_current_company
from database.database import get_db
from models.company import Company
from services.competitor_service import (
    CompetitorService,
)


router = APIRouter(
    prefix="/competitors",
    tags=["Competitors"],
)


def _parse_details(
    analysis: str | None,
) -> dict:
    return CompetitorService.parse_details(
        analysis
    )


def _serialize_competitor(
    competitor,
) -> dict:

    details = _parse_details(
        competitor.analysis
    )

    strategy = details.get(
        "strategy",
        {},
    )

    # Backwards-compatible plain text.
    if not isinstance(
        strategy,
        dict,
    ):
        strategy = {}

    return {
        "id": str(
            competitor.id
        ),
        "domain": competitor.domain,
        "traffic": competitor.traffic,
        "keywords": competitor.keywords,
        "backlinks": competitor.backlinks,
        "da": competitor.da,
        "gap": competitor.gap,

        # Keep old field for compatibility.
        "analysis": (
            strategy.get(
                "executive_summary",
                "",
            )
            or ""
        ),

        # New structured intelligence.
        "details": details,

        "created_at": (
            competitor.created_at.isoformat()
            if competitor.created_at
            else None
        ),
    }


@router.get("")
def get_competitors(
    db: Session = Depends(get_db),
    company: Company = Depends(
        get_current_company
    ),
):
    service = CompetitorService(
        db
    )

    competitors = service.get_competitors(
        company.id
    )

    return [
        _serialize_competitor(
            competitor
        )
        for competitor in competitors
    ]


@router.get("/{competitor_id}")
def get_competitor(
    competitor_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(
        get_current_company
    ),
):
    service = CompetitorService(
        db
    )

    competitor = service.get_competitor(
        competitor_id,
        company.id,
    )

    if not competitor:
        raise HTTPException(
            status_code=404,
            detail="Competitor not found",
        )

    return _serialize_competitor(
        competitor
    )


@router.post("")
async def add_competitor(
    domain: str = Query(
        ...,
        min_length=3,
        max_length=500,
    ),
    target_domain: str | None = Query(
        default=None,
        max_length=500,
    ),
    db: Session = Depends(get_db),
    company: Company = Depends(
        get_current_company
    ),
):
    service = CompetitorService(
        db
    )

    try:
        competitor = (
            await service.add_competitor(
                domain=domain,
                company=company,
                target_domain=target_domain,
            )
        )

        return _serialize_competitor(
            competitor
        )

    except ValueError as exc:
        message = str(exc)

        if (
            "credits" in message.lower()
        ):
            raise HTTPException(
                status_code=402,
                detail=message,
            )

        if (
            "anthropic"
            in message.lower()
        ):
            raise HTTPException(
                status_code=502,
                detail=message,
            )

        raise HTTPException(
            status_code=400,
            detail=message,
        )


@router.delete("/{competitor_id}")
def delete_competitor(
    competitor_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(
        get_current_company
    ),
):
    service = CompetitorService(
        db
    )

    deleted = (
        service.delete_competitor(
            competitor_id,
            company.id,
        )
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Competitor not found",
        )

    return {
        "success": True,
        "message": "Competitor deleted successfully.",
    }