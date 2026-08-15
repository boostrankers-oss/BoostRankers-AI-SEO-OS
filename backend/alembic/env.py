from logging.config import fileConfig
from pathlib import Path
import os

from dotenv import load_dotenv

from sqlalchemy import engine_from_config, pool

from alembic import context


# ============================================================
# Load project environment
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)


# ============================================================
# Database URL
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        f"DATABASE_URL is required for Alembic. "
        f"Expected environment file: {ENV_FILE}"
    )


# ============================================================
# SQLAlchemy metadata
# ============================================================

from models.base import Base


# Import EVERY model module so SQLAlchemy registers every table
# in Base.metadata before Alembic performs autogeneration.

import models.audit
import models.audit_log
import models.backlink
import models.client
import models.company
import models.competitor
import models.internal_linking
import models.permission
import models.refresh_token
import models.report
import models.role
import models.role_permission
import models.user


# ============================================================
# Alembic configuration
# ============================================================

config = context.config

# The password may contain URL-encoded characters such as %40,
# %23, etc. ConfigParser requires % to be escaped here.
config.set_main_option(
    "sqlalchemy.url",
    DATABASE_URL.replace("%", "%%"),
)


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


# ============================================================
# Offline migrations
# ============================================================

def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ============================================================
# Online migrations
# ============================================================

def run_migrations_online() -> None:
    """Run migrations against PostgreSQL."""

    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ============================================================
# Run migrations
# ============================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()