"""
Boost Rankers AI SEO OS
Production Company Router
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from sqlalchemy.orm import Session

from database.session import get_db

from schemas.company import (
    CompanyCreate,
    CompanyUpdate,
    CompanyResponse,
    CompanyListResponse,
    CompanyDashboard,
    CompanyFilters,
    CompanyBulkAction,
)

from services.company_service import CompanyService

router = APIRouter(
    prefix="/companies",
    tags=["Companies"],
)

    @router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
):

    service = CompanyService(db)

    try:

        return service.create_company(payload)

    except ValueError as exc:

        raise HTTPException(
        status_code=400,
        detail=str(exc),
        )
        
    @router.get(
    "/{company_id}",
    response_model=CompanyResponse,
)
def get_company(
    company_id: str,
    db: Session = Depends(get_db),
):

    service = CompanyService(db)

    company = service.get_by_id(company_id)

    if company is None:

        raise HTTPException(
        status_code=404,
        detail="Company not found.",
        )

    return company
    
    @router.get(
    "",
    response_model=CompanyListResponse,
)
def list_companies(

    search: str | None = Query(default=None),

    industry: str | None = Query(default=None),

    country: str | None = Query(default=None),

    status_filter: str | None = Query(
        default=None,
        alias="status",
    ),

    subscription_plan: str | None = Query(default=None),

    company_size: str | None = Query(default=None),

    is_active: bool | None = Query(default=None),

    page: int = Query(default=1, ge=1),

    page_size: int = Query(default=20, ge=1, le=100),

    sort_by: str = Query(default="created_at"),

    sort_order: str = Query(default="desc"),

    db: Session = Depends(get_db),

):

    filters = CompanyFilters(

        search=search,

        industry=industry,

        country=country,

        status=status_filter,

        subscription_plan=subscription_plan,

        company_size=company_size,

        is_active=is_active,

        page=page,

        page_size=page_size,

        sort_by=sort_by,

        sort_order=sort_order,

    )

    service = CompanyService(db)

    companies, total = service.get_all_companies(filters)

    total_pages = (
        (total + page_size - 1)
        // page_size
    )

    return CompanyListResponse(

        items=companies,

        total=total,

        page=page,

        page_size=page_size,

        total_pages=total_pages,

    )
    
    @router.put(
    "/{company_id}",
    response_model=CompanyResponse,
)
def update_company(

    company_id: str,

    payload: CompanyUpdate,

    db: Session = Depends(get_db),

):

    service = CompanyService(db)

    try:

        return service.update_company(
            company_id,
            payload,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )
        
    @router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_company(
    company_id: str,
    db: Session = Depends(get_db),
):

    service = CompanyService(db)

    deleted = service.delete_company(company_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Company not found.",
        )
        
    @router.patch(
    "/{company_id}/archive",
    response_model=CompanyResponse,
)
def archive_company(
    company_id: str,
    db: Session =Depends(get_db),
):

    service = CompanyService(db)

    try:
        return service.archive_company(company_id)

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )
        
    @router.patch(
    "/{company_id}/restore",
    response_model=CompanyResponse,
)
def restore_company(
    company_id: str,
    db: Session = Depends(get_db),
):

    service = CompanyService(db)

    try:

        return service.restore_company(company_id)

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )
        
    @router.get(
    "/dashboard",
    response_model=CompanyDashboard,
)
def dashboard(
    db: Session = Depends(get_db),
):

    service = CompanyService(db)

    return CompanyDashboard(
        **service.dashboard_statistics()
    )
    
    @router.post("/bulk/archive")
def bulk_archive(
    payload: CompanyBulkAction,
    db: Session = Depends(get_db),
):

    service = CompanyService(db)

    count = service.bulk_archive(
        payload.company_ids
    )

    return {
        "success": True,
        "affected": count,
    }
    
    @router.post("/bulk/restore")
def bulk_restore(
    payload: CompanyBulkAction,
    db: Session = Depends(get_db),
):

    service = CompanyService(db)

    count = service.bulk_restore(
        payload.company_ids
    )

    return {
        "success": True,
        "affected": count,
    }
    
    @router.post("/bulk/delete")
def bulk_delete(
    payload: CompanyBulkAction,
    db: Session = Depends(get_db),
):

    service = CompanyService(db)

    count = service.bulk_delete(
        payload.company_ids
    )

    return {
        "success": True,
        "affected": count,
    }
    
    @router.get("/export")
def export_companies(
    db: Session = Depends(get_db),
):

    service = CompanyService(db)

    return service.export_companies()
    
    @router.get("/health")
def health(
    db: Session = Depends(get_db),
):

    service = CompanyService(db)

    return service.health()