from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from pydantic import BaseModel, EmailStr, Field, HttpUrl
from sqlalchemy import text
from sqlalchemy.orm import Session

from sqlalchemy.orm import Session

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

from api.deps.current_user import get_current_company, get_current_user
from models.company import Company
from models.client import Client
from models.user import User
from core.security import hash_password, verify_password, validate_password_strength
from services.auth_service import AuthService

router = APIRouter(
    prefix="/clients",
    tags=["Clients"],
)

# ============================================================
# Authenticated Company Dependency
# ============================================================

def get_company_id(
    company: Company = Depends(get_current_company),
) -> str:
    """
    Resolve the company from the authenticated JWT user.
    """
    return str(company.id)


# ============================================================
# Agency Invitation & Access
# ============================================================

AGENCY_ROLES = {"super_admin", "agency_admin", "manager"}
INVITATION_TTL_HOURS = 72


class ClientInvitationCreate(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=255)
    website: HttpUrl
    email: EmailStr
    industry: str | None = Field(default=None, max_length=150)
    contact_name: str | None = Field(default=None, max_length=255)


class ExistingClientInvitationCreate(BaseModel):
    email: EmailStr


class ClientInvitationAccept(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=12, max_length=72)
    confirm_password: str = Field(..., min_length=12, max_length=72)


def _require_agency(current_user: User) -> User:
    if str(getattr(current_user, "role", "")).lower() not in AGENCY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only agency staff can manage client invitations and agency access.",
        )
    if not getattr(current_user, "company_id", None):
        raise HTTPException(status_code=403, detail="Agency account is not attached to a company.")
    return current_user


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "client"


def _frontend_url() -> str:
    import os
    return os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")[0].strip().rstrip("/")


