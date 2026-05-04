# Soloa Reddit Assistant (JSON endpoints)

Compliance-first assistant that:
- Monitors selected subreddits for relevant discussions
- Pulls subreddit rules and community context
- Scores post fit for engagement
- Generates suggested comment drafts for manual approval

## 1) Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill `.env` values:
- `REDDIT_USER_AGENT` (required, unique, descriptive)
- `TARGET_SUBREDDITS` (comma-separated, optional if `PAIN_SUBREDDITS` is set)
- `KEYWORDS` (comma-separated, optional if `PAIN_KEYWORDS` is set)

Optional:
- `GOOGLE_API_KEY` and `GOOGLE_MODEL` for stronger draft quality (default: `gemma-3-27b-it`)
- `PAIN_SUBREDDITS` for pain-heavy communities (creator, marketing, productivity, indie)
- `PAIN_KEYWORDS` for frustration signals (for example "this is taking too long")
- `EARLY_REPLY_WINDOW_MINUTES` for freshness scoring boost (default: `90`)

## 2) Run

```bash
python -m src.main
```

The app polls at intervals, prints opportunities, and suggests 2-3 comments per item.
Keep posting manual to stay within subreddit norms and Reddit policy.
Scoring is pain-first and time-sensitive: workflow frustration language and fresh threads are prioritized.

## 3) Review UI (for API submission demos)

This repo includes a human-in-the-loop review console so reviewers can see:
- Opportunities are reviewed before posting
- Approve/reject decisions are tracked
- Subreddit playbooks and audit logs exist

Run:

```bash
python -m ui.app
```

Then open `http://127.0.0.1:5050`.

## 4) Notes

- Uses Reddit's public `.json` endpoints (`/new.json`, `/about/rules.json`) for read-only monitoring
- No OAuth API keys required for read-only monitoring
- Stores lightweight state in SQLite (`bot_state.db`)
- Deletes are handled by refreshing source data each cycle; do not build long-term retention of deleted content
- Draft generation includes a Soloa knowledge profile and defaults to solve-first, subtle-mention behavior
