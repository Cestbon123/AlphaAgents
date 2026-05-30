from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class ExternalDataCache:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def get(self, symbol: str, data_key: str) -> dict[str, Any] | list[dict[str, Any]] | None:
        if not self.db_path.exists():
            return None

        with sqlite3.connect(self.db_path) as connection:
            if not _table_exists(connection, "external_research_cache"):
                return None
            row = connection.execute(
                """
                SELECT payload_json
                FROM external_research_cache
                WHERE symbol = ? AND data_key = ?
                LIMIT 1
                """,
                (symbol, data_key),
            ).fetchone()

        if row is None:
            return None
        payload = json.loads(row[0])
        return payload if isinstance(payload, dict | list) else None

    def set(
        self,
        symbol: str,
        data_key: str,
        payload: dict[str, Any] | list[dict[str, Any]],
    ) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS external_research_cache (
                    symbol TEXT NOT NULL,
                    data_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (symbol, data_key)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO external_research_cache (symbol, data_key, payload_json, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(symbol, data_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = datetime('now')
                """,
                (symbol, data_key, json.dumps(payload, ensure_ascii=False)),
            )


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )
