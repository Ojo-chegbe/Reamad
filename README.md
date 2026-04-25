# Soloa Reddit Assistant (PRAW)

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
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`
- `REDDIT_USER_AGENT` (unique, descriptive)
- `TARGET_SUBREDDITS` (comma-separated)
- `KEYWORDS` (comma-separated)

Optional:
- `OPENAI_API_KEY` and `OPENAI_MODEL` for stronger draft quality

## 2) Run

```bash
python -m src.main
```

The app polls at intervals, prints opportunities, and suggests 2-3 comments per item.
Keep posting manual to stay within subreddit norms and Reddit policy.

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

- Uses official Reddit API via PRAW (OAuth)
- Stores lightweight state in SQLite (`bot_state.db`)
- Deletes are handled by refreshing source data each cycle; do not build long-term retention of deleted content
