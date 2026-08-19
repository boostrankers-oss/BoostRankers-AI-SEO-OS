from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from database.database import get_db
from models.company import Company
from api.deps.current_user import get_current_company
from services.backlink_service import BacklinkService

class BacklinkCreate(BaseModel):
    source_url: str
    target_url: str
    anchor_text: str
    link_type: str
    domain_authority: int | None = None
    spam_score: int | None = None



class WordPressBacklinkCreate(BaseModel):
    wordpress_site: str = Field(..., min_length=8, max_length=500)
    wordpress_username: str = Field(..., min_length=1, max_length=255)
    wordpress_application_password: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=5, max_length=255)
    content: str = Field(..., min_length=300)
    target_url: str = Field(..., min_length=8, max_length=500)
    anchor_text: str = Field(..., min_length=1, max_length=255)
    status: str = Field(default="publish")

router = APIRouter(prefix="/backlinks", tags=["Backlinks"])

@router.get("/statistics")
def get_statistics(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = BacklinkService(db)
    return service.get_statistics(company.id)

@router.get("/")
def get_backlinks(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = BacklinkService(db)
    return service.get_backlinks(company.id)

@router.post("/")
async def add_backlink(
    data: BacklinkCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = BacklinkService(db)
    try:
        backlink = await service.add_backlink(company.id, data.model_dump())
        return backlink
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/publish/wordpress")
async def publish_wordpress_backlink(
    data: WordPressBacklinkCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = BacklinkService(db)
    try:
        return await service.publish_wordpress_backlink(
            company.id,
            data.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.delete("/{backlink_id}")
def delete_backlink(
    backlink_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = BacklinkService(db)
    if not service.delete_backlink(backlink_id, company.id):
        raise HTTPException(status_code=404, detail="Backlink not found")
    return {"success": True}

@router.post("/{backlink_id}/analyze")
async def analyze_backlink(
    backlink_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = BacklinkService(db)
    try:
        analysis = await service.analyze_backlink(backlink_id, company)
        return {"analysis": analysis}
    except ValueError as e:
        raise HTTPException(status_code=402 if "credits" in str(e) else 400, detail=str(e))

@router.get("/opportunities")
def get_opportunities(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = BacklinkService(db)
    return service.get_opportunities(company.id)

@router.post("/opportunities/generate")
async def generate_opportunities(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = BacklinkService(db)
    try:
        return await service.generate_opportunities(company)
    except ValueError as e:
        raise HTTPException(status_code=402 if "credits" in str(e) else 400, detail=str(e))

@router.delete("/opportunities/{opportunity_id}")
def delete_opportunity(
    opportunity_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = BacklinkService(db)
    if not service.delete_opportunity(opportunity_id, company.id):
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return {"success": True}

@router.post("/opportunities/{opportunity_id}/outreach")
async def generate_outreach_email(
    opportunity_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = BacklinkService(db)
    try:
        email = await service.generate_outreach_email(opportunity_id, company)
        return {"email": email}
    except ValueError as e:
        raise HTTPException(status_code=402 if "credits" in str(e) else 400, detail=str(e))

class SendOutreachRequest(BaseModel):
    recipient_email: str = Field(..., min_length=5, max_length=320)


class UpdateOutreachRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)


@router.put("/outreach/{outreach_id}")
def update_outreach_email(
    outreach_id: str,
    data: UpdateOutreachRequest,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = BacklinkService(db)
    try:
        email = service.update_outreach_email(
            outreach_id,
            company.id,
            data.subject,
            data.body,
        )
        return email
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/outreach/{outreach_id}/send")
async def send_outreach_email(
    outreach_id: str,
    data: SendOutreachRequest,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = BacklinkService(db)
    try:
        email = await service.send_outreach_email(
            outreach_id,
            company,
            data.recipient_email,
        )
        return {
            "success": True,
            "status": email.status,
            "sent_at": email.sent_at,
            "message": "Outreach email sent successfully.",
            "email": email,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/outreach")
def get_outreach_emails(
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = BacklinkService(db)
    return service.get_outreach_emails(company.id)