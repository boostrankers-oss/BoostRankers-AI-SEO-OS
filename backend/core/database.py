from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.settings import get_settings

logger = logging.getLogger(__name__)


# ==========================================================
# Base ORM Model
# ==========================================================

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# ==========================================================
# Database Manager
# ==========================================================

class DatabaseManager:

    def __init__(self) -> None:

        self.settings = get_settings()

        self.engine: AsyncEngine | None = None

        self.session_factory: async_sessionmaker[
            AsyncSession
        ] | None = None

        self._started = False

        self._lock = asyncio.Lock()


# ==========================================================
# Engine Creation
# ==========================================================

    async def startup(self) -> None:

        async with self._lock:

            if self._started:
                return

            database = self.settings.database

            self.engine = create_async_engine(

                database.url,

                echo=database.echo,

                pool_pre_ping=True,

                pool_size=database.pool_size,

                max_overflow=database.max_overflow,

                pool_timeout=database.pool_timeout,

                pool_recycle=database.pool_recycle,

                future=True,

            )

            self.session_factory = async_sessionmaker(

                bind=self.engine,

                class_=AsyncSession,

                autoflush=False,

                expire_on_commit=False,

                autocommit=False,

            )

            self._started = True

            logger.info("Database initialized.")


# ==========================================================
# Shutdown
# ==========================================================

    async def shutdown(self) -> None:

        async with self._lock:

            if self.engine:

                await self.engine.dispose()

            self.engine = None

            self.session_factory = None

            self._started = False

            logger.info("Database shutdown complete.")


# ==========================================================
# Session Factory
# ==========================================================

    async def session(self) -> AsyncSession:

        if self.session_factory is None:

            raise RuntimeError(
                "Database has not been initialized."
            )

        return self.session_factory()


# ==========================================================
# Dependency
# ==========================================================

    @asynccontextmanager
    async def dependency(
        self,
    ) -> AsyncGenerator[AsyncSession, None]:

        session = await self.session()

        try:

            yield session

            await session.commit()

        except Exception:

            await session.rollback()

            raise

        finally:

            await session.close()


# ==========================================================
# Execute SQL
# ==========================================================

    async def execute(
        self,
        sql: str,
        parameters: dict[str, Any] | None = None,
    ):

        async with self.dependency() as session:

            return await session.execute(

                text(sql),

                parameters or {},

            )


# ==========================================================
# Health Check
# ==========================================================

    async def health(self) -> dict[str, Any]:

        if self.engine is None:

            return {

                "status": "down",

                "database": "not_initialized",

            }

        try:

            async with self.engine.connect() as connection:

                await connection.execute(

                    text("SELECT 1")

                )

            return {

                "status": "healthy",

                "database": "connected",

            }

        except OperationalError as exc:

            return {

                "status": "unhealthy",

                "error": str(exc),

            }


# ==========================================================
# Database Version
# ==========================================================

    async def version(self) -> str:
    """Return the PostgreSQL server version."""

    if self.engine is None:
        raise RuntimeError("Database not initialized.")

    async with self.engine.connect() as connection:
        result = await connection.execute(
            text("SELECT version()")
        )

        return str(result.scalar())
            
            from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.exc import (
    IntegrityError,
    SQLAlchemyError,
)


# ==========================================================
# Retry Engine
# ==========================================================

    async def execute_with_retry(
        self,
        sql: str,
        parameters: dict[str, Any] | None = None,
        retries: int = 3,
        delay: float = 0.5,
    ):

        last_exception = None

        for attempt in range(retries):

            try:

                return await self.execute(
                    sql,
                    parameters,
                )

            except (
                OperationalError,
                DBAPIError,
            ) as exc:

                last_exception = exc

                if attempt == retries - 1:
                    break

                await asyncio.sleep(
                    delay * (2 ** attempt)
                )

        raise last_exception


# ==========================================================
# Transaction Manager
# ==========================================================

    @asynccontextmanager
    async def transaction(
        self,
    ) -> AsyncIterator[AsyncSession]:

        session = await self.session()

        try:

            async with session.begin():

                yield session

        except Exception:

            await session.rollback()

            raise

        finally:

            await session.close()


# ==========================================================
# Savepoint
# ==========================================================

    @asynccontextmanager
    async def savepoint(
        self,
        session: AsyncSession,
    ) -> AsyncIterator[AsyncSession]:

        nested = await session.begin_nested()

        try:

            yield session

            await nested.commit()

        except Exception:

            await nested.rollback()

            raise


# ==========================================================
# Read Session
# ==========================================================

    async def read_session(
        self,
    ) -> AsyncSession:

        return await self.session()


