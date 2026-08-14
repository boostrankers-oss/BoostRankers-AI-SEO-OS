from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    Query,
)

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, Request, Query, HTTPException, status
from database.database import get_db

from schemas.client import (
    ClientCreate,
    ClientDashboardResponse,
    ClientListResponse,
    ClientResponse,
    ClientStatistics,
    ClientUpdate,
)

from services import client_service

router = APIRouter(
    prefix="/clients",
    tags=["Clients"],
)

# ============================================================
# Temporary Company Dependency
# Replace with JWT authentication later
# ============================================================

MOCK_COMPANY_ID = "123e4567-e89b-12d3-a456-426614174000"


from fastapi import APIRouter, Depends, Request, Query, HTTPException, status
# ... other imports ...

# Remove the MOCK_COMPANY_ID constant
# MOCK_COMPANY_ID = "123e4567-e89b-12d3-a456-426614174000"

def get_company_id(request: Request) -> str:
    """
    Extract the authenticated user's company ID from the request state.
    """
    company_id = getattr(request.state, "company_id", None)
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Company not found. Please authenticate.",
        )
    return company_id


# ============================================================
# Get Clients
# ============================================================

@router.get(
    "/",
    response_model=list[ClientResponse],
)
def get_clients(
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
):

    return client_service.get_clients(
        db=db,
        company_id=company_id,
        skip=skip,
        limit=limit,
    )


# ============================================================
# Search Clients
# ============================================================

@router.get(
    "/search",
    response_model=ClientListResponse,
)
def search_clients(
    search: str | None = None,
    industry: str | None = None,
    country: str | None = None,
    city: str | None = None,
    status_filter: str | None = Query(
        default=None,
        alias="status",
    ),
    priority: str | None = None,
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    sort_by: str = "business_name",
    sort_order: str = "asc",
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
):

    return client_service.search_clients(
        db=db,
        company_id=company_id,
        search=search,
        industry=industry,
        country=country,
        city=city,
        status_filter=status_filter,
        priority=priority,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


# ============================================================
# Client Statistics
# ============================================================

@router.get(
    "/statistics",
    response_model=ClientStatistics,
)
def get_statistics(
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
):

    return client_service.get_client_statistics(
        db=db,
        company_id=company_id,
    )


# ============================================================
# Client Dashboard
# ============================================================

@router.get(
    "/{client_id}/dashboard",
    response_model=ClientDashboardResponse,
)
def get_dashboard(
    client_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
):

    return client_service.get_client_dashboard(
        db=db,
        company_id=company_id,
        client_id=client_id,
    )
    
    # ============================================================
# Create Client
# ============================================================

@router.post(
    "/",
    response_model=ClientResponse,
    status_code=201,
)
def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
):
    """
    Create a new client.
    """

    return client_service.create_client(
        db=db,
        client=client,
        company_id=company_id,
    )


# ============================================================
# Get Client
# ============================================================

@router.get(
    "/{client_id}",
    response_model=ClientResponse,
)
def get_client(
    client_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
):
    """
    Get a single client.
    """

    return client_service.get_client(
        db=db,
        client_id=client_id,
        company_id=company_id,
    )


# ============================================================
# Update Client
# ============================================================

@router.put(
    "/{client_id}",
    response_model=ClientResponse,
)
def update_client(
    client_id: str,
    client_update: ClientUpdate,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
):
    """
    Update an existing client.
    """

    return client_service.update_client(
        db=db,
        client_id=client_id,
        client_update=client_update,
        company_id=company_id,
    )


# ============================================================
# Archive Client
# ============================================================

@router.post(
    "/{client_id}/archive",
    response_model=ClientResponse,
)
def archive_client(
    client_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
):
    """
    Archive a client (soft delete).
    """

    return client_service.archive_client(
        db=db,
        client_id=client_id,
        company_id=company_id,
    )


# ============================================================
# Restore Client
# ============================================================

@router.post(
    "/{client_id}/restore",
    response_model=ClientResponse,
)
def restore_client(
    client_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
):
    """
    Restore an archived client.
    """

    return client_service.restore_client(
        db=db,
        client_id=client_id,
        company_id=company_id,
    )
    
    # ============================================================
# Delete Client
# ============================================================

@router.delete(
    "/{client_id}",
)
def delete_client(
    client_id: str,
    permanent: bool = Query(
        default=False,
        description="Set true to permanently delete the client.",
    ),
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
):
    """
    Delete a client.

    Default:
        Soft delete (archive)

    Permanent:
        DELETE /clients/{id}?permanent=true
    """

    if permanent:
        return client_service.delete_client(
            db=db,
            client_id=client_id,
            company_id=company_id,
        )

    return client_service.archive_client(
        db=db,
        client_id=client_id,
        company_id=company_id,
    )


# ============================================================
# Bulk Archive
# ============================================================

@router.post(
    "/bulk/archive",
)
def bulk_archive_clients(
    client_ids: list[str],
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
):
    """
    Archive multiple clients.
    """

    return client_service.bulk_archive_clients(
        db=db,
        company_id=company_id,
        client_ids=client_ids,
    )


# ============================================================
# Bulk Restore
# ============================================================

@router.post(
    "/bulk/restore",
)
def bulk_restore_clients(
    client_ids: list[str],
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
):
    """
    Restore multiple archived clients.
    """

    return client_service.bulk_restore_clients(
        db=db,
        company_id=company_id,
        client_ids=client_ids,
    )


# ============================================================
# Export Clients
# ============================================================

@router.get(
    "/export",
)
def export_clients(
    db: Session = Depends(get_db),
    company_id: str = Depends(get_company_id),
):
    """
    Export clients.

    Currently returns client records.
    Future versions will support:

    - CSV
    - Excel
    - PDF
    """

    return client_service.export_clients(
        db=db,
        company_id=company_id,
    )


# ============================================================
# Future Modules
# ============================================================

# Future router expansion:
#
# /clients/{id}/notes
# /clients/{id}/tasks
# /clients/{id}/documents
# /clients/{id}/reports
# /clients/{id}/audit-history
# /clients/{id}/keywords
# /clients/{id}/competitors
# /clients/{id}/backlinks
# /clients/{id}/schema
# /clients/{id}/technical
# /clients/{id}/content
# /clients/{id}/analytics
# /clients/{id}/search-console
# /clients/{id}/local-seo
# /clients/{id}/ai