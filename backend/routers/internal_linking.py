from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database.database import get_db
from models.company import Company
from api.deps.current_user import get_current_company
from services.internal_linking_service import InternalLinkingService

class InternalLinkingRequest(BaseModel):
    urls: list[str]

class InternalLinkingResponse(BaseModel):
    id: str
    urls: list[str]
    suggestions: list[dict]
    analysis: str
    created_at: str

router = APIRouter(prefix="/internal-linking", tags=["Internal Linking"])

@router.post("/analyze")
async def analyze_internal_linking(
    request: InternalLinkingRequest,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    """Analyze URLs and generate internal linking suggestions."""
    if len(request.urls) < 2:
        raise HTTPException(status_code=400, detail="At least 2 URLs are required.")

    # Check credits
    if company.ai_credits <= 0:
        raise HTTPException(
            status_code=402,
            detail="Insufficient AI credits. Please add budget."
        )

    service = InternalLinkingService(db)
    try:
        suggestion = await service.create_suggestion(request.urls, company)
        db.commit()  # credit is deducted inside create_suggestion
        return {
            "id": suggestion.id,
            "urls": suggestion.urls,
            "suggestions": suggestion.suggestions,
            "analysis": suggestion.analysis,
            "created_at": suggestion.created_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/")
def get_internal_linking_suggestions(
    limit: int = 50,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = InternalLinkingService(db)
    suggestions = service.get_suggestions(company.id, limit)
    return [
        {
            "id": s.id,
            "urls": s.urls,
            "suggestions": s.suggestions,
            "analysis": s.analysis,
            "created_at": s.created_at.isoformat(),
        }
        for s in suggestions
    ]

@router.delete("/{suggestion_id}")
def delete_suggestion(
    suggestion_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = InternalLinkingService(db)
    if not service.delete_suggestion(suggestion_id, company.id):
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return {"success": True}