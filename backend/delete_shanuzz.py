from database.database import engine
from sqlalchemy import text

USER_ID = "cf2bbddd-709c-4789-8da7-97d2649b0f76"
COMPANY_ID = "69ed878c-6c4b-43d9-bbc1-b9f13b92754f"
CLIENT_ID = "c6ace8c7-085e-47f8-ac6c-1520ca25021f"
AGENCY_ACCESS_ID = "fe50aa93-018d-49b5-9021-271f60dc7f08"

with engine.begin() as conn:

    # Safety checks
    user = conn.execute(
        text("""
            SELECT id, email, company_id, role
            FROM users
            WHERE id = :id
        """),
        {"id": USER_ID},
    ).mappings().first()

    if not user:
        raise RuntimeError("STOP: Shanuzz user was not found.")

    if str(user["company_id"]) != COMPANY_ID:
        raise RuntimeError(
            f"STOP: User belongs to unexpected company: {user['company_id']}"
        )

    client = conn.execute(
        text("""
            SELECT id, company_id, business_name
            FROM clients
            WHERE id = :id
        """),
        {"id": CLIENT_ID},
    ).mappings().first()

    if not client:
        raise RuntimeError("STOP: Shanuzz client was not found.")

    if str(client["company_id"]) != COMPANY_ID:
        raise RuntimeError(
            f"STOP: Client belongs to unexpected company: {client['company_id']}"
        )

    access = conn.execute(
        text("""
            SELECT id, agency_company_id, client_id
            FROM agency_client_access
            WHERE id = :id
              AND client_id = :client_id
        """),
        {
            "id": AGENCY_ACCESS_ID,
            "client_id": CLIENT_ID,
        },
    ).mappings().first()

    if not access:
        raise RuntimeError(
            "STOP: Expected Shanuzz agency-access relationship was not found."
        )

    # 1. Remove agency access relationship
    result = conn.execute(
        text("""
            DELETE FROM agency_client_access
            WHERE id = :id
              AND client_id = :client_id
        """),
        {
            "id": AGENCY_ACCESS_ID,
            "client_id": CLIENT_ID,
        },
    )
    print("Agency access deleted:", result.rowcount)

    # 2. Delete refresh tokens belonging to Shanuzz owner
    result = conn.execute(
        text("""
            DELETE FROM refresh_tokens
            WHERE user_id = :user_id
        """),
        {"user_id": USER_ID},
    )
    print("Refresh tokens deleted:", result.rowcount)

    # 3. Delete Shanuzz client
    result = conn.execute(
        text("""
            DELETE FROM clients
            WHERE id = :client_id
              AND company_id = :company_id
        """),
        {
            "client_id": CLIENT_ID,
            "company_id": COMPANY_ID,
        },
    )
    print("Shanuzz client deleted:", result.rowcount)

    if result.rowcount != 1:
        raise RuntimeError(
            "STOP: Expected exactly one Shanuzz client to be deleted."
        )

    # 4. Delete Shanuzz user
    result = conn.execute(
        text("""
            DELETE FROM users
            WHERE id = :user_id
              AND company_id = :company_id
            RETURNING id, email
        """),
        {
            "user_id": USER_ID,
            "company_id": COMPANY_ID,
        },
    )
    deleted_user = result.mappings().first()

    if not deleted_user:
        raise RuntimeError(
            "STOP: Shanuzz user was not deleted."
        )

    print("Shanuzz user deleted:", dict(deleted_user))

    # 5. Delete the now-empty Shanuzz workspace
    result = conn.execute(
        text("""
            DELETE FROM companies
            WHERE id = :company_id
            RETURNING id, name
        """),
        {"company_id": COMPANY_ID},
    )
    deleted_company = result.mappings().first()

    if not deleted_company:
        raise RuntimeError(
            "STOP: Shanuzz company/workspace was not deleted."
        )

    print("Shanuzz company deleted:", dict(deleted_company))

print("\n========== SHANUZZ COMPLETE DELETE FINISHED ==========")
