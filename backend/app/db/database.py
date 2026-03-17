"""Async SQLite database wrapper using aiosqlite."""

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    """Thin async wrapper around aiosqlite."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open the database connection and apply the schema."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        # Apply schema (CREATE IF NOT EXISTS is idempotent)
        schema_sql = _SCHEMA_PATH.read_text()
        await self._conn.executescript(schema_sql)
        await self._conn.commit()
        logger.info("Database connected: %s", self._db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Database closed")

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a single SQL statement and return the cursor."""
        assert self._conn is not None, "Database not connected"
        cursor = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cursor

    async def fetch_one(self, sql: str, params: tuple = ()) -> aiosqlite.Row | None:
        """Execute a query and return one row, or None."""
        assert self._conn is not None, "Database not connected"
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchone()

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        """Execute a query and return all rows."""
        assert self._conn is not None, "Database not connected"
        cursor = await self._conn.execute(sql, params)
        return await cursor.fetchall()

    async def insert(self, sql: str, params: tuple = ()) -> int:
        """Execute an INSERT and return the last row ID."""
        assert self._conn is not None, "Database not connected"
        cursor = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
