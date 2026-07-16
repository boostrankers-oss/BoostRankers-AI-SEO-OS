import aiosqlite
import os

DB_NAME = "seo_os.db"

async def get_db():
    db = await aiosqlite.connect(DB_NAME)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Clients Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT NOT NULL,
                website TEXT NOT NULL,
                industry TEXT,
                country TEXT,
                city TEXT,
                primary_keywords TEXT,
                secondary_keywords TEXT,
                competitors TEXT,
                monthly_goals TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Audits Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                url TEXT NOT NULL,
                primary_keyword TEXT NOT NULL,
                location TEXT,
                competitors TEXT,
                status TEXT DEFAULT 'pending',
                scores TEXT,
                findings TEXT,
                content_plan TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients (id)
            )
        """)

        # Config Table (for API keys)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                anthropic_api_key TEXT
            )
        """)
        
        # Insert default config row if not exists
        await db.execute("""
            INSERT OR IGNORE INTO config (id, anthropic_api_key) VALUES (1, NULL)
        """)
        
        await db.commit()