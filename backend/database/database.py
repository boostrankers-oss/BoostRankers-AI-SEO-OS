import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from models.base import Base


# ============================================================
# Environment
# ============================================================

# Project structure:
#
# BoostRankers-AI-SEO-OS/
# ├── .env
# └── backend/
#     └── database/
#         └── database.py
#
# database.py -> parents[2] = project root

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE, override=False)


# ============================================================
# PostgreSQL configuration
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not DATABASE_URL:
    raise RuntimeError(
        f"DATABASE_URL environment variable is required. "
        f"Expected environment file: {ENV_FILE}"
    )


# ============================================================
# SQLAlchemy Engine
# ============================================================

# Important:
# This application uses Supabase PostgreSQL.
#
# pool_pre_ping:
#   Detects stale/dead pooled connections before using them.
#
# pool_recycle:
#   Prevents very old connections from remaining in the pool.
#
# pool_timeout:
#   Prevents requests from hanging indefinitely while waiting
#   for a database connection.
#
# connect_args:
#   Gives PostgreSQL a finite connection timeout.

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_timeout=30,
    connect_args={
        "connect_timeout": 15,
    },
)


# ============================================================
# SQLAlchemy Session Factory
# ============================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ============================================================
# FastAPI Database Dependency
# ============================================================

def get_db():
    """
    Provide a SQLAlchemy database session to FastAPI routes.

    The session is always closed after the request, including
    when the route raises an exception.
    """
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# ============================================================
# Database Health Check
# ============================================================

def check_database_connection() -> bool:
    """
    Verify that the configured PostgreSQL database is reachable.

    Returns:
        True when the database responds successfully.

    Raises:
        Exception when the database cannot be reached.
    """
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return True


# ============================================================
# Database Shutdown
# ============================================================

def dispose_database_engine() -> None:
    """
    Dispose all SQLAlchemy pooled connections.

    Useful during application shutdown/reload.
    """
    engine.dispose()


__all__ = [
    "Base",
    "DATABASE_URL",
    "engine",
    "SessionLocal",
    "get_db",
    "check_database_connection",
    "dispose_database_engine",
]