def _create_invitation(
    db: Session,
    *,
    agency_company_id: str,
    client_id: str,
    email: str,
    invited_by: str,
) -> dict:
    # Invalidate older pending invitations for the same agency/client/email.
    db.execute(
        text("""
            UPDATE client_invitations
            SET status = 'superseded', updated_at = now()
            WHERE agency_company_id = :agency_company_id
              AND client_id = :client_id
              AND lower(email) = lower(:email)
              AND status = 'pending'
        """),
        {
            "agency_company_id": agency_company_id,
            "client_id": client_id,
            "email": email,
        },
    )

    raw_token = secrets.token_urlsafe(48)
    invitation_id = str(uuid4())
    expires_at = datetime.now(UTC) + timedelta(hours=INVITATION_TTL_HOURS)

    db.execute(
        text("""
            INSERT INTO client_invitations
                (id, agency_company_id, client_id, email, token_hash, status,
                 expires_at, invited_by, created_at, updated_at)
            VALUES
                (:id, :agency_company_id, :client_id, :email, :token_hash, 'pending',
                 :expires_at, :invited_by, now(), now())
        """),
        {
            "id": invitation_id,
            "agency_company_id": agency_company_id,
            "client_id": client_id,
            "email": email.lower().strip(),
            "token_hash": _token_hash(raw_token),
            "expires_at": expires_at,
            "invited_by": invited_by,
        },
    )

    return {
        "id": invitation_id,
        "email": email.lower().strip(),
        "client_id": client_id,
        "status": "pending",
        "expires_at": expires_at.isoformat(),
        "invitation_url": f"{_frontend_url()}/invite/{quote(raw_token)}",
    }


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
def invite_new_client(
    payload: ClientInvitationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a private client workspace and issue a secure invitation."""
    _require_agency(current_user)
    email = str(payload.email).lower().strip()

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=409,
            detail="This email already has a Boost Rankers account. Use Connect Existing Client instead.",
        )

    company_name = f"{payload.business_name.strip()} - Workspace"
    if db.query(Company).filter(Company.name == company_name).first():
        company_name = f"{payload.business_name.strip()} - Workspace {str(uuid4())[:8]}"

    slug = f"{_slugify(payload.business_name)}-{str(uuid4())[:8]}"
    company = Company(
        name=company_name,
        slug=slug,
        website=str(payload.website),
        subscription_plan="free",
        subscription_status="trial",
        is_active=True,
    )
    db.add(company)
    db.flush()

    client = Client(
        company_id=str(company.id),
        business_name=payload.business_name.strip(),
        website=str(payload.website).strip(),
        industry=payload.industry.strip() if payload.industry else None,
        contact_name=payload.contact_name.strip() if payload.contact_name else None,
        email=email,
    )
    db.add(client)
    db.flush()

    access_id = str(uuid4())
    db.execute(
        text("""
            INSERT INTO agency_client_access
                (id, agency_company_id, client_id, granted_by, status, created_at, updated_at)
            VALUES
                (:id, :agency_company_id, :client_id, :granted_by, 'active', now(), now())
        """),
        {
            "id": access_id,
            "agency_company_id": str(current_user.company_id),
            "client_id": str(client.id),
            "granted_by": str(current_user.id),
        },
    )

    invitation = _create_invitation(
        db,
        agency_company_id=str(current_user.company_id),
        client_id=str(client.id),
        email=email,
        invited_by=str(current_user.id),
    )
    db.commit()
    db.refresh(client)

    return {
        "success": True,
        "message": "Client workspace created and invitation generated.",
        "client": client,
        "invitation": invitation,
        "delivery": "copy_link",
    }


@router.post("/invitations/existing", status_code=status.HTTP_201_CREATED)
def invite_existing_client(
    payload: ExistingClientInvitationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Invite an already registered client without changing ownership."""
    _require_agency(current_user)
    email = str(payload.email).lower().strip()
    target_user = db.query(User).filter(User.email == email).first()

    if target_user is None:
        raise HTTPException(status_code=404, detail="No Boost Rankers client account exists for this email.")
    if str(target_user.role).lower() != "client":
        raise HTTPException(status_code=400, detail="The selected account is not a client account.")
    if not target_user.company_id:
        raise HTTPException(status_code=400, detail="The client account is not attached to a workspace.")

    client = db.query(Client).filter(
        Client.company_id == str(target_user.company_id),
        Client.email.ilike(email),
    ).order_by(Client.created_at.asc()).first()
    if client is None:
        raise HTTPException(status_code=404, detail="No client record is associated with this client account.")

    if str(target_user.company_id) == str(current_user.company_id):
        raise HTTPException(status_code=400, detail="This client is already owned by your agency workspace.")

    existing_access = db.execute(
        text("""SELECT status FROM agency_client_access
               WHERE agency_company_id=:agency AND client_id=:client"""),
        {"agency": str(current_user.company_id), "client": str(client.id)},
    ).scalar()

    if existing_access == "active":
        raise HTTPException(status_code=409, detail="This client is already connected to your agency.")

    invitation = _create_invitation(
        db,
        agency_company_id=str(current_user.company_id),
        client_id=str(client.id),
        email=email,
        invited_by=str(current_user.id),
    )
    db.commit()

    return {
        "success": True,
        "message": "Invitation created. Client must accept it before agency access is active.",
        "client": client,
        "invitation": invitation,
        "delivery": "copy_link",
    }


@router.get("/invitations/{token}")
def get_invitation(token: str, db: Session = Depends(get_db)):
    """Return safe invitation details without exposing the token hash."""
    row = db.execute(
        text("""
            SELECT i.id, i.email, i.status, i.expires_at, c.id AS client_id,
                   c.business_name, c.website, co.name AS workspace_name
            FROM client_invitations i
            JOIN clients c ON c.id = i.client_id
            JOIN companies co ON co.id = c.company_id
            WHERE i.token_hash = :token_hash
            LIMIT 1
        """),
        {"token_hash": _token_hash(token)},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Invitation not found.")
    if row["status"] != "pending":
        raise HTTPException(status_code=410, detail=f"Invitation is {row['status']}.")
    if row["expires_at"] <= datetime.now(UTC):
        db.execute(text("UPDATE client_invitations SET status='expired', updated_at=now() WHERE id=:id"), {"id": row["id"]})
        db.commit()
        raise HTTPException(status_code=410, detail="Invitation has expired.")

    return {
        "valid": True,
        "invitation_id": row["id"],
        "email": row["email"],
        "client_id": row["client_id"],
        "business_name": row["business_name"],
        "website": row["website"],
        "workspace_name": row["workspace_name"],
        "expires_at": row["expires_at"].isoformat(),
    }


@router.post("/invitations/{token}/accept")
def accept_invitation(
    token: str,
    payload: ClientInvitationAccept,
    db: Session = Depends(get_db),
):
    """Accept an invitation, create the client login if needed, and activate agency access."""
    row = db.execute(
        text("""
            SELECT id, agency_company_id, client_id, email, status, expires_at
            FROM client_invitations
            WHERE token_hash = :token_hash
            LIMIT 1
        """),
        {"token_hash": _token_hash(token)},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Invitation not found.")
    if row["status"] != "pending":
        raise HTTPException(status_code=410, detail=f"Invitation is {row['status']}.")
    if row["expires_at"] <= datetime.now(UTC):
        db.execute(text("UPDATE client_invitations SET status='expired', updated_at=now() WHERE id=:id"), {"id": row["id"]})
        db.commit()
        raise HTTPException(status_code=410, detail="Invitation has expired.")

    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    validation = validate_password_strength(payload.password)
    if not validation.valid:
        raise HTTPException(status_code=400, detail=validation.message)

    email = str(row["email"]).lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if user is not None:
        if str(user.role).lower() != "client":
            raise HTTPException(status_code=400, detail="This email belongs to a non-client account.")
        if str(user.company_id) != str(db.query(Client).filter(Client.id == str(row["client_id"])).with_entities(Client.company_id).scalar()):
            raise HTTPException(status_code=409, detail="This invitation does not match the existing client's workspace.")
        if not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Existing account password is incorrect.")
    else:
        client = db.query(Client).filter(Client.id == str(row["client_id"])).first()
        if client is None:
            raise HTTPException(status_code=404, detail="Client record no longer exists.")

        user = User(
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            email=email,
            hashed_password=hash_password(payload.password),
            role="client",
            company_id=str(client.company_id),
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.flush()

    access = db.execute(
        text("""
            SELECT id, status FROM agency_client_access
            WHERE agency_company_id=:agency AND client_id=:client
            LIMIT 1
        """),
        {"agency": row["agency_company_id"], "client": row["client_id"]},
    ).mappings().first()

    if access:
        db.execute(
            text("""UPDATE agency_client_access
                   SET status='active', granted_by=COALESCE(granted_by, :user_id), updated_at=now()
                   WHERE id=:id"""),
            {"id": access["id"], "user_id": row["invited_by"] if "invited_by" in row else None},
        )
    else:
        db.execute(
            text("""INSERT INTO agency_client_access
                   (id, agency_company_id, client_id, granted_by, status, created_at, updated_at)
                   VALUES (:id,:agency,:client,:user_id,'active',now(),now())"""),
            {"id": str(uuid4()), "agency": row["agency_company_id"], "client": row["client_id"], "user_id": None},
        )

    db.execute(
        text("""UPDATE client_invitations
               SET status='accepted', accepted_by=:user_id, accepted_at=now(), updated_at=now()
               WHERE id=:id"""),
        {"id": row["id"], "user_id": str(user.id)},
    )

    tokens = AuthService(db)._issue_tokens(user)
    db.commit()

    return {
        "success": True,
        "message": "Invitation accepted. Your client workspace is now connected to the agency.",
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "role": user.role,
            "company_id": user.company_id,
            "is_verified": user.is_verified,
        },
        "tokens": tokens,
    }


@router.get("/agency-access")
def list_agency_access(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List clients accessible to the authenticated agency."""
    _require_agency(current_user)
    rows = db.execute(
        text("""
            SELECT a.client_id, a.status, a.created_at, a.updated_at,
                   c.business_name, c.website, c.email, c.company_id AS owner_company_id
            FROM agency_client_access a
            JOIN clients c ON c.id = a.client_id
            WHERE a.agency_company_id = :agency
            ORDER BY c.business_name ASC
        """),
        {"agency": str(current_user.company_id)},
    ).mappings().all()
    return [dict(row) for row in rows]


@router.post("/{client_id}/agency-access/disable")
def disable_agency_access(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_agency(current_user)
    result = db.execute(
        text("""UPDATE agency_client_access SET status='disabled', updated_at=now()
               WHERE agency_company_id=:agency AND client_id=:client AND status='active'"""),
        {"agency": str(current_user.company_id), "client": client_id},
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=404, detail="Active agency access was not found.")
    db.commit()
    return {"success": True, "status": "disabled"}


@router.post("/{client_id}/agency-access/enable")
def enable_agency_access(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_agency(current_user)
    result = db.execute(
        text("""UPDATE agency_client_access SET status='active', updated_at=now()
               WHERE agency_company_id=:agency AND client_id=:client AND status='disabled'"""),
        {"agency": str(current_user.company_id), "client": client_id},
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=404, detail="Disabled agency access was not found.")
    db.commit()
    return {"success": True, "status": "active"}


@router.delete("/{client_id}/agency-access")
def revoke_agency_access(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_agency(current_user)
    result = db.execute(
        text("""UPDATE agency_client_access SET status='revoked', updated_at=now()
               WHERE agency_company_id=:agency AND client_id=:client AND status <> 'revoked'"""),
        {"agency": str(current_user.company_id), "client": client_id},
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=404, detail="Agency access was not found.")
    db.commit()
    return {"success": True, "status": "revoked"}


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
    current_user: User = Depends(get_current_user),
):

    # Keep the legacy service path for ordinary client workspaces.
    if str(getattr(current_user, "role", "")).lower() not in AGENCY_ROLES:
        return client_service.get_clients(
            db=db,
            company_id=company_id,
            skip=skip,
            limit=limit,
        )

    owned = client_service.get_clients(db=db, company_id=company_id, skip=skip, limit=limit)
    external_rows = db.execute(
        text("""
            SELECT c.id FROM clients c
            JOIN agency_client_access a ON a.client_id = c.id
            WHERE a.agency_company_id=:agency AND a.status='active'
              AND c.company_id <> :agency
            ORDER BY c.created_at DESC
            LIMIT :limit OFFSET :skip
        """),
        {"agency": company_id, "limit": limit, "skip": skip},
    ).scalars().all()
    external = db.query(Client).filter(Client.id.in_(external_rows)).all() if external_rows else []
    by_id = {str(c.id): c for c in external}
    external = [by_id[str(cid)] for cid in external_rows if str(cid) in by_id]
    return (owned + external)[:limit]


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
    current_user: User = Depends(get_current_user),
):
    """Create a new agency-owned client. Single-client owners cannot create additional clients."""
    if str(getattr(current_user, "role", "")).lower() == "client":
        raise HTTPException(status_code=403, detail="Single client accounts cannot create additional clients.")
    if str(getattr(current_user, "role", "")).lower() not in AGENCY_ROLES:
        raise HTTPException(status_code=403, detail="Only agency staff can create clients.")

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