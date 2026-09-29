from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.database import get_db
from schemas.client import (
    ClientCreate, ClientDashboardResponse, ClientListResponse, ClientResponse,
    ClientStatistics, ClientUpdate,
)
from services import client_service
from api.deps.current_user import get_current_company, get_current_user
from models.company import Company
from models.user import User
from models.client import Client
from models.agency_client_access import AgencyClientAccess

router = APIRouter(prefix="/clients", tags=["Clients"])

AGENCY_ROLES = {"super_admin", "agency_admin", "manager"}


class ClientAccessRequest(BaseModel):
    client_id: str


def _role(user: User) -> str:
    return str(getattr(user, "role", "")).strip().lower()


def _is_agency(user: User) -> bool:
    return _role(user) in AGENCY_ROLES


def get_company_id(company: Company = Depends(get_current_company)) -> str:
    return str(company.id)


def _managed_client_ids(db: Session, agency_company_id: str) -> list[str]:
    rows = (db.query(AgencyClientAccess.client_id)
        .filter(AgencyClientAccess.agency_company_id == agency_company_id, AgencyClientAccess.status == "active")
        .all())
    return [str(row[0]) for row in rows]


def _accessible_client_query(db: Session, user: User):
    company_id = str(user.company_id) if user.company_id else ""
    if _is_agency(user):
        ids = _managed_client_ids(db, company_id)
        if ids:
            return db.query(Client).filter(or_(Client.company_id == company_id, Client.id.in_(ids)))
        return db.query(Client).filter(Client.company_id == company_id)
    return db.query(Client).filter(Client.company_id == company_id)


def _resolve_client_for_user(db: Session, user: User, client_id: str) -> Client:
    query = _accessible_client_query(db, user).filter(Client.id == client_id)
    client = query.first()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found or you do not have access to this client.")
    return client


def _require_client_management(user: User) -> None:
    if not _is_agency(user):
        raise HTTPException(status_code=403, detail="Only agency users can manage clients.")


def _client_update_data(client_update: ClientUpdate) -> dict:
    if hasattr(client_update, "model_dump"):
        return client_update.model_dump(exclude_unset=True)
    return client_update.dict(exclude_unset=True)


