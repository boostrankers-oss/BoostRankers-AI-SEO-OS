from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import aiosqlite
from app.database import get_db

router = APIRouter()

class ConfigUpdate(BaseModel):
    anthropic_api_key: str

class ConfigResponse(BaseModel):
    is_configured: bool

@router.get("/", response_model=ConfigResponse)
async def get_config_status(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT anthropic_api_key FROM config WHERE id = 1") as cursor:
        row = await cursor.fetchone()
        if row and row["anthropic_api_key"]:
            return {"is_configured": True}
        return {"is_configured": False}

@router.post("/")
async def update_config(config: ConfigUpdate, db: aiosqlite.Connection = Depends(get_db)):
    await db.execute("UPDATE config SET anthropic_api_key = ? WHERE id = 1", (config.anthropic_api_key,))
    await db.commit()
    return {"message": "Configuration updated successfully"}