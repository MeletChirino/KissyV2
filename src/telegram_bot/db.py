"""SQLite persistence for conversation history.

Thin wrapper around the standard library `sqlite3` module. Stores one
transcript per active conversation in the `conversations` table:

    id           INTEGER  autoincrement PK
    chat_id      INTEGER  Telegram chat id
    conversation TEXT     full transcript, appended to
    status       BOOLEAN  1 = active, 0 = closed

The schema is created by ``scripts/db/schema.sql`` and is not owned by
this module — ``ensure_schema()`` runs ``CREATE TABLE IF NOT EXISTS`` so
the helpers are safe to import even before the setup script has been
run, but the canonical schema lives in the SQL file.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path

DEFAULT_DB_PATH = Path("data/conversations.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    conversation TEXT NOT NULL,
    status BOOLEAN NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_conversations_chat_active
    ON conversations (chat_id, status);
"""


def resolve_db_path(path: str | os.PathLike[str] | None = None) -> Path:
    """Return the absolute path to the database file.

    Resolution order: explicit argument > ``CONVERSATIONS_DB`` env var
    > ``data/conversations.db`` relative to the current working
    directory.
    """
    if path is not None:
        return Path(path)
    env = os.getenv("CONVERSATIONS_DB")
    if env:
        return Path(env)
    return DEFAULT_DB_PATH


def connect(db_path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    """Open a connection with row access by name.

    Ensures the parent directory exists and the schema is in place
    before returning. Callers are responsible for closing the
    connection (use ``with`` / ``contextlib.closing``).
    """
    resolved = resolve_db_path(db_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(resolved)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def ensure_schema(db_path: str | os.PathLike[str] | None = None) -> None:
    """Idempotently create the schema without keeping a connection open."""
    with closing(connect(db_path)):
        pass


def get_active(db_path: str | os.PathLike[str] | None, chat_id: int) -> sqlite3.Row | None:
    """Return the active row for ``chat_id`` or ``None``.

    "Active" means ``status = 1``. There is at most one active row per
    chat; if the data is ever corrupted and there are several, the
    newest one wins.
    """
    with closing(connect(db_path)) as conn:
        return conn.execute(
            """
            SELECT id, chat_id, conversation, status
            FROM conversations
            WHERE chat_id = ? AND status = 1
            ORDER BY id DESC
            LIMIT 1
            """,
            (chat_id,),
        ).fetchone()


def create_active(db_path: str | os.PathLike[str] | None, chat_id: int) -> int:
    """Insert a new active row with an empty transcript. Returns the new id."""
    with closing(connect(db_path)) as conn:
        cursor = conn.execute(
            "INSERT INTO conversations (chat_id, conversation, status) VALUES (?, ?, 1)",
            (chat_id, ""),
        )
        conn.commit()
        return int(cursor.lastrowid)


def append_turn(
    db_path: str | os.PathLike[str] | None,
    row_id: int,
    user_text: str,
    assistant_text: str,
) -> str:
    """Append one USER/SYSTEM turn to a row and return the new transcript.

    Both pieces of text are stored verbatim. Newlines inside the
    messages are preserved; the turn separator is a single blank line.
    """
    turn = f"USER:{user_text}\n\nSYSTEM:{assistant_text}\n\n"
    with closing(connect(db_path)) as conn:
        conn.execute(
            "UPDATE conversations SET conversation = conversation || ? WHERE id = ?",
            (turn, row_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT conversation FROM conversations WHERE id = ?", (row_id,)
        ).fetchone()
    return row["conversation"] if row else ""


def get_transcript(
    db_path: str | os.PathLike[str] | None,
    row_id: int,
) -> str:
    """Read the full transcript for a row (empty string if not found)."""
    with closing(connect(db_path)) as conn:
        row = conn.execute(
            "SELECT conversation FROM conversations WHERE id = ?", (row_id,)
        ).fetchone()
    return row["conversation"] if row else ""


def close_active(db_path: str | os.PathLike[str] | None, row_id: int) -> None:
    """Mark a row as closed (status = 0). Idempotent."""
    with closing(connect(db_path)) as conn:
        conn.execute(
            "UPDATE conversations SET status = 0 WHERE id = ?", (row_id,)
        )
        conn.commit()
