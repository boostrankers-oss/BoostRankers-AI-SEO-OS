from __future__ import annotations

from database.database import engine
from sqlalchemy import text
import uuid

AGENCY_EMAIL = "mdarifalam0631@gmail.com"
CLIENT_IDS = [
    "70528fb7-4a81-4644-9276-ce2bc465c3b5",  # Commercial Cleaning Perth WA
    "c6ace8c7-085e-47f8-ac6c-1520ca25021f",  # Shanuzz Salon Andheri
    "b23c8b8b-8efe-4791-8717-300523590262",  # USCA ACADEMY
]

with engine.begin() as conn:
    agency = conn.execute(text("SELECT id, role FROM users WHERE lower(email)=lower(:email) AND is_active=true"), {"email": AGENCY_EMAIL}).mappings().first()
    if not agency:
        raise SystemExit(f"Agency user not found: {AGENCY_EMAIL}")
    if str(agency["role"]).lower() not in {"agency_admin", "manager", "super_admin"}:
        raise SystemExit(f"Agency user has unexpected role: {agency['role']}")

    company_id = conn.execute(text("SELECT company_id FROM users WHERE id=:id"), {"id": agency["id"]}).scalar_one()
    for client_id in CLIENT_IDS:
        exists = conn.execute(text("SELECT 1 FROM clients WHERE id=:client_id"), {"client_id": client_id}).first()
        if not exists:
            raise SystemExit(f"Client not found: {client_id}")
        conn.execute(text("""
            INSERT INTO agency_client_access (id, agency_company_id, client_id, granted_by, status, created_at, updated_at)
            VALUES (:id, :agency_company_id, :client_id, :granted_by, 'active', now(), now())
            ON CONFLICT (agency_company_id, client_id) DO UPDATE SET status='active', granted_by=EXCLUDED.granted_by, updated_at=now()
        """), {"id": str(uuid.uuid4()), "agency_company_id": company_id, "client_id": client_id, "granted_by": agency["id"]})

    rows = conn.execute(text("""
        SELECT a.client_id, c.business_name, c.company_id AS owner_company_id, a.status
        FROM agency_client_access a JOIN clients c ON c.id=a.client_id
        WHERE a.agency_company_id=:agency_company_id ORDER BY c.business_name
    """), {"agency_company_id": company_id}).mappings().all()
    for row in rows:
        print(dict(row))