@router.get("/", response_model=list[ClientResponse])
def get_clients(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (_accessible_client_query(db, current_user)
        .filter(Client.is_archived.is_(False))
        .order_by(Client.business_name.asc())
        .offset(skip).limit(limit).all())


@router.get("/search", response_model=ClientListResponse)
def search_clients(search: str | None = None, industry: str | None = None, country: str | None = None, city: str | None = None, status_filter: str | None = Query(None, alias="status"), priority: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), sort_by: str = "business_name", sort_order: str = "asc", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = _accessible_client_query(db, current_user).filter(Client.is_archived.is_(False))
    if search:
        keyword = f"%{search.strip()}%"
        query = query.filter(or_(Client.business_name.ilike(keyword), Client.website.ilike(keyword), Client.email.ilike(keyword), Client.contact_name.ilike(keyword), Client.primary_keyword.ilike(keyword)))
    if industry: query = query.filter(Client.industry == industry)
    if country: query = query.filter(Client.country == country)
    if city: query = query.filter(Client.city == city)
    if status_filter: query = query.filter(Client.status == status_filter)
    if priority: query = query.filter(Client.priority == priority)
    sort_columns = {"business_name": Client.business_name, "website": Client.website, "industry": Client.industry, "overall_score": Client.overall_score, "created_at": Client.created_at, "updated_at": Client.updated_at, "last_audit_at": Client.last_audit_at}
    column = sort_columns.get(sort_by, Client.business_name)
    query = query.order_by(column.desc() if sort_order.lower() == "desc" else column.asc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "total_pages": ceil(total / page_size) if total else 0, "items": items}


@router.get("/statistics", response_model=ClientStatistics)
def get_statistics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    clients = _accessible_client_query(db, current_user).all()
    if not clients:
        return {"total_clients":0,"active_clients":0,"inactive_clients":0,"archived_clients":0,"average_score":0,"total_keywords":0,"total_backlinks":0,"total_audits":0,"completed_audits":0,"failed_audits":0}
    return {
        "total_clients": len(clients),
        "active_clients": sum(bool(c.is_active) for c in clients),
        "inactive_clients": sum(not bool(c.is_active) for c in clients),
        "archived_clients": sum(bool(c.is_archived) for c in clients),
        "average_score": round(sum(float(c.overall_score or 0) for c in clients) / len(clients), 2),
        "total_keywords": sum(int(c.total_keywords or 0) for c in clients),
        "total_backlinks": sum(int(c.total_backlinks or 0) for c in clients),
        "total_audits": sum(int(c.total_audits or 0) for c in clients),
        "completed_audits": sum(int(c.passed_checks or 0) for c in clients),
        "failed_audits": sum(int(c.critical_issues or 0) for c in clients),
    }


@router.get("/{client_id}/dashboard", response_model=ClientDashboardResponse)
def get_dashboard(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = _resolve_client_for_user(db, current_user, client_id)
    owner_company_id = str(client.company_id)
    return client_service.get_client_dashboard(db=db, company_id=owner_company_id, client_id=str(client.id))


@router.post("/", response_model=ClientResponse, status_code=201)
def create_client(client: ClientCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user), company_id: str = Depends(get_company_id)):
    _require_client_management(current_user)
    return client_service.create_client(db=db, client=client, company_id=company_id)


@router.post("/access", response_model=ClientResponse)
def connect_existing_client(request: ClientAccessRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_client_management(current_user)
    client = db.query(Client).filter(Client.id == request.client_id).first()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    if str(client.company_id) == str(current_user.company_id):
        return client
    existing = db.query(AgencyClientAccess).filter(AgencyClientAccess.agency_company_id == str(current_user.company_id), AgencyClientAccess.client_id == str(client.id)).first()
    if existing:
        if existing.status != "active":
            existing.status = "active"
            existing.granted_by = str(current_user.id)
            db.commit(); db.refresh(client)
        return client
    db.add(AgencyClientAccess(agency_company_id=str(current_user.company_id), client_id=str(client.id), granted_by=str(current_user.id), status="active"))
    db.commit(); db.refresh(client)
    return client


@router.delete("/access/{client_id}")
def revoke_client_access(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_client_management(current_user)
    row = db.query(AgencyClientAccess).filter(AgencyClientAccess.agency_company_id == str(current_user.company_id), AgencyClientAccess.client_id == client_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Agency access record not found.")
    db.delete(row); db.commit()
    return {"success": True, "message": "Agency access revoked. Client ownership was not changed.", "client_id": client_id}


@router.get("/export")
def export_clients(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (_accessible_client_query(db, current_user)
        .filter(Client.is_archived.is_(False))
        .order_by(Client.business_name.asc()).all())



@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    client = _resolve_client_for_user(db, current_user, client_id)
    return client


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(client_id: str, client_update: ClientUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_client_management(current_user)
    client = _resolve_client_for_user(db, current_user, client_id)
    data = _client_update_data(client_update)
    for key, value in data.items():
        if hasattr(client, key): setattr(client, key, value)
    db.commit(); db.refresh(client)
    return client


@router.post("/{client_id}/archive", response_model=ClientResponse)
def archive_client(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_client_management(current_user)
    client = _resolve_client_for_user(db, current_user, client_id)
    client.is_archived = True; client.is_active = False
    db.commit(); db.refresh(client)
    return client


@router.post("/{client_id}/restore", response_model=ClientResponse)
def restore_client(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_client_management(current_user)
    client = _resolve_client_for_user(db, current_user, client_id)
    client.is_archived = False; client.is_active = True
    db.commit(); db.refresh(client)
    return client


@router.delete("/{client_id}")
def delete_client(client_id: str, permanent: bool = Query(False, description="Set true to permanently delete the client."), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_client_management(current_user)
    client = _resolve_client_for_user(db, current_user, client_id)
    if not permanent:
        client.is_archived = True; client.is_active = False
        db.commit()
        return {"success": True, "message": "Client archived.", "client_id": client_id}
    # Never allow an agency to permanently delete an independently owned client.
    if str(client.company_id) != str(current_user.company_id):
        raise HTTPException(status_code=403, detail="Independently owned client accounts cannot be permanently deleted by an agency. Revoke agency access instead.")
    db.delete(client); db.commit()
    return {"success": True, "message": "Client permanently deleted.", "client_id": client_id}


@router.post("/bulk/archive")
def bulk_archive_clients(client_ids: list[str], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_client_management(current_user)
    changed = 0
    for client_id in client_ids:
        client = _resolve_client_for_user(db, current_user, client_id)
        if not client.is_archived:
            client.is_archived = True; client.is_active = False; changed += 1
    db.commit()
    return {"success": True, "archived": changed}


@router.post("/bulk/restore")
def bulk_restore_clients(client_ids: list[str], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_client_management(current_user)
    changed = 0
    for client_id in client_ids:
        client = _resolve_client_for_user(db, current_user, client_id)
        if client.is_archived:
            client.is_archived = False; client.is_active = True; changed += 1
    db.commit()
    return {"success": True, "restored": changed}
