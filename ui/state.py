from __future__ import annotations

import json
import os
import secrets
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DB_PATH = Path("ui_state.db")
DEFAULT_ACCOUNT_ID = "soloa-ai"
DEFAULT_ACCOUNT_NAME = "Soloa AI"
DEFAULT_REJECTED_RETENTION_HOURS = 24
PIPELINE_STAGES = {
    "new",
    "qualified",
    "drafted",
    "approved",
    "posted",
    "replied_back",
    "converted",
    "lost",
    "rejected",
    "pending",
}


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def get_default_profile() -> dict[str, Any]:
    from src.soloa_profile import default_profile

    return default_profile()


def get_initial_soloa_profile() -> dict[str, Any]:
    profile_path = Path("bot_profile.json")
    if profile_path.exists():
        try:
            with profile_path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                from src.soloa_profile import normalize_profile

                return normalize_profile(loaded)
        except Exception:
            pass
    return get_default_profile()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
    column_names = {col[1] for col in columns}
    if column not in column_names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _migrate_multitenant_primary_keys(conn: sqlite3.Connection) -> None:
    opportunity_columns = conn.execute("PRAGMA table_info(opportunities)").fetchall()
    opportunity_pk = [col[1] for col in opportunity_columns if col[5]]
    if opportunity_pk == ["id"]:
        conn.execute("ALTER TABLE opportunities RENAME TO opportunities_legacy_single_account")
        conn.execute(
            """
            CREATE TABLE opportunities (
                id TEXT NOT NULL,
                account_id TEXT NOT NULL DEFAULT 'soloa-ai',
                platform TEXT NOT NULL DEFAULT 'reddit',
                subreddit TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                url TEXT NOT NULL,
                score INTEGER NOT NULL,
                status TEXT NOT NULL,
                status_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reasons_json TEXT NOT NULL,
                drafts_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                posted_reply_url TEXT NOT NULL DEFAULT '',
                selected_draft_index INTEGER,
                replied_at DATETIME,
                followup_sentiment TEXT NOT NULL DEFAULT '',
                clicks INTEGER NOT NULL DEFAULT 0,
                signups INTEGER NOT NULL DEFAULT 0,
                conversion_value REAL NOT NULL DEFAULT 0,
                next_follow_up_at DATETIME,
                operator_notes TEXT NOT NULL DEFAULT '',
                feedback_label TEXT NOT NULL DEFAULT '',
                feedback_note TEXT NOT NULL DEFAULT '',
                campaign_name TEXT NOT NULL DEFAULT '',
                product_area TEXT NOT NULL DEFAULT '',
                updated_at DATETIME,
                PRIMARY KEY (account_id, id)
            )
            """
        )
        legacy_names = {col[1] for col in opportunity_columns}
        select_account = "account_id" if "account_id" in legacy_names else f"'{DEFAULT_ACCOUNT_ID}'"
        conn.execute(
            f"""
            INSERT OR IGNORE INTO opportunities (
                id, account_id, platform, subreddit, title, body, url, score, status,
                status_updated_at, reasons_json, drafts_json, created_at, posted_reply_url,
                selected_draft_index, replied_at, followup_sentiment, clicks, signups,
                conversion_value, next_follow_up_at, operator_notes, feedback_label,
                feedback_note, campaign_name, product_area, updated_at
            )
            SELECT
                id, COALESCE({select_account}, '{DEFAULT_ACCOUNT_ID}'), COALESCE(platform, 'reddit'),
                subreddit, title, body, url, score, status, status_updated_at, reasons_json,
                drafts_json, created_at, posted_reply_url, selected_draft_index, replied_at,
                followup_sentiment, clicks, signups, conversion_value, next_follow_up_at,
                operator_notes, feedback_label, feedback_note, campaign_name, product_area, updated_at
            FROM opportunities_legacy_single_account
            """
        )
        conn.execute("DROP TABLE opportunities_legacy_single_account")

    playbook_columns = conn.execute("PRAGMA table_info(playbooks)").fetchall()
    playbook_pk = [col[1] for col in playbook_columns if col[5]]
    if playbook_pk == ["subreddit"]:
        conn.execute("ALTER TABLE playbooks RENAME TO playbooks_legacy_single_account")
        conn.execute(
            """
            CREATE TABLE playbooks (
                account_id TEXT NOT NULL DEFAULT 'soloa-ai',
                subreddit TEXT NOT NULL,
                rules_text TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, subreddit)
            )
            """
        )
        legacy_names = {col[1] for col in playbook_columns}
        select_account = "account_id" if "account_id" in legacy_names else f"'{DEFAULT_ACCOUNT_ID}'"
        conn.execute(
            f"""
            INSERT OR IGNORE INTO playbooks (account_id, subreddit, rules_text, notes, updated_at)
            SELECT COALESCE({select_account}, '{DEFAULT_ACCOUNT_ID}'), subreddit, rules_text, notes, updated_at
            FROM playbooks_legacy_single_account
            """
        )
        conn.execute("DROP TABLE playbooks_legacy_single_account")