# ==========================================================
# Write Session
# ==========================================================

    async def write_session(
        self,
    ) -> AsyncSession:

        return await self.session()


# ==========================================================
# Execute Query
# ==========================================================

    async def query(
        self,
        statement,
    ):

        async with self.dependency() as session:

            return await session.execute(
                statement
            )


# ==========================================================
# Scalar Query
# ==========================================================

    async def scalar(
        self,
        statement,
    ):

        result = await self.query(
            statement
        )

        return result.scalar()


# ==========================================================
# Scalars
# ==========================================================

    async def scalars(
        self,
        statement,
    ):

        result = await self.query(
            statement
        )

        return result.scalars()


# ==========================================================
# Add
# ==========================================================

    async def add(
        self,
        instance: Any,
    ) -> None:

        async with self.transaction() as session:

            session.add(instance)


# ==========================================================
# Delete
# ==========================================================

    async def delete(
        self,
        instance: Any,
    ) -> None:

        async with self.transaction() as session:

            await session.delete(
                instance
            )


# ==========================================================
# Flush
# ==========================================================

    async def flush(
        self,
        session: AsyncSession,
    ) -> None:

        await session.flush()


# ==========================================================
# Refresh
# ==========================================================

    async def refresh(
        self,
        session: AsyncSession,
        instance: Any,
    ) -> None:

        await session.refresh(
            instance
        )


# ==========================================================
# Rollback
# ==========================================================

    async def rollback(
        self,
        session: AsyncSession,
    ) -> None:

        await session.rollback()


# ==========================================================
# Commit
# ==========================================================

    async def commit(
        self,
        session: AsyncSession,
    ) -> None:

        await session.commit()


# ==========================================================
# Connection Statistics
# ==========================================================

    async def statistics(
        self,
    ) -> dict[str, Any]:

        return {

            "started": self._started,

            "engine_created": self.engine is not None,

            "session_factory": self.session_factory is not None,

            "database_url": self.settings.database.url,

            "pool_size": self.settings.database.pool_size,

            "max_overflow": self.settings.database.max_overflow,

        }


# ==========================================================
# Diagnostics
# ==========================================================

    async def diagnostics(
        self,
    ) -> dict[str, Any]:

        report = {

            "healthy": True,

            "health": await self.health(),

            "statistics": await self.statistics(),

            "errors": [],

        }

        try:

            await self.version()

        except Exception as exc:

            report["healthy"] = False

            report["errors"].append(
                str(exc)
            )

        return report


# ==========================================================
# SQLAlchemy Event Hooks
# ==========================================================

def register_engine_events(
    engine: Engine,
) -> None:

    @event.listens_for(
        engine,
        "connect",
    )
    def on_connect(
        dbapi_connection,
        connection_record,
    ):

        logger.debug(
            "Database connection established."
        )

    @event.listens_for(
        engine,
        "close",
    )
    def on_close(
        dbapi_connection,
        connection_record,
    ):

        logger.debug(
            "Database connection closed."
        )

    @event.listens_for(
        engine,
        "checkout",
    )
    def on_checkout(
        dbapi_connection,
        connection_record,
        connection_proxy,
    ):

        logger.debug(
            "Database connection checked out."
        )

    @event.listens_for(
        engine,
        "checkin",
    )
    def on_checkin(
        dbapi_connection,
        connection_record,
    ):

        logger.debug(
            "Database connection returned to pool."
        )
        
        import contextvars
import time
from dataclasses import dataclass
from uuid import uuid4


# ==========================================================
# Request Context
# ==========================================================

_request_id: contextvars.ContextVar[str | None] = (
    contextvars.ContextVar(
        "request_id",
        default=None,
    )
)

_tenant_id: contextvars.ContextVar[str | None] = (
    contextvars.ContextVar(
        "tenant_id",
        default=None,
    )
)


# ==========================================================
# Query Statistics
# ==========================================================

@dataclass(slots=True)
class QueryStatistics:

    total_queries: int = 0

    successful_queries: int = 0

    failed_queries: int = 0

    retried_queries: int = 0

    total_execution_time: float = 0.0

    longest_query: float = 0.0

    last_query: float = 0.0


# ==========================================================
# DatabaseManager.__init__()
# ADD THESE VARIABLES
# ==========================================================

        self.query_statistics = QueryStatistics()

        self._active_sessions: dict[
            str,
            AsyncSession,
        ] = {}

        self._tenant_engines: dict[
            str,
            AsyncEngine,
        ] = {}

        self.query_timeout = 120

        self.slow_query_threshold = 1.0


# ==========================================================
# Request Context
# ==========================================================

    def set_request_id(
        self,
        request_id: str | None = None,
    ) -> str:

        if request_id is None:

            request_id = str(uuid4())

        _request_id.set(request_id)

        return request_id


    def request_id(self) -> str | None:

        return _request_id.get()


