from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


DB_PATH = Path("ui_state.db")


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY,
                subreddit TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                url TEXT NOT NULL,
                score INTEGER NOT NULL,
                status TEXT NOT NULL,
                reasons_json TEXT NOT NULL,
                drafts_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
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
                opportunity_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def seed_if_empty() -> None:
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
                (id, subreddit, title, body, url, score, status, reasons_json, drafts_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
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


def list_opportunities(status: str | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT id, subreddit, title, body, url, score, status, reasons_json, drafts_json, created_at
        FROM opportunities
    """
    params: tuple[Any, ...] = ()
    if status:
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY score DESC, created_at DESC"

    with _conn() as conn:
        rows = conn.execute(query, params).fetchall()

    output = []
    for row in rows:
        output.append(
            {
                "id": row[0],
                "subreddit": row[1],
                "title": row[2],
                "body": row[3],
                "url": row[4],
                "score": row[5],
                "status": row[6],
                "reasons": json.loads(row[7]),
                "drafts": json.loads(row[8]),
                "created_at": row[9],
            }
        )
    return output


def get_opportunity(opportunity_id: str) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT id, subreddit, title, body, url, score, status, reasons_json, drafts_json, created_at
            FROM opportunities
            WHERE id = ?
            """,
            (opportunity_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "subreddit": row[1],
        "title": row[2],
        "body": row[3],
        "url": row[4],
        "score": row[5],
        "status": row[6],
        "reasons": json.loads(row[7]),
        "drafts": json.loads(row[8]),
        "created_at": row[9],
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


def update_status(opportunity_id: str, status: str, actor: str, note: str = "") -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE opportunities SET status = ? WHERE id = ?",
            (status, opportunity_id),
        )
        conn.execute(
            "INSERT INTO audit_log (opportunity_id, action, actor, note) VALUES (?, ?, ?, ?)",
            (opportunity_id, status, actor, note),
        )


def list_audit() -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, opportunity_id, action, actor, note, created_at
            FROM audit_log
            ORDER BY id DESC
            LIMIT 100
            """
        ).fetchall()
    return [
        {
            "id": row[0],
            "opportunity_id": row[1],
            "action": row[2],
            "actor": row[3],
            "note": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]