def _rejected_retention_hours() -> int:
    raw_value = os.getenv("REJECTED_RETENTION_HOURS", str(DEFAULT_REJECTED_RETENTION_HOURS)).strip()
    try:
        parsed = int(raw_value)
    except ValueError:
        return DEFAULT_REJECTED_RETENTION_HOURS
    return max(1, parsed)


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                current_account_id TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_accounts (
                user_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'owner',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, account_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO accounts (id, name, profile_json)
            VALUES (?, ?, ?)
            """,
            (DEFAULT_ACCOUNT_ID, DEFAULT_ACCOUNT_NAME, json.dumps(get_initial_soloa_profile())),
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL DEFAULT 'reddit',
                subreddit TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                url TEXT NOT NULL,
                score INTEGER NOT NULL,
                status TEXT NOT NULL,
                status_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reasons_json TEXT NOT NULL,
                drafts_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = conn.execute("PRAGMA table_info(opportunities)").fetchall()
        column_names = {col[1] for col in columns}
        if "account_id" not in column_names:
            conn.execute("ALTER TABLE opportunities ADD COLUMN account_id TEXT")
            conn.execute(
                "UPDATE opportunities SET account_id = ? WHERE account_id IS NULL OR account_id = ''",
                (DEFAULT_ACCOUNT_ID,),
            )
        if "platform" not in column_names:
            conn.execute("ALTER TABLE opportunities ADD COLUMN platform TEXT")
        conn.execute("UPDATE opportunities SET platform = 'reddit' WHERE platform IS NULL OR platform = ''")
        if "status_updated_at" not in column_names:
            conn.execute(
                "ALTER TABLE opportunities ADD COLUMN status_updated_at DATETIME"
            )
            conn.execute(
                "UPDATE opportunities SET status_updated_at = created_at WHERE status_updated_at IS NULL"
            )
        extra_columns = {
            "posted_reply_url": "TEXT NOT NULL DEFAULT ''",
            "selected_draft_index": "INTEGER",
            "replied_at": "DATETIME",
            "followup_sentiment": "TEXT NOT NULL DEFAULT ''",
            "clicks": "INTEGER NOT NULL DEFAULT 0",
            "signups": "INTEGER NOT NULL DEFAULT 0",
            "conversion_value": "REAL NOT NULL DEFAULT 0",
            "next_follow_up_at": "DATETIME",
            "operator_notes": "TEXT NOT NULL DEFAULT ''",
            "feedback_label": "TEXT NOT NULL DEFAULT ''",
            "feedback_note": "TEXT NOT NULL DEFAULT ''",
            "campaign_name": "TEXT NOT NULL DEFAULT ''",
            "product_area": "TEXT NOT NULL DEFAULT ''",
            "updated_at": "DATETIME",
        }
        for column, definition in extra_columns.items():
            if column not in column_names:
                conn.execute(f"ALTER TABLE opportunities ADD COLUMN {column} {definition}")
        conn.execute("UPDATE opportunities SET status = 'new' WHERE status = 'pending'")
        conn.execute("UPDATE opportunities SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS playbooks (
                subreddit TEXT PRIMARY KEY,
                rules_text TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_column(conn, "playbooks", "account_id", "TEXT")
        conn.execute(
            "UPDATE playbooks SET account_id = ? WHERE account_id IS NULL OR account_id = ''",
            (DEFAULT_ACCOUNT_ID,),
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL DEFAULT 'reddit',
                opportunity_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        audit_columns = conn.execute("PRAGMA table_info(audit_log)").fetchall()
        audit_column_names = {col[1] for col in audit_columns}
        if "account_id" not in audit_column_names:
            conn.execute("ALTER TABLE audit_log ADD COLUMN account_id TEXT")
            conn.execute(
                "UPDATE audit_log SET account_id = ? WHERE account_id IS NULL OR account_id = ''",
                (DEFAULT_ACCOUNT_ID,),
            )
        if "platform" not in audit_column_names:
            conn.execute("ALTER TABLE audit_log ADD COLUMN platform TEXT")
        conn.execute("UPDATE audit_log SET platform = 'reddit' WHERE platform IS NULL OR platform = ''")
        _migrate_multitenant_primary_keys(conn)


def bootstrap_owner(email: str, password_hash: str, display_name: str = "Workspace owner") -> None:
    init_db()
    with _conn() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email.lower(),)).fetchone()
        if existing:
            user_id = existing[0]
        else:
            user_id = _new_token()
            conn.execute(
                """
                INSERT INTO users (id, email, password_hash, display_name, current_account_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, email.lower(), password_hash, display_name, DEFAULT_ACCOUNT_ID),
            )
        current_allowed = conn.execute(
            "SELECT 1 FROM user_accounts WHERE user_id = ? AND account_id = (SELECT current_account_id FROM users WHERE id = ?)",
            (user_id, user_id),
        ).fetchone()
        if not current_allowed:
            conn.execute(
                "UPDATE users SET current_account_id = ? WHERE id = ?",
                (DEFAULT_ACCOUNT_ID, user_id),
            )
        conn.execute(
            """
            INSERT OR IGNORE INTO user_accounts (user_id, account_id, role)
            VALUES (?, ?, 'owner')
            """,
            (user_id, DEFAULT_ACCOUNT_ID),
        )


