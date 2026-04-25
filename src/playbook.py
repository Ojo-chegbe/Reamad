from __future__ import annotations

import praw

from src.store import Store


def refresh_subreddit_rules(reddit: praw.Reddit, store: Store, subreddits: list[str]) -> None:
    for sub_name in subreddits:
        subreddit = reddit.subreddit(sub_name)
        lines: list[str] = []
        try:
            for rule in subreddit.rules:
                short = getattr(rule, "short_name", "") or ""
                desc = getattr(rule, "description", "") or ""
                if short and desc:
                    lines.append(f"{short}: {desc}")
                elif short:
                    lines.append(short)
                elif desc:
                    lines.append(desc)
        except Exception as exc:
            lines.append(f"Could not load rules: {exc}")

        store.upsert_rules(sub_name, "\n".join(lines).strip())

