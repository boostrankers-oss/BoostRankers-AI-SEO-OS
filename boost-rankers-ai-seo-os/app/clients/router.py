from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import aiosqlite
from app.database import get_db

router = APIRouter()

class ClientBase(BaseModel):
    business_name: str
    website: str
    industry: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    primary_keywords: Optional[str] = None
    secondary_keywords: Optional[str] = None
    competitors: Optional[str] = None
    monthly_goals: Optional[str] = None

class Client(ClientBase):
    id: int
    created_at: str

@router.get("/", response_model=List[Client])
async def get_clients(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM clients ORDER BY created_at DESC") as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

@router.post("/", response_model=Client)
async def create_client(client: ClientBase, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        """INSERT INTO clients (business_name, website, industry, country, city, primary_keywords, secondary_keywords, competitors, monthly_goals)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (client.business_name, client.website, client.industry, client.country, client.city, client.primary_keywords, client.secondary_keywords, client.competitors, client.monthly_goals)
    )
    await db.commit()
    new_id = cursor.lastrowid
    async with db.execute("SELECT * FROM clients WHERE id = ?", (new_id,)) as cur:
        row = await cur.fetchone()
        return dict(row)

@router.get("/{client_id}", response_model=Client)
async def get_client(client_id: int, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)) as cursor:
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Client not found")
        return dict(row)

@router.delete("/{client_id}")
async def delete_client(client_id: int, db: aiosqlite.Connection = Depends(get_db)):
    await db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    await db.execute("DELETE FROM audits WHERE client_id = ?", (client_id,))
    await db.commit()
    return {"message": "Client deleted"}