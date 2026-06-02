"""Agent memory database schema."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

DDL = """
CREATE TABLE IF NOT EXISTS agent_schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_user_profile (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    source TEXT
);

CREATE TABLE IF NOT EXISTS agent_decision_memory (
    id            TEXT PRIMARY KEY,
    symbol        TEXT,
    decision_date TEXT,
    decision_type TEXT,
    conclusion    TEXT NOT NULL,
    outcome       TEXT,
    source        TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_decision_symbol ON agent_decision_memory(symbol);
CREATE INDEX IF NOT EXISTS idx_decision_date ON agent_decision_memory(decision_date);

CREATE TABLE IF NOT EXISTS agent_stock_impressions (
    symbol       TEXT PRIMARY KEY,
    status       TEXT NOT NULL,
    impression   TEXT NOT NULL,
    last_updated TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_sessions (
    id         TEXT PRIMARY KEY,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at   TEXT,
    summary    TEXT
);

CREATE TABLE IF NOT EXISTS agent_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL REFERENCES agent_sessions(id),
    role         TEXT NOT NULL,
    content      TEXT,
    tool_calls   TEXT,
    tool_call_id TEXT,
    tool_name    TEXT,
    timestamp    REAL NOT NULL DEFAULT (unixepoch('subsec'))
);

CREATE INDEX IF NOT EXISTS idx_msg_session ON agent_messages(session_id, timestamp);

CREATE VIRTUAL TABLE IF NOT EXISTS agent_messages_fts USING fts5(
    content, tool_name, tool_calls
);

CREATE TRIGGER IF NOT EXISTS agent_msg_fts_insert AFTER INSERT ON agent_messages BEGIN
    INSERT INTO agent_messages_fts(rowid, content, tool_name, tool_calls)
    VALUES (
        new.id,
        COALESCE(new.content,''),
        COALESCE(new.tool_name,''),
        COALESCE(new.tool_calls,'')
    );
END;

CREATE TRIGGER IF NOT EXISTS agent_msg_fts_delete AFTER DELETE ON agent_messages BEGIN
    DELETE FROM agent_messages_fts WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS agent_msg_fts_update AFTER UPDATE ON agent_messages BEGIN
    DELETE FROM agent_messages_fts WHERE rowid = old.id;
    INSERT INTO agent_messages_fts(rowid, content, tool_name, tool_calls)
    VALUES (
        new.id,
        COALESCE(new.content,''),
        COALESCE(new.tool_name,''),
        COALESCE(new.tool_calls,'')
    );
END;
"""


def init_agent_memory(db_path: Path | str) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(DDL)
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(agent_messages)").fetchall()
    }
    if "tool_call_id" not in columns:
        conn.execute("ALTER TABLE agent_messages ADD COLUMN tool_call_id TEXT")
    current = conn.execute(
        "SELECT version FROM agent_schema_version"
    ).fetchone()
    if current is None:
        conn.execute(
            "INSERT INTO agent_schema_version(version) VALUES(?)",
            (SCHEMA_VERSION,),
        )
    conn.commit()
    return conn
