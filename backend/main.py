import os
from routers import (
    auth, users, clients, audits, reports, competitors, 
    internal_linking, dashboard
)
from api.v1.auth import router as auth_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from database.database import Base, engine
from routers import backlinks

# Create tables
Base.metadata.create_all(bind=engine)

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Boost Rankers AI SEO OS",
    description="Enterprise Multi-Tenant SaaS Backend",
    version="1.0.0",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# Register Routers
# ============================================

# Include routers
app.include_router(auth, prefix="/api/auth", tags=["Authentication"])
app.include_router(users, prefix="/api/users", tags=["Users"])
app.include_router(clients, prefix="/api", tags=["Clients"])
app.include_router(audits, prefix="/api", tags=["Audits"])
app.include_router(reports, prefix="/api", tags=["Reports"])
app.include_router(competitors, prefix="/api", tags=["Competitors"])   # ✅ prefix /api + router prefix /competitors = /api/competitors
app.include_router(dashboard, prefix="/api", tags=["Dashboard"])
app.include_router(internal_linking, prefix="/api", tags=["Internal Linking"])
app.include_router(backlinks, prefix="/api", tags=["Backlinks"])

# Auth v1 (from api/v1/auth.py)
app.include_router(auth_router, prefix="/api/v1", tags=["Authentication V1"])

# Health Check Route
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "boost-rankers-backend",
        "database": "postgresql",
        "ai_provider": "anthropic"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)