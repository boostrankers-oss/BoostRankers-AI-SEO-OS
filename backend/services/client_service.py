from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models.client import Client
from schemas.client import (
    ClientCreate,
    ClientUpdate,
)


# ============================================================
# Helpers
# ============================================================

def _client_query(
    db: Session,
    company_id: str,
):
    """
    Base query scoped to a company.
    """

    return db.query(Client).filter(
        Client.company_id == company_id
    )


def _get_or_404(
    db: Session,
    client_id: str,
    company_id: str,
) -> Client:

    client = (
        _client_query(db, company_id)
        .filter(Client.id == client_id)
        .first()
    )

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found.",
        )

    return client


def _validate_duplicate(
    db: Session,
    company_id: str,
    business_name: str,
    website: str,
    ignore_id: Optional[str] = None,
):
    """
    Prevent duplicate clients inside the same company.
    """

    query = _client_query(
        db,
        company_id,
    ).filter(
        or_(
            func.lower(Client.business_name)
            == business_name.lower(),

            func.lower(Client.website)
            == website.lower(),
        )
    )

    if ignore_id:
        query = query.filter(
            Client.id != ignore_id
        )

    exists = query.first()

    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A client with the same "
                "business name or website "
                "already exists."
            ),
        )


# ============================================================
# CRUD
# ============================================================

def get_clients(
    db: Session,
    company_id: str,
    skip: int = 0,
    limit: int = 20,
):
    """
    Return all active clients.
    """

    return (
        _client_query(db, company_id)
        .filter(Client.is_archived.is_(False))
        .order_by(Client.business_name.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_client(
    db: Session,
    client_id: str,
    company_id: str,
):

    return _get_or_404(
        db,
        client_id,
        company_id,
    )


def create_client(
    db: Session,
    client: ClientCreate,
    company_id: str,
):

    _validate_duplicate(
        db=db,
        company_id=company_id,
        business_name=client.business_name,
        website=str(client.website),
    )

    db_client = Client(
        company_id=company_id,

        business_name=client.business_name,
        legal_name=client.legal_name,

        website=str(client.website),

        industry=client.industry,
        business_type=client.business_type,

        company_size=client.company_size,

        description=client.description,
        logo_url=(
            str(client.logo_url)
            if client.logo_url
            else None
        ),

        contact_name=client.contact_name,
        designation=client.designation,

        email=(
            str(client.email)
            if client.email
            else None
        ),

        secondary_email=(
            str(client.secondary_email)
            if client.secondary_email
            else None
        ),

        phone=client.phone,
        whatsapp=client.whatsapp,

        address_line1=client.address_line1,
        address_line2=client.address_line2,

        city=client.city,
        state=client.state,
        postal_code=client.postal_code,
        country=client.country,

        timezone=client.timezone,
        currency=client.currency,

        primary_keyword=client.primary_keyword,
        target_location=client.target_location,
        target_country=client.target_country,
        target_language=client.target_language,

        cms=client.cms,
        hosting_provider=client.hosting_provider,

        google_business_profile=(
            str(client.google_business_profile)
            if client.google_business_profile
            else None
        ),
    )

    db.add(db_client)

    db.commit()

    db.refresh(db_client)

    return db_client


def update_client(
    db: Session,
    client_id: str,
    client_update: ClientUpdate,
    company_id: str,
):

    client = _get_or_404(
        db,
        client_id,
        company_id,
    )

    update_data = client_update.model_dump(
        exclude_unset=True
    )

    if (
        "business_name" in update_data
        or "website" in update_data
    ):

        _validate_duplicate(
            db=db,
            company_id=company_id,
            business_name=update_data.get(
                "business_name",
                client.business_name,
            ),
            website=str(
                update_data.get(
                    "website",
                    client.website,
                )
            ),
            ignore_id=client.id,
        )

    for field, value in update_data.items():

        if hasattr(value, "__str__") and value is not None:
            if field in (
                "website",
                "logo_url",
                "google_business_profile",
            ):
                value = str(value)

        setattr(
            client,
            field,
            value,
        )

    db.commit()

    db.refresh(client)

    return client
    
    # ============================================================
# Search & Filtering
# ============================================================

def search_clients(
    db: Session,
    company_id: str,
    search: Optional[str] = None,
    industry: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    status_filter: Optional[str] = None,
    priority: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "business_name",
    sort_order: str = "asc",
):
    """
    Advanced client search with filtering and pagination.
    """

    query = (
        _client_query(db, company_id)
        .filter(Client.is_archived.is_(False))
    )

    # -----------------------------------------
    # Search
    # -----------------------------------------

    if search:

        keyword = f"%{search.strip()}%"

        query = query.filter(
            or_(
                Client.business_name.ilike(keyword),
                Client.website.ilike(keyword),
                Client.email.ilike(keyword),
                Client.contact_name.ilike(keyword),
                Client.primary_keyword.ilike(keyword),
            )
        )

    # -----------------------------------------
    # Filters
    # -----------------------------------------

    if industry:
        query = query.filter(Client.industry == industry)

    if country:
        query = query.filter(Client.country == country)

    if city:
        query = query.filter(Client.city == city)

    if status_filter:
        query = query.filter(Client.status == status_filter)

    if priority:
        query = query.filter(Client.priority == priority)

    # -----------------------------------------
    # Total
    # -----------------------------------------

    total = query.count()

    # -----------------------------------------
    # Sorting
    # -----------------------------------------

    sort_columns = {
        "business_name": Client.business_name,
        "website": Client.website,
        "industry": Client.industry,
        "overall_score": Client.overall_score,
        "created_at": Client.created_at,
        "updated_at": Client.updated_at,
        "last_audit_at": Client.last_audit_at,
    }

    column = sort_columns.get(
        sort_by,
        Client.business_name,
    )

    if sort_order.lower() == "desc":
        query = query.order_by(column.desc())
    else:
        query = query.order_by(column.asc())

    # -----------------------------------------
    # Pagination
    # -----------------------------------------

    items = (
        query
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    total_pages = (
        (total + page_size - 1)
        // page_size
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": items,
    }


# ============================================================
# Dashboard Statistics
# ============================================================

def get_client_statistics(
    db: Session,
    company_id: str,
):
    """
    Agency-wide client statistics.
    """

    clients = (
        _client_query(db, company_id)
        .all()
    )

    if not clients:

        return {
            "total_clients": 0,
            "active_clients": 0,
            "inactive_clients": 0,
            "archived_clients": 0,
            "average_score": 0,
            "total_keywords": 0,
            "total_backlinks": 0,
            "total_audits": 0,
            "completed_audits": 0,
            "failed_audits": 0,
        }

    total_clients = len(clients)

    active_clients = sum(
        c.is_active
        for c in clients
    )

    inactive_clients = sum(
        not c.is_active
        for c in clients
    )

    archived_clients = sum(
        c.is_archived
        for c in clients
    )

    average_score = round(
        sum(c.overall_score for c in clients)
        / total_clients,
        2,
    )

    total_keywords = sum(
        c.total_keywords
        for c in clients
    )

    total_backlinks = sum(
        c.total_backlinks
        for c in clients
    )

    total_audits = sum(
        c.total_audits
        for c in clients
    )

    completed_audits = sum(
        c.passed_checks
        for c in clients
    )

    failed_audits = sum(
        c.critical_issues
        for c in clients
    )

    return {
        "total_clients": total_clients,
        "active_clients": active_clients,
        "inactive_clients": inactive_clients,
        "archived_clients": archived_clients,
        "average_score": average_score,
        "total_keywords": total_keywords,
        "total_backlinks": total_backlinks,
        "total_audits": total_audits,
        "completed_audits": completed_audits,
        "failed_audits": failed_audits,
    }


# ============================================================
# Client Dashboard
# ============================================================

def get_client_dashboard(
    db: Session,
    company_id: str,
    client_id: str,
):
    """
    Dashboard data for a single client.
    """

    client = _get_or_404(
        db,
        client_id,
        company_id,
    )

    return {
        "client": client,
        "statistics": get_client_statistics(
            db,
            company_id,
        ),
        "kpis": [
            {
                "title": "Overall SEO Score",
                "value": client.overall_score,
            },
            {
                "title": "Keywords",
                "value": client.total_keywords,
            },
            {
                "title": "Backlinks",
                "value": client.total_backlinks,
            },
            {
                "title": "Audits",
                "value": client.total_audits,
            },
        ],
        "recent_activity": [],
        "upcoming_tasks": [],
        "ai_recommendations": [],
    }
    
    # ============================================================
# Archive / Restore
# ============================================================

def archive_client(
    db: Session,
    client_id: str,
    company_id: str,
):
    """
    Soft delete (archive) a client.
    """

    client = _get_or_404(
        db,
        client_id,
        company_id,
    )

    if client.is_archived:
        return client

    client.is_archived = True
    client.is_active = False

    db.commit()
    db.refresh(client)

    return client


def restore_client(
    db: Session,
    client_id: str,
    company_id: str,
):
    """
    Restore archived client.
    """

    client = _get_or_404(
        db,
        client_id,
        company_id,
    )

    client.is_archived = False
    client.is_active = True

    db.commit()
    db.refresh(client)

    return client


# ============================================================
# Permanent Delete
# ============================================================

def delete_client(
    db: Session,
    client_id: str,
    company_id: str,
):
    """
    Permanently remove a client.
    Normally archive_client() should be used.
    """

    client = _get_or_404(
        db,
        client_id,
        company_id,
    )

    db.delete(client)
    db.commit()

    return {
        "success": True,
        "message": "Client permanently deleted.",
    }


# ============================================================
# Bulk Archive
# ============================================================

def bulk_archive_clients(
    db: Session,
    company_id: str,
    client_ids: list[str],
):
    """
    Archive multiple clients.
    """

    archived = 0

    clients = (
        _client_query(db, company_id)
        .filter(Client.id.in_(client_ids))
        .all()
    )

    for client in clients:

        if not client.is_archived:

            client.is_archived = True
            client.is_active = False

            archived += 1

    db.commit()

    return {
        "success": True,
        "archived": archived,
    }


# ============================================================
# Bulk Restore
# ============================================================

def bulk_restore_clients(
    db: Session,
    company_id: str,
    client_ids: list[str],
):

    restored = 0

    clients = (
        _client_query(db, company_id)
        .filter(Client.id.in_(client_ids))
        .all()
    )

    for client in clients:

        if client.is_archived:

            client.is_archived = False
            client.is_active = True

            restored += 1

    db.commit()

    return {
        "success": True,
        "restored": restored,
    }


# ============================================================
# Export
# ============================================================

def export_clients(
    db: Session,
    company_id: str,
):
    """
    Returns all non-archived clients.
    CSV/Excel generation will be handled
    by the reporting module.
    """

    return (
        _client_query(db, company_id)
        .filter(Client.is_archived.is_(False))
        .order_by(Client.business_name.asc())
        .all()
    )


# ============================================================
# Dashboard KPIs
# ============================================================

def get_dashboard_kpis(
    db: Session,
    company_id: str,
):

    stats = get_client_statistics(
        db,
        company_id,
    )

    return [
        {
            "title": "Clients",
            "value": stats["total_clients"],
            "change": 0,
            "trend": "neutral",
        },
        {
            "title": "Average SEO Score",
            "value": stats["average_score"],
            "change": 0,
            "trend": "neutral",
        },
        {
            "title": "Keywords",
            "value": stats["total_keywords"],
            "change": 0,
            "trend": "neutral",
        },
        {
            "title": "Backlinks",
            "value": stats["total_backlinks"],
            "change": 0,
            "trend": "neutral",
        },
    ]