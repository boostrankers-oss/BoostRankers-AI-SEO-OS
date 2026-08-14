from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.database import get_db
from models.company import Company
from api.deps.current_user import get_current_company

router = APIRouter(prefix="/api/company", tags=["Company"])

@router.post("/add-credits")
def add_credits(
    amount: int,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    if amount <= 0:
        raise HTTPException(400, "Amount must be positive.")
    company.ai_credits += amount
    db.commit()
    return {"credits": company.ai_credits}