import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


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
        "DATABASE_URL environment variable is required. "
        f"Expected environment file: {ENV_FILE}"
    )


# ============================================================
# Normalize PostgreSQL URL
# ============================================================

# SQLAlchemy expects:
#
# postgresql+psycopg2://...
#
# Some deployment environments may provide:
#
# postgresql://...
#
# Normalize it so the application consistently uses psycopg2.

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg2://",
        1,
    )


# ============================================================
# SQLAlchemy Engine
# ============================================================

# IMPORTANT FOR SUPABASE / RENDER
#
# pool_pre_ping=True
#   Checks whether a pooled connection is still alive before
#   handing it to the application.
#
# pool_recycle=900
#   Recycles connections after 15 minutes instead of keeping
#   potentially stale connections for a long period.
#
# pool_size=5
#   Keeps a small predictable pool suitable for a Render
#   service and Supabase connection pooler.
#
# max_overflow=5
#   Allows temporary bursts without creating an unlimited
#   number of PostgreSQL connections.
#
# pool_timeout=30
#   Prevents requests from waiting indefinitely for a connection.
#
# connect_args:
#   PostgreSQL connection-level timeout and TCP keepalive
#   configuration.
#
# sslmode=require
#   Ensures the Supabase PostgreSQL connection uses SSL.
#
# keepalives:
#   Helps detect broken TCP connections instead of allowing
#   dead connections to remain apparently usable.

# Keep the pool deliberately small for Supabase session-mode pooling.
# Values can be overridden through environment variables without changing
# application code. This prevents Render/Uvicorn workers from exhausting
# the Supabase session connection limit.
try:
    DATABASE_POOL_SIZE = max(
        1,
        int(os.getenv("DATABASE_POOL_SIZE", "2")),
    )
except (TypeError, ValueError):
    DATABASE_POOL_SIZE = 2

try:
    DATABASE_MAX_OVERFLOW = max(
        0,
        int(os.getenv("DATABASE_MAX_OVERFLOW", "0")),
    )
except (TypeError, ValueError):
    DATABASE_MAX_OVERFLOW = 0

try:
    DATABASE_POOL_TIMEOUT = max(
        5,
        int(os.getenv("DATABASE_POOL_TIMEOUT", "30")),
    )
except (TypeError, ValueError):
    DATABASE_POOL_TIMEOUT = 30

try:
    DATABASE_POOL_RECYCLE = max(
        60,
        int(os.getenv("DATABASE_POOL_RECYCLE", "900")),
    )
except (TypeError, ValueError):
    DATABASE_POOL_RECYCLE = 900

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=DATABASE_POOL_RECYCLE,
    pool_size=DATABASE_POOL_SIZE,
    max_overflow=DATABASE_MAX_OVERFLOW,
    pool_timeout=DATABASE_POOL_TIMEOUT,
    pool_use_lifo=True,
    connect_args={
        "connect_timeout": 15,
        "sslmode": "require",

        # TCP keepalive
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    },
)


# ============================================================
# SQLAlchemy Session Factory
# ============================================================

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
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

    except Exception:
        # Make absolutely sure a failed request does not leave
        # an open transaction attached to the session.
        db.rollback()
        raise

    finally:
        db.close()


# ============================================================
# Database Health Check
# ============================================================

def check_database_connection() -> bool:
    """
    Verify that PostgreSQL is reachable and that a fresh
    SQLAlchemy connection can successfully execute a query.

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

    This should be called during application shutdown/reload
    so Render/Uvicorn does not retain old database connections.
    """

    engine.dispose()


# ============================================================
# Public exports
# ============================================================

__all__ = [
    "DATABASE_URL",
    "DATABASE_POOL_SIZE",
    "DATABASE_MAX_OVERFLOW",
    "DATABASE_POOL_TIMEOUT",
    "DATABASE_POOL_RECYCLE",
    "engine",
    "SessionLocal",
    "get_db",
    "check_database_connection",
    "dispose_database_engine",
]