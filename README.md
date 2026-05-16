# The Gatekeeper Social Listening Assistant

Compliance-first assistant that:
- Monitors selected subreddits for relevant discussions
- Searches X/Twitter and YouTube when enabled
- Pulls subreddit rules and community context
- Qualifies content against each account's campaign knowledge
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
- `GOOGLE_API_KEY` and `GOOGLE_MODEL` for stronger draft quality (default: `gemma-3-27b-it`)

Optional:
- `EARLY_REPLY_WINDOW_MINUTES` for freshness scoring boost (default: `90`)
- `TWITTER_RELEVANCE_MIN_SCORE` for X/Twitter semantic filtering (default: `25`)
- `YOUTUBE_API_KEY` and `YOUTUBE_ENABLED=1` to enable YouTube comment discovery
- `YOUTUBE_MAX_SEARCH_QUERIES`, `YOUTUBE_MAX_VIDEOS`, and `YOUTUBE_MAX_COMMENTS_PER_VIDEO` to control YouTube Data API quota usage

Audience targeting is configured per account in the review UI, not in `.env`.
Use Configuration -> Bot Profile to edit target subreddits, Reddit discovery signals, Twitter handles, Twitter queries, YouTube channels, YouTube queries, knowledge blocks, and prompt templates for the active account.

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
- Draft generation uses the active account's campaign knowledge and defaults to solve-first, subtle-mention behavior
