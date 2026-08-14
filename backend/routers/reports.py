from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from database.database import get_db
from services.report_service import ReportService
from models.user import User
from models.company import Company
from api.deps.current_user import get_current_user, get_current_company

router = APIRouter(prefix="/api/reports", tags=["Reports"])

@router.get("/")
def get_reports(
    limit: int = 50,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = ReportService(db)
    reports = service.get_reports_for_company(company.id, limit)
    return [
        {
            "id": r.id,
            "title": r.title,
            "client_name": r.client.business_name if r.client else "N/A",
            "date": r.generated_at.isoformat(),
            "score": r.score,
            "format": r.format,
            "content": r.content,
            "summary": r.summary,
        }
        for r in reports
    ]

@router.get("/{report_id}")
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = ReportService(db)
    report = service.get_report(report_id, company.id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": report.id,
        "title": report.title,
        "client_name": report.client.business_name if report.client else "N/A",
        "date": report.generated_at.isoformat(),
        "score": report.score,
        "format": report.format,
        "content": report.content,
        "summary": report.summary,
    }

@router.delete("/{report_id}")
def delete_report(
    report_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = ReportService(db)
    if not service.delete_report(report_id, company.id):
        raise HTTPException(status_code=404, detail="Report not found")
    return {"success": True}