def create_user(email: str, password_hash: str, account_name: str, display_name: str = "") -> dict[str, Any]:
    init_db()
    account_id = _new_token()
    user_id = _new_token()
    normalized_email = email.strip().lower()
    normalized_account = account_name.strip() or "New account"
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO accounts (id, name, profile_json)
            VALUES (?, ?, ?)
            """,
            (account_id, normalized_account, json.dumps(get_default_profile())),
        )
        conn.execute(
            """
            INSERT INTO users (id, email, password_hash, display_name, current_account_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, normalized_email, password_hash, display_name.strip(), account_id),
        )
        conn.execute(
            "INSERT INTO user_accounts (user_id, account_id, role) VALUES (?, ?, 'owner')",
            (user_id, account_id),
        )
    return get_user_context(user_id) or {}


def create_account_for_user(user_id: str, account_name: str) -> dict[str, Any]:
    init_db()
    account_id = _new_token()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO accounts (id, name, profile_json) VALUES (?, ?, ?)",
            (account_id, account_name.strip() or "New account", json.dumps(get_default_profile())),
        )
        conn.execute(
            "INSERT INTO user_accounts (user_id, account_id, role) VALUES (?, ?, 'owner')",
            (user_id, account_id),
        )
        conn.execute("UPDATE users SET current_account_id = ? WHERE id = ?", (account_id, user_id))
    return get_user_context(user_id) or {}


def create_session(user_id: str) -> str:
    token = _new_token()
    with _conn() as conn:
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    return token


