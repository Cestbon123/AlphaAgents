"""Agent memory CRUD operations.

All memory tables live in the same SQLite database as market data
(default: data/alphaagents.db), initialized by memory_schema.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agent.memory_schema import init_agent_memory


class AgentMemoryRepository:
    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            from app.core.config import get_settings
            db_path = get_settings().data_db
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = init_agent_memory(self._db_path)
        return self._conn

    # ── user profile ──

    def get_profile(self) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT key, value FROM agent_user_profile"
        ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    def get_profile_key(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM agent_user_profile WHERE key=?",
            (key,),
        ).fetchone()
        return row["value"] if row else None

    def update_profile(self, key: str, value: str, source: str = "") -> None:
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            """INSERT INTO agent_user_profile(key, value, updated_at, source)
               VALUES(?,?,?,?)
               ON CONFLICT(key) DO UPDATE SET
               value=excluded.value,
               updated_at=excluded.updated_at,
               source=excluded.source""",
            (key, value, now, source),
        )
        self.conn.commit()

    # ── decision memory ──

    def add_decision(self, decision: dict[str, Any]) -> str:
        decision_id = decision.get("id") or str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            """INSERT INTO agent_decision_memory(id, symbol, decision_date,
               decision_type, conclusion, outcome, source, created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                decision_id,
                decision.get("symbol"),
                decision.get("decision_date"),
                decision.get("decision_type"),
                decision["conclusion"],
                decision.get("outcome"),
                decision.get("source", ""),
                decision.get("created_at", now),
            ),
        )
        self.conn.commit()
        return decision_id

    def search_decisions(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        like = f"%{query}%"
        rows = self.conn.execute(
            """SELECT * FROM agent_decision_memory
               WHERE conclusion LIKE ? OR symbol LIKE ?
               ORDER BY created_at DESC LIMIT ?""",
            (like, like, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_decisions_for_symbol(self, symbol: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT * FROM agent_decision_memory
               WHERE symbol=? ORDER BY created_at DESC""",
            (symbol,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── stock impressions ──

    def get_impression(self, symbol: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM agent_stock_impressions WHERE symbol=?",
            (symbol,),
        ).fetchone()
        return dict(row) if row else None

    def upsert_impression(self, symbol: str, status: str, impression: str) -> None:
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            """INSERT INTO agent_stock_impressions(symbol, status, impression, last_updated)
               VALUES(?,?,?,?)
               ON CONFLICT(symbol) DO UPDATE SET
               status=excluded.status,
               impression=excluded.impression,
               last_updated=excluded.last_updated""",
            (symbol, status, impression, now),
        )
        self.conn.commit()

    def get_all_impressions(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM agent_stock_impressions ORDER BY last_updated DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ── sessions ──

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            "INSERT INTO agent_sessions(id, started_at) VALUES(?,?)",
            (session_id, now),
        )
        self.conn.commit()
        return session_id

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str | None = None,
        tool_calls: str | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
    ) -> None:
        now = datetime.now(UTC).timestamp()
        self.conn.execute(
            """INSERT INTO agent_messages(
                   session_id, role, content, tool_calls, tool_call_id, tool_name, timestamp
               )
               VALUES(?,?,?,?,?,?,?)""",
            (session_id, role, content, tool_calls, tool_call_id, tool_name, now),
        )
        self.conn.commit()

    def get_session_messages(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT * FROM agent_messages WHERE session_id=?
               ORDER BY timestamp ASC LIMIT ?""",
            (session_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_sessions(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        # FTS5 with default unicode61 tokenizer splits CJK into single chars,
        # so fall back to LIKE for CJK queries. Use FTS for ASCII/latin queries.
        if any('\u4e00' <= c <= '\u9fff' for c in query):
            like = f"%{query}%"
            rows = self.conn.execute(
                """SELECT * FROM agent_messages
                   WHERE content LIKE ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (like, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT m.* FROM agent_messages m
                   JOIN agent_messages_fts f ON m.id = f.rowid
                   WHERE agent_messages_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def close_session(self, session_id: str, summary: str = "") -> None:
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            "UPDATE agent_sessions SET ended_at=?, summary=? WHERE id=?",
            (now, summary, session_id),
        )
        self.conn.commit()

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT id, started_at, ended_at, summary,
                      (SELECT COUNT(*) FROM agent_messages WHERE session_id = s.id) as message_count
               FROM agent_sessions s
               ORDER BY started_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: str) -> bool:
        self.conn.execute("DELETE FROM agent_messages WHERE session_id=?", (session_id,))
        cursor = self.conn.execute("DELETE FROM agent_sessions WHERE id=?", (session_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    # ── maintenance ──

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
