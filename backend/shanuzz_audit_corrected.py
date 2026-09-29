from database.database import engine
from sqlalchemy import text

USER_ID = "cf2bbddd-709c-4789-8da7-97d2649b0f76"
COMPANY_ID = "69ed878c-6c4b-43d9-bbc1-b9f13b92754f"
CLIENT_ID = "c6ace8c7-085e-47f8-ac6c-1520ca25021f"

with engine.connect() as conn:

    print("\n========== COMPANY ==========")

    rows = conn.execute(
        text("""
            SELECT id, name, website, created_at
            FROM companies
            WHERE id = :id
        """),
        {"id": COMPANY_ID},
    ).mappings().all()

    for row in rows:
        print(dict(row))

    print("\n========== COMPANY / CLIENT / USER DEPENDENCIES ==========")

    columns = conn.execute(
        text("""
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND column_name IN (
                  'company_id',
                  'client_id',
                  'user_id',
                  'agency_company_id'
              )
            ORDER BY table_name, column_name
        """)
    ).mappings().all()

    checked = set()

    for item in columns:
        table = item["table_name"]
        column = item["column_name"]

        if (table, column) in checked:
            continue

        checked.add((table, column))

        if column == "user_id":
            value = USER_ID
        elif column == "client_id":
            value = CLIENT_ID
        else:
            value = COMPANY_ID

        try:
            count = conn.execute(
                text(
                    f'SELECT COUNT(*) FROM "{table}" '
                    f'WHERE "{column}" = :value'
                ),
                {"value": value},
            ).scalar()

            if count:
                print(f"{table}.{column} = {count}")

        except Exception as exc:
            print(f"{table}.{column} -> ERROR: {exc}")

    print("\n========== SPECIFIC RECORDS ==========")

    print("\nUsers:")
    rows = conn.execute(
        text("""
            SELECT id, email, company_id, role, is_active
            FROM users
            WHERE id = :id
        """),
        {"id": USER_ID},
    ).mappings().all()

    for row in rows:
        print(dict(row))

    print("\nClients:")
    rows = conn.execute(
        text("""
            SELECT id, company_id, business_name, website, email
            FROM clients
            WHERE id = :id
        """),
        {"id": CLIENT_ID},
    ).mappings().all()

    for row in rows:
        print(dict(row))

    print("\nAgency access:")
    rows = conn.execute(
        text("""
            SELECT id, agency_company_id, client_id, status
            FROM agency_client_access
            WHERE client_id = :id
        """),
        {"id": CLIENT_ID},
    ).mappings().all()

    for row in rows:
        print(dict(row))

    print("\n========== AUDIT COMPLETE ==========")
