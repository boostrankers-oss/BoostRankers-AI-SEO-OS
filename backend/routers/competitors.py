from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.database import get_db
from models.company import Company
from api.deps.current_user import get_current_company
from services.competitor_service import CompetitorService

# ✅ Set prefix here – this will be appended to the route paths
router = APIRouter(prefix="/competitors", tags=["Competitors"])

@router.get("")   # empty string – matches /competitors (no trailing slash)
def get_competitors(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = CompetitorService(db)
    competitors = service.get_competitors(company.id)
    return [
        {
            "id": c.id,
            "domain": c.domain,
            "traffic": c.traffic,
            "keywords": c.keywords,
            "backlinks": c.backlinks,
            "da": c.da,
            "gap": c.gap,
            "analysis": c.analysis,
            "created_at": c.created_at.isoformat(),
        }
        for c in competitors
    ]

@router.post("")  # empty string – matches /competitors
async def add_competitor(
    domain: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = CompetitorService(db)
    try:
        competitor = await service.add_competitor(domain, company)
        return {
            "id": competitor.id,
            "domain": competitor.domain,
            "traffic": competitor.traffic,
            "keywords": competitor.keywords,
            "backlinks": competitor.backlinks,
            "da": competitor.da,
            "gap": competitor.gap,
            "analysis": competitor.analysis,
            "created_at": competitor.created_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{competitor_id}")
def delete_competitor(
    competitor_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = CompetitorService(db)
    if not service.delete_competitor(competitor_id, company.id):
        raise HTTPException(status_code=404, detail="Competitor not found")
    return {"success": True}