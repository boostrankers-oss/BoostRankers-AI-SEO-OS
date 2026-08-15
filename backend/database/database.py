import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from models.base import Base
from sqlalchemy.orm import sessionmaker


# ============================================================
# Environment
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(
    PROJECT_ROOT / ".env"
)


# ============================================================
# PostgreSQL
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is required."
    )


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


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
    Provide a SQLAlchemy session to FastAPI routes.
    """
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()