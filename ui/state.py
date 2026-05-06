from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DB_PATH = Path("ui_state.db")
DEFAULT_REJECTED_RETENTION_HOURS = 24


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


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
        if "platform" not in audit_column_names:
            conn.execute("ALTER TABLE audit_log ADD COLUMN platform TEXT")
        conn.execute("UPDATE audit_log SET platform = 'reddit' WHERE platform IS NULL OR platform = ''")


def seed_if_empty() -> None:
    if os.getenv("UI_SEED_DEMO", "").strip() != "1":
        return

    with _conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()
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
                (id, platform, subreddit, title, body, url, score, status, reasons_json, drafts_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
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
                INSERT OR REPLACE INTO playbooks (subreddit, rules_text, notes, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (subreddit, rules, notes),
            )


def list_opportunities(status: str | None = None, platform: str | None = None) -> list[dict[str, Any]]:
    purge_expired_rejected_opportunities()
    query = """
        SELECT id, platform, subreddit, title, body, url, score, status, reasons_json, drafts_json, created_at
        FROM opportunities
    """
    where_parts: list[str] = []
    params_list: list[Any] = []
    if status:
        where_parts.append("status = ?")
        params_list.append(status)
    if platform:
        where_parts.append("platform = ?")
        params_list.append(platform)
    if where_parts:
        query += " WHERE " + " AND ".join(where_parts)
    params: tuple[Any, ...] = tuple(params_list)
    query += " ORDER BY score DESC, created_at DESC"

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
            }
        )
    return output


def purge_expired_rejected_opportunities() -> int:
    retention_hours = _rejected_retention_hours()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    cutoff_sqlite = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        cursor = conn.execute(
            """
            DELETE FROM opportunities
            WHERE status = 'rejected' AND status_updated_at < ?
            """,
            (cutoff_sqlite,),
        )
        return int(cursor.rowcount or 0)


def get_opportunity(opportunity_id: str) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT id, platform, subreddit, title, body, url, score, status, reasons_json, drafts_json, created_at
            FROM opportunities
            WHERE id = ?
            """,
            (opportunity_id,),
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
    }


def list_playbooks() -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT subreddit, rules_text, notes, updated_at FROM playbooks ORDER BY subreddit ASC"
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
) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO opportunities
            (id, platform, subreddit, title, body, url, score, status, status_updated_at, reasons_json, drafts_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                platform = excluded.platform,
                subreddit = excluded.subreddit,
                title = excluded.title,
                body = excluded.body,
                url = excluded.url,
                score = excluded.score,
                reasons_json = excluded.reasons_json,
                drafts_json = excluded.drafts_json,
                status = opportunities.status
            """,
            (
                opportunity_id,
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


def upsert_playbook(subreddit: str, rules_text: str) -> None:
    normalized = (rules_text or "").strip()
    is_error_blob = normalized.lower().startswith("could not load rules:")

    with _conn() as conn:
        existing = conn.execute(
            "SELECT rules_text FROM playbooks WHERE subreddit = ?",
            (subreddit.lower(),),
        ).fetchone()

        if is_error_blob or not normalized:
            if existing and (existing[0] or "").strip():
                return
            normalized = "Rules temporarily unavailable. Retry after network access is restored."

        conn.execute(
            """
            INSERT INTO playbooks (subreddit, rules_text, notes, updated_at)
            VALUES (?, ?, '', CURRENT_TIMESTAMP)
            ON CONFLICT(subreddit) DO UPDATE SET
                rules_text = excluded.rules_text,
                updated_at = CURRENT_TIMESTAMP
            """,
            (subreddit.lower(), normalized),
        )


def update_status(opportunity_id: str, status: str, actor: str, note: str = "") -> None:
    with _conn() as conn:
        platform_row = conn.execute(
            "SELECT platform FROM opportunities WHERE id = ?",
            (opportunity_id,),
        ).fetchone()
        platform = platform_row[0] if platform_row and platform_row[0] else "reddit"
        conn.execute(
            "UPDATE opportunities SET status = ?, status_updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, opportunity_id),
        )
        conn.execute(
            "INSERT INTO audit_log (platform, opportunity_id, action, actor, note) VALUES (?, ?, ?, ?, ?)",
            (platform, opportunity_id, status, actor, note),
        )


def reject_all_pending(actor: str, platform: str | None = None) -> int:
    with _conn() as conn:
        params: tuple[Any, ...] = ()
        query = "SELECT id FROM opportunities WHERE status = 'pending'"
        if platform:
            query += " AND platform = ?"
            params = (platform,)
        rows = conn.execute(query, params).fetchall()
        if not rows:
            return 0
        ids = [r[0] for r in rows]
        if platform:
            conn.execute(
                "UPDATE opportunities SET status = 'rejected', status_updated_at = CURRENT_TIMESTAMP WHERE status = 'pending' AND platform = ?",
                (platform,),
            )
        else:
            conn.execute(
                "UPDATE opportunities SET status = 'rejected', status_updated_at = CURRENT_TIMESTAMP WHERE status = 'pending'"
            )
        audit_data = [(platform or "reddit", opp_id, 'rejected', actor, 'Bulk discarded') for opp_id in ids]
        conn.executemany(
            "INSERT INTO audit_log (platform, opportunity_id, action, actor, note) VALUES (?, ?, ?, ?, ?)",
            audit_data
        )
        return len(ids)


def list_audit(platform: str | None = None) -> list[dict[str, Any]]:
    with _conn() as conn:
        if platform:
            rows = conn.execute(
                """
                SELECT id, platform, opportunity_id, action, actor, note, created_at
                FROM audit_log
                WHERE platform = ?
                ORDER BY id DESC
                LIMIT 100
                """,
                (platform,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, platform, opportunity_id, action, actor, note, created_at
                FROM audit_log
                ORDER BY id DESC
                LIMIT 100
                """
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
