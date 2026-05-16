from __future__ import annotations

import sqlite3
import os
from pathlib import Path


class Store:
    def __init__(self, path: str = "bot_state.db", account_id: str | None = None) -> None:
        self.path = Path(path)
        self.account_id = account_id or os.getenv("SOLOA_ACCOUNT_ID", "soloa-ai").strip() or "soloa-ai"
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
            for table in ("seen_items", "subreddit_rules"):
                columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
                column_names = {col[1] for col in columns}
                if "account_id" not in column_names:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN account_id TEXT")
                    conn.execute(
                        f"UPDATE {table} SET account_id = ? WHERE account_id IS NULL OR account_id = ''",
                        (self.account_id,),
                    )
            seen_columns = conn.execute("PRAGMA table_info(seen_items)").fetchall()
            if [col[1] for col in seen_columns if col[5]] == ["thing_id"]:
                conn.execute("ALTER TABLE seen_items RENAME TO seen_items_legacy_single_account")
                conn.execute(
                    """
                    CREATE TABLE seen_items (
                        account_id TEXT NOT NULL DEFAULT 'soloa-ai',
                        thing_id TEXT NOT NULL,
                        seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (account_id, thing_id)
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO seen_items (account_id, thing_id, seen_at)
                    SELECT COALESCE(account_id, ?), thing_id, seen_at
                    FROM seen_items_legacy_single_account
                    """,
                    (self.account_id,),
                )
                conn.execute("DROP TABLE seen_items_legacy_single_account")
            rules_columns = conn.execute("PRAGMA table_info(subreddit_rules)").fetchall()
            if [col[1] for col in rules_columns if col[5]] == ["subreddit"]:
                conn.execute("ALTER TABLE subreddit_rules RENAME TO subreddit_rules_legacy_single_account")
                conn.execute(
                    """
                    CREATE TABLE subreddit_rules (
                        account_id TEXT NOT NULL DEFAULT 'soloa-ai',
                        subreddit TEXT NOT NULL,
                        rules_text TEXT NOT NULL,
                        refreshed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (account_id, subreddit)
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO subreddit_rules (account_id, subreddit, rules_text, refreshed_at)
                    SELECT COALESCE(account_id, ?), subreddit, rules_text, refreshed_at
                    FROM subreddit_rules_legacy_single_account
                    """,
                    (self.account_id,),
                )
                conn.execute("DROP TABLE subreddit_rules_legacy_single_account")

    def is_seen(self, thing_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_items WHERE thing_id = ? AND account_id = ?",
                (thing_id, self.account_id),
            ).fetchone()
        return row is not None

    def mark_seen(self, thing_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO seen_items (thing_id, account_id) VALUES (?, ?)",
                (thing_id, self.account_id),
            )

    def upsert_rules(self, subreddit: str, rules_text: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO subreddit_rules (account_id, subreddit, rules_text, refreshed_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(account_id, subreddit) DO UPDATE SET
                    rules_text = excluded.rules_text,
                    refreshed_at = CURRENT_TIMESTAMP
                """,
                (self.account_id, subreddit.lower(), rules_text),
            )

    def get_rules(self, subreddit: str) -> str:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT rules_text FROM subreddit_rules WHERE subreddit = ? AND account_id = ?",
                (subreddit.lower(), self.account_id),
            ).fetchone()
        return row[0] if row else ""
