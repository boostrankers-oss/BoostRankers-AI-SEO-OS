from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database.database import get_db
from services.audit_service import AuditService
from models.user import User
from models.company import Company
from api.deps.current_user import get_current_user, get_current_company
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/run")
async def run_audit(
    url: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
):
    """
    Start a new AI audit with multi-agent orchestration.
    Returns a Server-Sent Events stream.
    """
    logger.info(f"Audit requested for {url} by user {current_user.id}, company {company.id}")
    service = AuditService(db)
    return StreamingResponse(
        service.run_audit(url, current_user, company, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )