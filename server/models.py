"""
RemoteGate database layer (aiosqlite).

Provides async CRUD helpers for the agents and sessions tables.
"""

import logging
import time
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


async def init_db(db_path: str) -> None:
    """Create tables if they do not exist.

    Args:
        db_path: Filesystem path to the SQLite database file.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                agent_id      TEXT PRIMARY KEY,
                hostname      TEXT NOT NULL,
                resolution_w  INTEGER NOT NULL DEFAULT 0,
                resolution_h  INTEGER NOT NULL DEFAULT 0,
                status        TEXT NOT NULL DEFAULT 'offline',
                last_seen     REAL NOT NULL DEFAULT 0
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id    TEXT NOT NULL,
                client_addr TEXT NOT NULL,
                started_at  REAL NOT NULL,
                ended_at    REAL
            )
            """
        )
        await db.commit()
        logger.info("Database initialised at %s", db_path)


# ---------------------------------------------------------------------------
# Agent CRUD
# ---------------------------------------------------------------------------

async def register_agent(
    db_path: str,
    agent_id: str,
    hostname: str,
    resolution_w: int,
    resolution_h: int,
) -> None:
    """Insert or update an agent record and mark it online."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO agents (agent_id, hostname, resolution_w, resolution_h, status, last_seen)
            VALUES (?, ?, ?, ?, 'online', ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                hostname     = excluded.hostname,
                resolution_w = excluded.resolution_w,
                resolution_h = excluded.resolution_h,
                status       = 'online',
                last_seen    = excluded.last_seen
            """,
            (agent_id, hostname, resolution_w, resolution_h, time.time()),
        )
        await db.commit()


async def update_agent_status(
    db_path: str,
    agent_id: str,
    status: str,
) -> None:
    """Set an agent's status (e.g. 'online', 'offline')."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE agents SET status = ?, last_seen = ? WHERE agent_id = ?",
            (status, time.time(), agent_id),
        )
        await db.commit()


async def get_agents(db_path: str) -> list[dict]:
    """Return all registered agents."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM agents")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_agent(db_path: str, agent_id: str) -> dict | None:
    """Return a single agent or None."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

async def create_session(
    db_path: str,
    agent_id: str,
    client_addr: str,
) -> int:
    """Create a new session record and return its id."""
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "INSERT INTO sessions (agent_id, client_addr, started_at) VALUES (?, ?, ?)",
            (agent_id, client_addr, time.time()),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def end_session(db_path: str, session_id: int) -> None:
    """Mark a session as ended."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (time.time(), session_id),
        )
        await db.commit()
