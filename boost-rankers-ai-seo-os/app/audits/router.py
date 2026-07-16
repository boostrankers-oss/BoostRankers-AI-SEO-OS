from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import aiosqlite
import json
import os
from app.database import get_db
from app.audits.engine import run_audit_engine

router = APIRouter()

class AuditBase(BaseModel):
    client_id: Optional[int] = None
    url: str
    primary_keyword: str
    location: Optional[str] = None
    competitors: Optional[str] = None

class Audit(AuditBase):
    id: int
    status: str
    scores: Optional[str]
    findings: Optional[str]
    content_plan: Optional[str]
    created_at: str

@router.get("/", response_model=List[Audit])
async def get_audits(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM audits ORDER BY created_at DESC") as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

@router.post("/", response_model=Audit)
async def create_audit(audit: AuditBase, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        """INSERT INTO audits (client_id, url, primary_keyword, location, competitors, status)
           VALUES (?, ?, ?, ?, ?, 'running')""",
        (audit.client_id, audit.url, audit.primary_keyword, audit.location, audit.competitors)
    )
    await db.commit()
    audit_id = cursor.lastrowid

    # Fetch API key
    async with db.execute("SELECT anthropic_api_key FROM config WHERE id = 1") as cursor:
        config_row = await cursor.fetchone()
        api_key = config_row["anthropic_api_key"] if config_row else None

    # Run the audit engine (synchronously for simplicity in this MVP, 
    # in a real app this would be a background task like Celery)
    try:
        results = await run_audit_engine(api_key, audit.url, audit.primary_keyword, audit.location, audit.competitors)
        
        await db.execute(
            """UPDATE audits SET status = 'completed', scores = ?, findings = ?, content_plan = ? WHERE id = ?""",
            (json.dumps(results.get("scores", {})), json.dumps(results.get("findings", [])), json.dumps(results.get("content_plan", [])), audit_id)
        )
        await db.commit()
    except Exception as e:
        await db.execute("UPDATE audits SET status = 'failed' WHERE id = ?", (audit_id,))
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))

    async with db.execute("SELECT * FROM audits WHERE id = ?", (audit_id,)) as cur:
        row = await cur.fetchone()
        return dict(row)