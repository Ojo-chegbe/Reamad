from __future__ import annotations

import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path: str = "bot_state.db") -> None:
        self.path = Path(path)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_items (
                    thing_id TEXT PRIMARY KEY,
                    seen_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS subreddit_rules (
                    subreddit TEXT PRIMARY KEY,
                    rules_text TEXT NOT NULL,
                    refreshed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def is_seen(self, thing_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_items WHERE thing_id = ?",
                (thing_id,),
            ).fetchone()
        return row is not None

    def mark_seen(self, thing_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO seen_items (thing_id) VALUES (?)",
                (thing_id,),
            )

    def upsert_rules(self, subreddit: str, rules_text: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO subreddit_rules (subreddit, rules_text, refreshed_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(subreddit) DO UPDATE SET
                    rules_text = excluded.rules_text,
                    refreshed_at = CURRENT_TIMESTAMP
                """,
                (subreddit.lower(), rules_text),
            )

    def get_rules(self, subreddit: str) -> str:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT rules_text FROM subreddit_rules WHERE subreddit = ?",
                (subreddit.lower(),),
            ).fetchone()
        return row[0] if row else ""

