import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from app.database import init_db, get_db
from app.clients.router import router as clients_router
from app.audits.router import router as audits_router
from app.config.router import router as config_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="Boost Rankers AI SEO OS", lifespan=lifespan)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, set this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(clients_router, prefix="/api/clients", tags=["clients"])
app.include_router(audits_router, prefix="/api/audits", tags=["audits"])
app.include_router(config_router, prefix="/api/config", tags=["config"])

# Serve Frontend (Built React app)
# The frontend build output should be copied to app/static
app.mount("/assets", StaticFiles(directory="app/static/assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # This catches all non-API routes and serves the React index.html
    file_path = os.path.join("app/static", full_path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse("app/static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)