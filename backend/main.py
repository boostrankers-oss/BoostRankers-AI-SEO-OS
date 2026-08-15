import os
from pathlib import Path

from dotenv import load_dotenv

# ============================================================
# Load environment variables BEFORE importing modules that
# require DATABASE_URL, ANTHROPIC_API_KEY, JWT secrets, etc.
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)


# ============================================================
# Application imports
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.database import engine


from routers import (
    auth,
    users,
    clients,
    audits,
    reports,
    competitors,
    internal_linking,
    dashboard,
    backlinks,
)

from api.v1.auth import router as auth_router
from routers.ai import router as ai_router
from routers.ai_settings import router as ai_settings_router

# ============================================================
# Validate required environment
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        f"DATABASE_URL is not configured. "
        f"Expected environment file: {ENV_FILE}"
    )


# ============================================================
# Create database tables
# ============================================================




# ============================================================
# FastAPI application
# ============================================================

app = FastAPI(
    title="Boost Rankers AI SEO OS",
    description="Enterprise Multi-Tenant SaaS Backend",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API Routers
# ============================================================

app.include_router(
    auth,
    prefix="/api/auth",
    tags=["Authentication"],
)

app.include_router(
    users,
    prefix="/api/users",
    tags=["Users"],
)

app.include_router(
    clients,
    prefix="/api",
    tags=["Clients"],
)

app.include_router(
    audits,
    prefix="/api/audits",
    tags=["Audits"],
)

app.include_router(
    reports,
    prefix="/api",
    tags=["Reports"],
)

app.include_router(
    competitors,
    prefix="/api",
    tags=["Competitors"],
)

app.include_router(
    dashboard,
    prefix="/api",
    tags=["Dashboard"],
)

app.include_router(
    internal_linking,
    prefix="/api",
    tags=["Internal Linking"],
)

app.include_router(
    backlinks,
    prefix="/api",
    tags=["Backlinks"],
)

# Keep the existing V1 authentication route for compatibility.
app.include_router(
    auth_router,
    prefix="/api/v1",
    tags=["Authentication V1"],
)

app.include_router(
    ai_settings_router,
    prefix="/api",
    tags=["AI Settings"],
)

app.include_router(
    ai_router,
    prefix="/api",
    tags=["AI"],
)

# ============================================================
# Health Check
# ============================================================

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "boost-rankers-backend",
        "database": "postgresql",
        "ai_provider": "anthropic",
    }


# ============================================================
# Local entry point
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )