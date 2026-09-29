from database.database import engine
from sqlalchemy import text

USER_ID = "cf2bbddd-709c-4789-8da7-97d2649b0f76"
COMPANY_ID = "69ed878c-6c4b-43f8-ac6c-1520ca25021f"
CLIENT_ID = "c6ace8c7-085e-47f8-ac6c-1520ca25021f"
EMAIL = "noc.aika.shanuzz@gmail.com"

with engine.connect() as conn:
    print("\n========== SHANUZZ OWNER ==========")
    rows = conn.execute(text("""
        SELECT id, email, company_id, role, is_active
        FROM users
        WHERE id = :user_id OR lower(email) = lower(:email)
    """), {
        "user_id": USER_ID,
        "email": EMAIL,
    }).mappings().all()

    for row in rows:
        print(dict(row))

    print("\n========== SHANUZZ COMPANY ==========")
    rows = conn.execute(text("""
        SELECT id, name, website, created_at
        FROM companies
        WHERE id = :company_id
    """), {
        "company_id": COMPANY_ID,
    }).mappings().all()

    for row in rows:
        print(dict(row))

    print("\n========== SHANUZZ CLIENT ==========")
    rows = conn.execute(text("""
        SELECT id, company_id, business_name, website, email, created_at
        FROM clients
        WHERE id = :client_id OR company_id = :company_id
    """), {
        "client_id": CLIENT_ID,
        "company_id": COMPANY_ID,
    }).mappings().all()

    for row in rows:
        print(dict(row))

    print("\n========== AGENCY ACCESS ==========")
    rows = conn.execute(text("""
        SELECT id, agency_company_id, client_id, status, created_at, updated_at
        FROM agency_client_access
        WHERE client_id = :client_id
           OR agency_company_id = :company_id
    """), {
        "client_id": CLIENT_ID,
        "company_id": COMPANY_ID,
    }).mappings().all()

    for row in rows:
        print(dict(row))

    print("\n========== ALL TABLE DEPENDENCIES ==========")

    tables = conn.execute(text("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name IN (
              'user_id',
              'company_id',
              'client_id',
              'agency_company_id'
          )
        ORDER BY table_name, column_name
    """)).mappings().all()

    checked = set()

    for item in tables:
        table = item["table_name"]
        column = item["column_name"]

        if (table, column) in checked:
            continue

        checked.add((table, column))

        try:
            if column == "user_id":
                value = USER_ID
            elif column == "company_id":
                value = COMPANY_ID
            elif column == "client_id":
                value = CLIENT_ID
            elif column == "agency_company_id":
                value = COMPANY_ID
            else:
                continue

            count = conn.execute(
                text(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" = :value'),
                {"value": value},
            ).scalar()

            if count:
                print(f"{table}.{column} = {count}")

        except Exception as exc:
            print(f"{table}.{column} -> CHECK ERROR: {exc}")

    print("\n========== AUDIT COMPLETE ==========")