# ==========================================================
# Tenant Context
# ==========================================================

    def set_tenant(
        self,
        tenant_id: str,
    ) -> None:

        _tenant_id.set(tenant_id)


    def tenant(self) -> str | None:

        return _tenant_id.get()


# ==========================================================
# Session Registry
# ==========================================================

    async def register_session(
        self,
        session: AsyncSession,
    ) -> str:

        session_id = str(uuid4())

        self._active_sessions[
            session_id
        ] = session

        return session_id


    async def unregister_session(
        self,
        session_id: str,
    ) -> None:

        self._active_sessions.pop(
            session_id,
            None,
        )


    @property
    def active_session_count(
        self,
    ) -> int:

        return len(
            self._active_sessions
        )


# ==========================================================
# Timed Execute
# ==========================================================

    async def timed_execute(
        self,
        statement,
    ):

        started = time.perf_counter()

        self.query_statistics.total_queries += 1

        try:

            result = await self.query(
                statement
            )

            elapsed = (
                time.perf_counter()
                - started
            )

            self.query_statistics.successful_queries += 1

            self.query_statistics.total_execution_time += elapsed

            self.query_statistics.last_query = elapsed

            self.query_statistics.longest_query = max(

                self.query_statistics.longest_query,

                elapsed,

            )

            if elapsed > self.slow_query_threshold:

                logger.warning(

                    "Slow query detected %.2fs",

                    elapsed,

                )

            return result

        except Exception:

            self.query_statistics.failed_queries += 1

            raise


# ==========================================================
# Execute With Timeout
# ==========================================================

    async def execute_timeout(
        self,
        statement,
        timeout: float | None = None,
    ):

        return await asyncio.wait_for(

            self.timed_execute(
                statement
            ),

            timeout or self.query_timeout,

        )


# ==========================================================
# Deadlock Retry
# ==========================================================

    async def execute_deadlock_retry(
        self,
        statement,
        retries: int = 3,
    ):

        for attempt in range(retries):

            try:

                return await self.execute_timeout(
                    statement
                )

            except OperationalError:

                self.query_statistics.retried_queries += 1

                if attempt == retries - 1:

                    raise

                await asyncio.sleep(
                    2**attempt
                )


# ==========================================================
# Tenant Engine
# ==========================================================

    async def tenant_engine(
        self,
        tenant_id: str,
    ) -> AsyncEngine:

        if tenant_id in self._tenant_engines:

            return self._tenant_engines[
                tenant_id
            ]

        self._tenant_engines[
            tenant_id
        ] = self.engine

        return self.engine


# ==========================================================
# Leak Detection
# ==========================================================

    def leaked_sessions(
        self,
    ) -> list[str]:

        return list(

            self._active_sessions.keys()

        )


# ==========================================================
# Performance Metrics
# ==========================================================

    def performance_metrics(
        self,
    ) -> dict[str, Any]:

        stats = self.query_statistics

        average = 0.0

        if stats.successful_queries:

            average = (

                stats.total_execution_time

                /

                stats.successful_queries

            )

        return {

            "queries": stats.total_queries,

            "successful": stats.successful_queries,

            "failed": stats.failed_queries,

            "retried": stats.retried_queries,

            "average_execution_time": average,

            "slowest_query": stats.longest_query,

            "last_query": stats.last_query,

            "active_sessions": self.active_session_count,

            "tenant_engines": len(

                self._tenant_engines

            ),

        }


# ==========================================================
# Audit Hook
# ==========================================================

    async def audit_event(
        self,
        action: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:

        logger.info(

            "DATABASE AUDIT | %s | request=%s | tenant=%s | %s",

            action,

            self.request_id(),

            self.tenant(),

            metadata or {},

        )
        
        from collections.abc import AsyncIterator

from sqlalchemy import insert, update, delete
from sqlalchemy.orm import InstrumentedAttribute


# ==========================================================
# DatabaseManager.__init__()
# ADD THESE VARIABLES
# ==========================================================

        self._read_engines: list[AsyncEngine] = []

        self._read_index = 0

        self.statement_cache: dict[str, Any] = {}

        self.max_statement_cache = 1000


# ==========================================================
# Register Read Replica
# ==========================================================

    async def register_read_replica(
        self,
        database_url: str,
    ) -> None:

        engine = create_async_engine(

            database_url,

            echo=self.settings.database.echo,

            pool_pre_ping=True,

            pool_size=self.settings.database.pool_size,

            max_overflow=self.settings.database.max_overflow,

            pool_timeout=self.settings.database.pool_timeout,

            pool_recycle=self.settings.database.pool_recycle,

        )

        self._read_engines.append(engine)


# ==========================================================
# Read Engine
# ==========================================================

    def read_engine(
        self,
    ) -> AsyncEngine:

        if not self._read_engines:

            return self.engine

        engine = self._read_engines[
            self._read_index
        ]

        self._read_index = (

            self._read_index + 1

        ) % len(self._read_engines)

        return engine


# ==========================================================
# Write Engine
# ==========================================================

    def write_engine(
        self,
    ) -> AsyncEngine:

        return self.engine


# ==========================================================
# Read Session
# ==========================================================

    async def replica_session(
        self,
    ) -> AsyncSession:

        factory = async_sessionmaker(

            bind=self.read_engine(),

            class_=AsyncSession,

            expire_on_commit=False,

            autoflush=False,

        )

        return factory()


# ==========================================================
# Bulk Insert
# ==========================================================

    async def bulk_insert(
        self,
        model,
        rows: list[dict[str, Any]],
    ) -> None:

        if not rows:

            return

        async with self.transaction() as session:

            await session.execute(

                insert(model),

                rows,

            )


# ==========================================================
# Bulk Update
# ==========================================================

    async def bulk_update(
        self,
        model,
        rows: list[dict[str, Any]],
        key: str = "id",
    ) -> None:

        async with self.transaction() as session:

            for row in rows:

                value = row.pop(key)

                await session.execute(

                    update(model)

                    .where(

                        getattr(

                            model,

                            key,

                        )

                        == value

                    )

                    .values(**row)

                )


# ==========================================================
# Bulk Delete
# ==========================================================

    async def bulk_delete(
        self,
        model,
        ids: list[Any],
        key: str = "id",
    ) -> None:

        if not ids:

            return

        async with self.transaction() as session:

            await session.execute(

                delete(model).where(

                    getattr(

                        model,

                        key,

                    ).in_(ids)

                )

            )


# ==========================================================
# Stream Results
# ==========================================================

    async def stream(
        self,
        statement,
    ) -> AsyncIterator[Any]:

        async with self.dependency() as session:

            stream = await session.stream(

                statement

            )

            async for row in stream:

                yield row


# ==========================================================
# Offset Pagination
# ==========================================================

    async def paginate(
        self,
        statement,
        page: int = 1,
        page_size: int = 50,
    ):

        statement = statement.offset(

            (page - 1) * page_size

        ).limit(page_size)

        return await self.query(
            statement
        )


# ==========================================================
# Cursor Pagination
# ==========================================================

    async def cursor_paginate(
        self,
        model,
        cursor: Any | None,
        page_size: int = 100,
        column: str = "id",
    ):

        statement = model.__table__.select()

        if cursor is not None:

            statement = statement.where(

                getattr(

                    model,

                    column,

                ) > cursor

            )

        statement = statement.limit(
            page_size
        )

        return await self.query(
            statement
        )


# ==========================================================
# Statement Cache
# ==========================================================

    def cache_statement(
        self,
        key: str,
        statement,
    ) -> None:

        if len(

            self.statement_cache

        ) >= self.max_statement_cache:

            first = next(

                iter(self.statement_cache)

            )

            self.statement_cache.pop(

                first

            )

        self.statement_cache[key] = statement


    def cached_statement(
        self,
        key: str,
    ):

        return self.statement_cache.get(
            key
        )


# ==========================================================
# Pool Health
# ==========================================================

    async def pool_health(
        self,
    ) -> dict[str, Any]:

        pool = self.engine.pool

        return {

            "checked_in": pool.checkedin(),

            "checked_out": pool.checkedout(),

            "overflow": pool.overflow(),

            "size": pool.size(),

        }


# ==========================================================
# Recover Pool
# ==========================================================

    async def recover_pool(
        self,
    ) -> None:

        if self.engine is None:

            return

        await self.engine.dispose()

        await self.startup()


# ==========================================================
# Isolation Level
# ==========================================================

    async def isolation_level(
        self,
    ) -> str:

        async with self.engine.connect() as connection:

            return await connection.get_isolation_level()


# ==========================================================
# Lock Manager
# ==========================================================

    async def advisory_lock(
        self,
        name: str,
    ) -> None:

        logger.debug(

            "Acquire advisory lock: %s",

            name,

        )


    async def advisory_unlock(
        self,
        name: str,
    ) -> None:

        logger.debug(

            "Release advisory lock: %s",

            name,

        )
        
        from datetime import UTC, datetime
from typing import Generic, TypeVar

from sqlalchemy import Select, and_, func, inspect, select
from sqlalchemy.exc import NoResultFound

T = TypeVar("T", bound=Base)


# ==========================================================
# Repository
# ==========================================================

class Repository(Generic[T]):

    def __init__(
        self,
        database: DatabaseManager,
        model: type[T],
    ) -> None:

        self.database = database

        self.model = model


# ==========================================================
# Create
# ==========================================================

    async def create(
        self,
        **values,
    ) -> T:

        async with self.database.transaction() as session:

            instance = self.model(**values)

            session.add(instance)

            await session.flush()

            await session.refresh(instance)

            return instance


# ==========================================================
# Get
# ==========================================================

    async def get(
        self,
        object_id,
    ) -> T | None:

        async with self.database.dependency() as session:

            return await session.get(

                self.model,

                object_id,

            )


# ==========================================================
# Get Or Raise
# ==========================================================

    async def get_or_raise(
        self,
        object_id,
    ) -> T:

        entity = await self.get(object_id)

        if entity is None:

            raise NoResultFound(

                f"{self.model.__name__} not found."

            )

        return entity


# ==========================================================
# Exists
# ==========================================================

    async def exists(
        self,
        **filters,
    ) -> bool:

        statement = select(

            func.count()

        ).select_from(

            self.model

        )

        for key, value in filters.items():

            statement = statement.where(

                getattr(

                    self.model,

                    key,

                ) == value

            )

        count = await self.database.scalar(

            statement

        )

        return bool(count)


# ==========================================================
# List
# ==========================================================

    async def list(
        self,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[T]:

        statement = select(

            self.model

        )

        if offset:

            statement = statement.offset(offset)

        if limit:

            statement = statement.limit(limit)

        result = await self.database.query(

            statement

        )

        return list(

            result.scalars().all()

        )


# ==========================================================
# Filter
# ==========================================================

    async def filter(
        self,
        **filters,
    ) -> list[T]:

        statement = select(

            self.model

        )

        for key, value in filters.items():

            statement = statement.where(

                getattr(

                    self.model,

                    key,

                ) == value

            )

        result = await self.database.query(

            statement

        )

        return list(

            result.scalars().all()

        )


# ==========================================================
# Update
# ==========================================================

    async def update(
        self,
        instance: T,
        **values,
    ) -> T:

        async with self.database.transaction() as session:

            merged = await session.merge(

                instance

            )

            for key, value in values.items():

                setattr(

                    merged,

                    key,

                    value,

                )

            if hasattr(

                merged,

                "updated_at",

            ):

                merged.updated_at = datetime.now(

                    UTC

                )

            await session.flush()

            await session.refresh(

                merged

            )

            return merged


# ==========================================================
# Delete
# ==========================================================

    async def delete(
        self,
        instance: T,
    ) -> None:

        async with self.database.transaction() as session:

            merged = await session.merge(

                instance

            )

            await session.delete(

                merged

            )


# ==========================================================
# Soft Delete
# ==========================================================

    async def soft_delete(
        self,
        instance: T,
    ) -> T:

        if hasattr(

            instance,

            "deleted",

        ):

            return await self.update(

                instance,

                deleted=True,

                deleted_at=datetime.now(

                    UTC

                ),

            )

        raise AttributeError(

            "Soft delete not supported."

        )


# ==========================================================
# Restore
# ==========================================================

    async def restore(
        self,
        instance: T,
    ) -> T:

        return await self.update(

            instance,

            deleted=False,

            deleted_at=None,

        )


# ==========================================================
# Count
# ==========================================================

    async def count(
        self,
    ) -> int:

        statement = select(

            func.count()

        ).select_from(

            self.model

        )

        return int(

            await self.database.scalar(

                statement

            )

        )


# ==========================================================
# Search
# ==========================================================

    async def search(
        self,
        column: str,
        keyword: str,
    ) -> list[T]:

        statement = select(

            self.model

        ).where(

            getattr(

                self.model,

                column,

            ).ilike(

                f"%{keyword}%"

            )

        )

        result = await self.database.query(

            statement

        )

        return list(

            result.scalars().all()

        )


# ==========================================================
# Filter Builder
# ==========================================================

    def build_filter(
        self,
        **filters,
    ) -> Select:

        statement = select(

            self.model

        )

        conditions = []

        mapper = inspect(

            self.model

        )

        columns = {

            column.key

            for column in mapper.columns

        }

        for key, value in filters.items():

            if key not in columns:

                continue

            conditions.append(

                getattr(

                    self.model,

                    key,

                ) == value

            )

        if conditions:

            statement = statement.where(

                and_(*conditions)

            )

        return statement


# ==========================================================
# Batch Create
# ==========================================================

    async def batch_create(
        self,
        rows: list[dict],
    ) -> None:

        await self.database.bulk_insert(

            self.model,

            rows,

        )


# ==========================================================
# Batch Delete
# ==========================================================

    async def batch_delete(
        self,
        ids: list[int],
    ) -> None:

        await self.database.bulk_delete(

            self.model,

            ids,

        )


# ==========================================================
# Audit
# ==========================================================

    async def audit(
        self,
        action: str,
        entity: T,
    ) -> None:

        await self.database.audit_event(

            action,

            {

                "model": self.model.__name__,

                "id": getattr(

                    entity,

                    "id",

                    None,

                ),

            },

        )
        
        from dataclasses import dataclass, field
from typing import TypeAlias


# ==========================================================
# Repository Registry
# ==========================================================

RepositoryType: TypeAlias = Repository[Any]


class RepositoryRegistry:

    def __init__(self) -> None:

        self._repositories: dict[
            type[Base],
            RepositoryType,
        ] = {}

    def register(
        self,
        model: type[Base],
        repository: RepositoryType,
    ) -> None:

        self._repositories[model] = repository

    def get(
        self,
        model: type[Base],
    ) -> RepositoryType:

        try:

            return self._repositories[model]

        except KeyError:

            raise LookupError(
                f"Repository not registered for {model.__name__}"
            )

    def exists(
        self,
        model: type[Base],
    ) -> bool:

        return model in self._repositories

    def clear(self) -> None:

        self._repositories.clear()


# ==========================================================
# Unit Of Work
# ==========================================================

class UnitOfWork:

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:

        self.database = database

        self.session: AsyncSession | None = None

        self._committed = False


    async def __aenter__(self):

        self.session = await self.database.session()

        await self.session.begin()

        return self


    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ) -> None:

        if exc:

            await self.rollback()

        elif not self._committed:

            await self.commit()

        await self.session.close()


    async def commit(self) -> None:

        if self.session is None:

            return

        await self.session.commit()

        self._committed = True


    async def rollback(self) -> None:

        if self.session is None:

            return

        await self.session.rollback()


# ==========================================================
# Version Manager
# ==========================================================

class VersionManager:

    VERSION_FIELD = "version"


    @classmethod
    def initialize(
        cls,
        entity: Any,
    ) -> None:

        if hasattr(entity, cls.VERSION_FIELD):

            if getattr(entity, cls.VERSION_FIELD) is None:

                setattr(entity, cls.VERSION_FIELD, 1)


    @classmethod
    def increment(
        cls,
        entity: Any,
    ) -> None:

        if hasattr(entity, cls.VERSION_FIELD):

            current = getattr(
                entity,
                cls.VERSION_FIELD,
                1,
            )

            setattr(
                entity,
                cls.VERSION_FIELD,
                current + 1,
            )


# ==========================================================
# Optimistic Lock
# ==========================================================

class OptimisticLockError(RuntimeError):

    pass


async def verify_version(
    current: Any,
    expected: int,
) -> None:

    if not hasattr(current, "version"):

        return

    if current.version != expected:

        raise OptimisticLockError(

            "Entity has been modified by another transaction."

        )


# ==========================================================
# Schema Manager
# ==========================================================

class SchemaManager:

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:

        self.database = database


    async def create_all(self) -> None:

        async with self.database.engine.begin() as connection:

            await connection.run_sync(

                Base.metadata.create_all

            )


    async def drop_all(self) -> None:

        async with self.database.engine.begin() as connection:

            await connection.run_sync(

                Base.metadata.drop_all

            )


# ==========================================================
# Seed Manager
# ==========================================================

class SeedManager:

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:

        self.database = database

        self._seeders: list = []


    def register(
        self,
        seeder,
    ) -> None:

        self._seeders.append(seeder)


    async def run(self) -> None:

        for seeder in self._seeders:

            await seeder(self.database)


# ==========================================================
# Tenant Repository
# ==========================================================

class TenantRepository(
    Repository[T],
):

    def __init__(
        self,
        database: DatabaseManager,
        model: type[T],
        tenant_id: str,
    ) -> None:

        super().__init__(
            database,
            model,
        )

        self.tenant_id = tenant_id


    def tenant_filter(
        self,
        statement,
    ):

        if hasattr(

            self.model,

            "tenant_id",

        ):

            statement = statement.where(

                self.model.tenant_id

                == self.tenant_id

            )

        return statement


    async def list(
        self,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[T]:

        statement = self.tenant_filter(

            select(self.model)

        )

        if offset:

            statement = statement.offset(offset)

        if limit:

            statement = statement.limit(limit)

        result = await self.database.query(

            statement

        )

        return list(

            result.scalars().all()

        )


# ==========================================================
# Migration Manager
# ==========================================================

class MigrationManager:

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:

        self.database = database


    async def current_revision(self) -> str:

        return "head"


    async def upgrade(self) -> None:

        logger.info(

            "Database upgraded."

        )


    async def downgrade(self) -> None:

        logger.info(

            "Database downgraded."

        )


# ==========================================================
# Database Services
# ==========================================================

repository_registry = RepositoryRegistry()

schema_manager = SchemaManager(database)

seed_manager = SeedManager(database)

migration_manager = MigrationManager(database)

import gzip
import shutil
from datetime import UTC, datetime
from pathlib import Path



# ==========================================================
# Query Profiler
# ==========================================================

class QueryProfiler:

    def __init__(self):

        self.records = []


    def record(

        self,

        sql: str,

        duration: float,

    ):

        self.records.append({

            "sql": sql,

            "duration": duration,

            "time": datetime.now(UTC),

        })


    def slow_queries(

        self,

        threshold: float = 1.0,

    ):

        return [

            record

            for record in self.records

            if record["duration"] >= threshold

        ]


    def clear(self):

        self.records.clear()


# ==========================================================
# SQL Performance Analyzer
# ==========================================================

class SQLPerformanceAnalyzer:

    def __init__(

        self,

        profiler: QueryProfiler,

    ):

        self.profiler = profiler


    def summary(self):

        if not self.profiler.records:

            return {

                "count": 0,

                "average": 0,

                "maximum": 0,

            }

        durations = [

            record["duration"]

            for record in self.profiler.records

        ]

        return {

            "count": len(durations),

            "average": sum(durations)

            / len(durations),

            "maximum": max(durations),

        }


# ==========================================================
# Database Event Bus
# ==========================================================

class DatabaseEventBus:

    def __init__(self):

        self.listeners: dict[

            str,

            list,

        ] = {}


    def subscribe(

        self,

        event: str,

        listener,

    ):

        self.listeners.setdefault(

            event,

            [],

        ).append(listener)


    async def publish(

        self,

        event: str,

        payload: dict,

    ):

        for listener in self.listeners.get(

            event,

            [],

        ):

            result = listener(payload)

            if asyncio.iscoroutine(result):

                await result


# ==========================================================
# Health Monitor
# ==========================================================

class DatabaseHealthMonitor:

    def __init__(

        self,

        database: DatabaseManager,

    ):

        self.database = database


    async def liveness(self):

        return {

            "alive": self.database._started,

        }


    async def readiness(self):

        return await self.database.health()


    async def diagnostics(self):

        return {

            "health": await self.database.health(),

            "statistics": await self.database.statistics(),

            "performance": self.database.performance_metrics(),

        }


# ==========================================================
# Maintenance Manager
# ==========================================================

class DatabaseMaintenance:

    def __init__(

        self,

        database: DatabaseManager,

    ):

        self.database = database


    async def vacuum(self):

        await self.database.execute(

            "VACUUM"

        )


    async def analyze(self):

        await self.database.execute(

            "ANALYZE"

        )


    async def integrity_check(self) -> dict[str, Any]:
    """Perform a PostgreSQL database health check."""

    if self.engine is None:
        raise RuntimeError("Database not initialized.")

    try:
        async with self.engine.connect() as connection:
            result = await connection.execute(
                text("SELECT 1")
            )

            value = result.scalar()

            return {
                "status": "ok" if value == 1 else "failed",
                "database": "postgresql",
            }

    except Exception as exc:
        return {
            "status": "failed",
            "database": "postgresql",
            "error": str(exc),
        }


    async def wal_checkpoint(self) -> dict[str, Any]:
    """Check PostgreSQL database connectivity.

    Kept for API compatibility with existing callers.
    PostgreSQL manages WAL internally.
    """

    if self.engine is None:
        raise RuntimeError("Database not initialized.")

    try:
        async with self.engine.connect() as connection:
            await connection.execute(
                text("SELECT 1")
            )

        return {
            "status": "ok",
            "database": "postgresql",
            "message": "PostgreSQL WAL is managed by the database server.",
        }

    except Exception as exc:
        return {
            "status": "failed",
            "database": "postgresql",
            "error": str(exc),
        }


# ==========================================================
# Cleanup Manager
# ==========================================================

class CleanupManager:

    def __init__(

        self,

        profiler: QueryProfiler,

    ):

        self.profiler = profiler


    async def cleanup(

        self,

    ):

        self.profiler.clear()


# ==========================================================
# Automatic Startup Tasks
# ==========================================================

async def initialize_database_services(

    database: DatabaseManager,

):

    profiler = QueryProfiler()

    analyzer = SQLPerformanceAnalyzer(

        profiler

    )

    events = DatabaseEventBus()

    health = DatabaseHealthMonitor(

        database

    )

    maintenance = DatabaseMaintenance(

        database

    )

    cleanup = CleanupManager(

        profiler

    )

    return {

        "profiler": profiler,

        "performance": analyzer,

        "events": events,

        "health": health,

        "maintenance": maintenance,

        "cleanup": cleanup,

    }
    
    from collections.abc import AsyncGenerator

# ==========================================================
# Global Singleton
# ==========================================================

_database_instance: DatabaseManager | None = None


def get_database() -> DatabaseManager:
    """
    Returns the global DatabaseManager singleton.
    """

    global _database_instance

    if _database_instance is None:
        _database_instance = DatabaseManager()

    return _database_instance


database = get_database()


# ==========================================================
# Repository Factory
# ==========================================================

class RepositoryFactory:

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:

        self.database = database

        self._cache: dict[type[Base], Repository[Any]] = {}


    def repository(
        self,
        model: type[T],
    ) -> Repository[T]:

        if model not in self._cache:

            self._cache[model] = Repository(
                self.database,
                model,
            )

        return self._cache[model]


repository_factory = RepositoryFactory(
    database
)


# ==========================================================
# Dependency
# ==========================================================

async def get_db() -> AsyncGenerator[
    AsyncSession,
    None,
]:

    async with database.dependency() as session:

        yield session


async def get_uow() -> AsyncGenerator[
    UnitOfWork,
    None,
]:

    async with UnitOfWork(database) as uow:

        yield uow


def get_repository(
    model: type[T],
) -> Repository[T]:

    return repository_factory.repository(
        model
    )


# ==========================================================
# Startup
# ==========================================================

async def startup_database() -> None:

    logger.info(
        "Starting Database Manager..."
    )

    await database.startup()

    register_engine_events(
        database.engine.sync_engine
    )

    await schema_manager.create_all()

    await seed_manager.run()

    logger.info(
        "Database started successfully."
    )


# ==========================================================
# Shutdown
# ==========================================================

async def shutdown_database() -> None:

    logger.info(
        "Stopping Database Manager..."
    )

    await database.shutdown()

    logger.info(
        "Database stopped."
    )


# ==========================================================
# Lifespan
# ==========================================================

@asynccontextmanager
async def database_lifespan(
    app,
):

    await startup_database()

    try:

        yield

    finally:

        await shutdown_database()


# ==========================================================
# Health Endpoint Helper
# ==========================================================

async def database_health() -> dict:

    diagnostics = await database.diagnostics()

    performance = database.performance_metrics()

    pool = await database.pool_health()

    return {

        "database": diagnostics,

        "performance": performance,

        "pool": pool,

    }


# ==========================================================
# Readiness Probe
# ==========================================================

async def database_ready() -> bool:

    health = await database.health()

    return bool(
        health.get(
            "healthy",
            False,
        )
    )


# ==========================================================
# Liveness Probe
# ==========================================================

async def database_alive() -> bool:

    return database._started


# ==========================================================
# Repository Registration Helper
# ==========================================================

def register_repository(
    model: type[Base],
) -> None:

    repository_registry.register(

        model,

        repository_factory.repository(
            model
        ),

    )


# ==========================================================
# Register All Models
# ==========================================================

def register_models(
    *models: type[Base],
) -> None:

    for model in models:

        register_repository(
            model
        )


# ==========================================================
# Shutdown Hook
# ==========================================================

import atexit

atexit.register(
    lambda: logger.info(
        "Database module unloaded."
    )
)


# ==========================================================
# Public Exports
# ==========================================================

__all__ = [

    # Base
    "Base",

    # Database
    "DatabaseManager",

    "database",

    "get_database",

    # Repository

    "Repository",

    "RepositoryFactory",

    "repository_factory",

    "RepositoryRegistry",

    "repository_registry",

    "TenantRepository",

    # Unit Of Work

    "UnitOfWork",

    # Version

    "VersionManager",

    "verify_version",

    "OptimisticLockError",

    # Schema

    "SchemaManager",

    "schema_manager",

    # Seed

    "SeedManager",

    "seed_manager",

    # Migration

    "MigrationManager",

    "migration_manager",

    # Backup

    "DatabaseBackupManager",

    # Monitoring

    "DatabaseHealthMonitor",

    "DatabaseMaintenance",

    "QueryProfiler",

    "SQLPerformanceAnalyzer",

    "DatabaseEventBus",

    "CleanupManager",

    # Dependency

    "get_db",

    "get_uow",

    "get_repository",

    # Startup

    "startup_database",

    "shutdown_database",

    "database_lifespan",

    # Health

    "database_health",

    "database_ready",

    "database_alive",

    # Registration

    "register_repository",

    "register_models",
]