def delete_session(token: str) -> None:
    if not token:
        return
    with _conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def get_user_by_email(email: str) -> dict[str, Any] | None:
    init_db()
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash, display_name, current_account_id FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "email": row[1],
        "password_hash": row[2],
        "display_name": row[3],
        "current_account_id": row[4],
    }


def get_user_by_session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    init_db()
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT users.id, users.email, users.display_name, users.current_account_id
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?
            """,
            (token,),
        ).fetchone()
    if not row:
        return None
    return {"id": row[0], "email": row[1], "display_name": row[2], "current_account_id": row[3]}


def get_user_context(user_id: str) -> dict[str, Any] | None:
    init_db()
    with _conn() as conn:
        user = conn.execute(
            "SELECT id, email, display_name, current_account_id FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not user:
            return None
        accounts = conn.execute(
            """
            SELECT accounts.id, accounts.name, user_accounts.role
            FROM user_accounts
            JOIN accounts ON accounts.id = user_accounts.account_id
            WHERE user_accounts.user_id = ?
            ORDER BY accounts.created_at ASC
            """,
            (user_id,),
        ).fetchall()
    return {
        "user": {
            "id": user[0],
            "email": user[1],
            "display_name": user[2],
            "current_account_id": user[3],
        },
        "accounts": [{"id": row[0], "name": row[1], "role": row[2]} for row in accounts],
    }


def set_current_account(user_id: str, account_id: str) -> bool:
    init_db()
    with _conn() as conn:
        allowed = conn.execute(
            "SELECT 1 FROM user_accounts WHERE user_id = ? AND account_id = ?",
            (user_id, account_id),
        ).fetchone()
        if not allowed:
            return False
        conn.execute("UPDATE users SET current_account_id = ? WHERE id = ?", (account_id, user_id))
    return True


def get_account_profile(account_id: str) -> dict[str, Any]:
    init_db()
    with _conn() as conn:
        row = conn.execute("SELECT profile_json FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if not row:
        return get_default_profile()
    try:
        from src.soloa_profile import normalize_profile

        loaded = json.loads(row[0])
        if isinstance(loaded, dict):
            return normalize_profile(loaded)
    except Exception:
        pass
    return get_default_profile()


def save_account_profile(account_id: str, data: dict[str, Any]) -> None:
    from src.soloa_profile import normalize_profile

    init_db()
    with _conn() as conn:
        conn.execute(
            """
            UPDATE accounts
            SET profile_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(normalize_profile(data)), account_id),
        )


def seed_if_empty() -> None:
    if os.getenv("UI_SEED_DEMO", "").strip() != "1":
        return

    with _conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM opportunities WHERE account_id = ?", (DEFAULT_ACCOUNT_ID,)).fetchone()
        if row and row[0] > 0:
            return

        sample = [
            {
                "id": "t3_mock_001",
                "subreddit": "SaaS",
                "title": "What AI stack are you using for short-form video content?",
                "body": "I run a tiny agency and need to speed up script, visuals and voice.",
                "url": "https://reddit.com/r/SaaS/comments/mock001",
                "score": 81,
                "status": "pending",
                "reasons": [
                    "High intent request",
                    "Strong keyword overlap: ai tools, video, workflow",
                    "Subreddit allows tool discussion when useful",
                ],
                "drafts": [
                    "If speed is the goal, test one repeatable flow for 7 days: idea -> script -> visuals -> voiceover. Measure edit time per video.",
                    "I’d compare tools by consistency, not single output quality. The best stack is usually the one that needs fewer retries.",
                    "A simple rubric helps: output quality, total production minutes, and cost per publish-ready clip.",
                ],
            },
            {
                "id": "t3_mock_002",
                "subreddit": "marketing",
                "title": "Need better workflow for product ad creatives",
                "body": "Any practical process to generate variants without burning designer time?",
                "url": "https://reddit.com/r/marketing/comments/mock002",
                "score": 74,
                "status": "pending",
                "reasons": [
                    "Question-style post",
                    "Relevant to content automation",
                    "No strict no-promo rule detected in playbook",
                ],
                "drafts": [
                    "Try batching by angle first (problem, proof, offer), then generate 3 variants per angle. That reduces random outputs.",
                    "Keep one fixed brief template so every variant is comparable on CTR and watch-time.",
                ],
            },
        ]

        for item in sample:
            conn.execute(
                """
                INSERT OR REPLACE INTO opportunities
                (id, account_id, platform, subreddit, title, body, url, score, status, reasons_json, drafts_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    DEFAULT_ACCOUNT_ID,
                    "reddit",
                    item["subreddit"],
                    item["title"],
                    item["body"],
                    item["url"],
                    item["score"],
                    item["status"],
                    json.dumps(item["reasons"]),
                    json.dumps(item["drafts"]),
                ),
            )

        playbooks = [
            ("saas", "No low-effort promotion. Be transparent. Add value first.", "Prefer tactical replies."),
            ("marketing", "No spam. Case studies and frameworks are welcome.", "Avoid hard CTA wording."),
        ]
        for subreddit, rules, notes in playbooks:
            conn.execute(
                """
                INSERT OR REPLACE INTO playbooks (account_id, subreddit, rules_text, notes, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (DEFAULT_ACCOUNT_ID, subreddit, rules, notes),
            )


def list_opportunities(
    status: str | None = None,
    platform: str | None = None,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> list[dict[str, Any]]:
    purge_expired_rejected_opportunities(account_id=account_id)
    query = """
        SELECT id, platform, subreddit, title, body, url, score, status, reasons_json, drafts_json, created_at,
               posted_reply_url, selected_draft_index, replied_at, followup_sentiment, clicks, signups,
               conversion_value, next_follow_up_at, operator_notes, feedback_label, feedback_note,
               campaign_name, product_area, updated_at
        FROM opportunities
    """
    where_parts: list[str] = []
    params_list: list[Any] = []
    where_parts.append("account_id = ?")
    params_list.append(account_id)
    if status:
        where_parts.append("status = ?")
        params_list.append(status)
    if platform:
        where_parts.append("platform = ?")
        params_list.append(platform)
    if where_parts:
        query += " WHERE " + " AND ".join(where_parts)
    params: tuple[Any, ...] = tuple(params_list)
    query += " ORDER BY created_at DESC, score DESC"

    with _conn() as conn:
        rows = conn.execute(query, params).fetchall()

    output = []
    for row in rows:
        output.append(
            {
                "id": row[0],
                "platform": row[1],
                "subreddit": row[2],
                "title": row[3],
                "body": row[4],
                "url": row[5],
                "score": row[6],
                "status": row[7],
                "reasons": json.loads(row[8]),
                "drafts": json.loads(row[9]),
                "created_at": row[10],
                "posted_reply_url": row[11],
                "selected_draft_index": row[12],
                "replied_at": row[13],
                "followup_sentiment": row[14],
                "clicks": row[15],
                "signups": row[16],
                "conversion_value": row[17],
                "next_follow_up_at": row[18],
                "operator_notes": row[19],
                "feedback_label": row[20],
                "feedback_note": row[21],
                "campaign_name": row[22],
                "product_area": row[23],
                "updated_at": row[24],
            }
        )
    return output


def purge_expired_rejected_opportunities(account_id: str | None = None) -> int:
    retention_hours = _rejected_retention_hours()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    cutoff_sqlite = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        if account_id:
            cursor = conn.execute(
                """
                DELETE FROM opportunities
                WHERE account_id = ? AND status = 'rejected' AND status_updated_at < ?
                """,
                (account_id, cutoff_sqlite),
            )
        else:
            cursor = conn.execute(
                """
                DELETE FROM opportunities
                WHERE status = 'rejected' AND status_updated_at < ?
                """,
                (cutoff_sqlite,),
            )
        return int(cursor.rowcount or 0)


def get_opportunity(opportunity_id: str, account_id: str = DEFAULT_ACCOUNT_ID) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT id, platform, subreddit, title, body, url, score, status, reasons_json, drafts_json, created_at,
                   posted_reply_url, selected_draft_index, replied_at, followup_sentiment, clicks, signups,
                   conversion_value, next_follow_up_at, operator_notes, feedback_label, feedback_note,
                   campaign_name, product_area, updated_at
            FROM opportunities
            WHERE id = ? AND account_id = ?
            """,
            (opportunity_id, account_id),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "platform": row[1],
        "subreddit": row[2],
        "title": row[3],
        "body": row[4],
        "url": row[5],
        "score": row[6],
        "status": row[7],
        "reasons": json.loads(row[8]),
        "drafts": json.loads(row[9]),
        "created_at": row[10],
        "posted_reply_url": row[11],
        "selected_draft_index": row[12],
        "replied_at": row[13],
        "followup_sentiment": row[14],
        "clicks": row[15],
        "signups": row[16],
        "conversion_value": row[17],
        "next_follow_up_at": row[18],
        "operator_notes": row[19],
        "feedback_label": row[20],
        "feedback_note": row[21],
        "campaign_name": row[22],
        "product_area": row[23],
        "updated_at": row[24],
    }


def list_playbooks(account_id: str = DEFAULT_ACCOUNT_ID) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT subreddit, rules_text, notes, updated_at FROM playbooks WHERE account_id = ? ORDER BY subreddit ASC",
            (account_id,),
        ).fetchall()
    return [
        {"subreddit": r[0], "rules_text": r[1], "notes": r[2], "updated_at": r[3]}
        for r in rows
    ]


def upsert_opportunity(
    opportunity_id: str,
    platform: str,
    subreddit: str,
    title: str,
    body: str,
    url: str,
    score: int,
    reasons: list[str],
    drafts: list[str],
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO opportunities
            (id, account_id, platform, subreddit, title, body, url, score, status, status_updated_at, reasons_json, drafts_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP, ?, ?)
            ON CONFLICT(account_id, id) DO UPDATE SET
                platform = excluded.platform,
                subreddit = excluded.subreddit,
                title = excluded.title,
                body = excluded.body,
                url = excluded.url,
                score = excluded.score,
                reasons_json = excluded.reasons_json,
                drafts_json = excluded.drafts_json,
                status = opportunities.status,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                opportunity_id,
                account_id,
                platform,
                subreddit,
                title,
                body,
                url,
                score,
                json.dumps(reasons),
                json.dumps(drafts),
            ),
        )


def upsert_playbook(subreddit: str, rules_text: str, account_id: str = DEFAULT_ACCOUNT_ID) -> None:
    normalized = (rules_text or "").strip()
    is_error_blob = normalized.lower().startswith("could not load rules:")

    with _conn() as conn:
        existing = conn.execute(
            "SELECT rules_text FROM playbooks WHERE subreddit = ? AND account_id = ?",
            (subreddit.lower(), account_id),
        ).fetchone()

        if is_error_blob or not normalized:
            if existing and (existing[0] or "").strip():
                return
            normalized = "Rules temporarily unavailable. Retry after network access is restored."

        conn.execute(
            """
            INSERT INTO playbooks (account_id, subreddit, rules_text, notes, updated_at)
            VALUES (?, ?, ?, '', CURRENT_TIMESTAMP)
            ON CONFLICT(account_id, subreddit) DO UPDATE SET
                rules_text = excluded.rules_text,
                updated_at = CURRENT_TIMESTAMP
            """,
            (account_id, subreddit.lower(), normalized),
        )


def update_status(opportunity_id: str, status: str, actor: str, note: str = "", account_id: str = DEFAULT_ACCOUNT_ID) -> None:
    if status not in PIPELINE_STAGES:
        raise ValueError(f"Unsupported status: {status}")
    with _conn() as conn:
        platform_row = conn.execute(
            "SELECT platform FROM opportunities WHERE id = ? AND account_id = ?",
            (opportunity_id, account_id),
        ).fetchone()
        platform = platform_row[0] if platform_row and platform_row[0] else "reddit"
        conn.execute(
            """
            UPDATE opportunities
            SET status = ?, status_updated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND account_id = ?
            """,
            (status, opportunity_id, account_id),
        )
        conn.execute(
            "INSERT INTO audit_log (account_id, platform, opportunity_id, action, actor, note) VALUES (?, ?, ?, ?, ?, ?)",
            (account_id, platform, opportunity_id, status, actor, note),
        )


def update_outcome(
    opportunity_id: str,
    actor: str,
    posted_reply_url: str = "",
    selected_draft_index: int | None = None,
    replied_at: str | None = None,
    followup_sentiment: str = "",
    clicks: int | None = None,
    signups: int | None = None,
    conversion_value: float | None = None,
    next_follow_up_at: str | None = None,
    operator_notes: str = "",
    status: str | None = None,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> None:
    if status and status not in PIPELINE_STAGES:
        raise ValueError(f"Unsupported status: {status}")
    with _conn() as conn:
        existing = conn.execute(
            "SELECT platform, status FROM opportunities WHERE id = ? AND account_id = ?",
            (opportunity_id, account_id),
        ).fetchone()
        if not existing:
            raise ValueError("Opportunity not found")
        platform = existing[0] or "reddit"
        next_status = status or existing[1]
        conn.execute(
            """
            UPDATE opportunities
            SET posted_reply_url = ?,
                selected_draft_index = ?,
                replied_at = ?,
                followup_sentiment = ?,
                clicks = COALESCE(?, clicks),
                signups = COALESCE(?, signups),
                conversion_value = COALESCE(?, conversion_value),
                next_follow_up_at = ?,
                operator_notes = ?,
                status = ?,
                status_updated_at = CASE WHEN status != ? THEN CURRENT_TIMESTAMP ELSE status_updated_at END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND account_id = ?
            """,
            (
                posted_reply_url,
                selected_draft_index,
                replied_at,
                followup_sentiment,
                clicks,
                signups,
                conversion_value,
                next_follow_up_at,
                operator_notes,
                next_status,
                next_status,
                opportunity_id,
                account_id,
            ),
        )
        conn.execute(
            "INSERT INTO audit_log (account_id, platform, opportunity_id, action, actor, note) VALUES (?, ?, ?, ?, ?, ?)",
            (account_id, platform, opportunity_id, "outcome_updated", actor, operator_notes),
        )


def update_feedback(opportunity_id: str, label: str, actor: str, note: str = "", account_id: str = DEFAULT_ACCOUNT_ID) -> None:
    with _conn() as conn:
        platform_row = conn.execute(
            "SELECT platform FROM opportunities WHERE id = ? AND account_id = ?",
            (opportunity_id, account_id),
        ).fetchone()
        if not platform_row:
            raise ValueError("Opportunity not found")
        platform = platform_row[0] or "reddit"
        conn.execute(
            """
            UPDATE opportunities
            SET feedback_label = ?, feedback_note = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND account_id = ?
            """,
            (label, note, opportunity_id, account_id),
        )
        conn.execute(
            "INSERT INTO audit_log (account_id, platform, opportunity_id, action, actor, note) VALUES (?, ?, ?, ?, ?, ?)",
            (account_id, platform, opportunity_id, f"feedback:{label}", actor, note),
        )


def reject_all_pending(actor: str, platform: str | None = None, account_id: str = DEFAULT_ACCOUNT_ID) -> int:
    with _conn() as conn:
        params: tuple[Any, ...] = (account_id,)
        query = "SELECT id FROM opportunities WHERE account_id = ? AND status IN ('new', 'qualified', 'drafted', 'pending')"
        if platform:
            query += " AND platform = ?"
            params = (account_id, platform)
        rows = conn.execute(query, params).fetchall()
        if not rows:
            return 0
        ids = [r[0] for r in rows]
        if platform:
            conn.execute(
                "UPDATE opportunities SET status = 'rejected', status_updated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE account_id = ? AND status IN ('new', 'qualified', 'drafted', 'pending') AND platform = ?",
                (account_id, platform),
            )
        else:
            conn.execute(
                "UPDATE opportunities SET status = 'rejected', status_updated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE account_id = ? AND status IN ('new', 'qualified', 'drafted', 'pending')",
                (account_id,),
            )
        audit_data = [(account_id, platform or "reddit", opp_id, 'rejected', actor, 'Bulk discarded') for opp_id in ids]
        conn.executemany(
            "INSERT INTO audit_log (account_id, platform, opportunity_id, action, actor, note) VALUES (?, ?, ?, ?, ?, ?)",
            audit_data
        )
        return len(ids)


def list_audit(platform: str | None = None, account_id: str = DEFAULT_ACCOUNT_ID) -> list[dict[str, Any]]:
    with _conn() as conn:
        if platform:
            rows = conn.execute(
                """
                SELECT id, platform, opportunity_id, action, actor, note, created_at
                FROM audit_log
                WHERE account_id = ? AND platform = ?
                ORDER BY id DESC
                LIMIT 100
                """,
                (account_id, platform),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, platform, opportunity_id, action, actor, note, created_at
                FROM audit_log
                WHERE account_id = ?
                ORDER BY id DESC
                LIMIT 100
                """,
                (account_id,),
            ).fetchall()
    return [
        {
            "id": row[0],
            "platform": row[1],
            "opportunity_id": row[2],
            "action": row[3],
            "actor": row[4],
            "note": row[5],
            "created_at": row[6],
        }
        for row in rows
    ]


def analytics(platform: str | None = None, account_id: str = DEFAULT_ACCOUNT_ID) -> dict[str, Any]:
    rows = list_opportunities(platform=platform, account_id=account_id)
    stage_counts = Counter(row["status"] for row in rows)
    total = len(rows)
    approved = stage_counts["approved"] + stage_counts["posted"] + stage_counts["replied_back"] + stage_counts["converted"]
    posted = stage_counts["posted"] + stage_counts["replied_back"] + stage_counts["converted"]
    replied = stage_counts["replied_back"] + stage_counts["converted"]
    converted = stage_counts["converted"]

    by_channel: dict[str, int] = defaultdict(int)
    by_product_area: dict[str, int] = defaultdict(int)
    by_feedback: dict[str, int] = defaultdict(int)
    by_day: dict[str, int] = defaultdict(int)
    pipeline_value = 0.0
    clicks = 0
    signups = 0
    for row in rows:
        by_channel[row["subreddit"]] += 1
        if row.get("product_area"):
            by_product_area[row["product_area"]] += 1
        if row.get("feedback_label"):
            by_feedback[row["feedback_label"]] += 1
        if row.get("created_at"):
            by_day[str(row["created_at"])[:10]] += 1
        pipeline_value += float(row.get("conversion_value") or 0)
        clicks += int(row.get("clicks") or 0)
        signups += int(row.get("signups") or 0)

    def rate(part: int) -> float:
        return round((part / total) * 100, 1) if total else 0.0

    return {
        "total": total,
        "stage_counts": dict(stage_counts),
        "approval_rate": rate(approved),
        "posted_rate": rate(posted),
        "reply_rate": rate(replied),
        "conversion_rate": rate(converted),
        "clicks": clicks,
        "signups": signups,
        "pipeline_value": round(pipeline_value, 2),
        "estimated_time_saved_minutes": posted * 8 + approved * 3,
        "best_channels": sorted(by_channel.items(), key=lambda item: item[1], reverse=True)[:8],
        "best_product_areas": sorted(by_product_area.items(), key=lambda item: item[1], reverse=True)[:8],
        "feedback": dict(by_feedback),
        "opportunities_by_day": dict(sorted(by_day.items())),
    }
