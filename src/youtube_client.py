from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests


@dataclass(frozen=True)
class YouTubeVideo:
    video_id: str
    title: str
    description: str
    channel_id: str
    channel_title: str
    published_at: str


@dataclass(frozen=True)
class YouTubeComment:
    comment_id: str
    video_id: str
    video_title: str
    channel_title: str
    author_display_name: str
    text: str
    like_count: int
    published_at: str
    permalink: str
    created_at_ts: float


class YouTubeClient:
    def __init__(self, api_key: str, timeout_seconds: int = 20) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://www.googleapis.com/youtube/v3"

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/{path}",
            params={**params, "key": self.api_key},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("YouTube API returned a non-object response")
        return data

    def search_videos(
        self,
        query: str,
        max_results: int,
        published_after: str | None = None,
    ) -> list[YouTubeVideo]:
        params: dict[str, Any] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "date",
            "maxResults": max(1, min(50, max_results)),
            "safeSearch": "moderate",
        }
        if published_after:
            params["publishedAfter"] = published_after
        data = self._get("search", params)
        videos: list[YouTubeVideo] = []
        for item in data.get("items", []):
            if not isinstance(item, dict):
                continue
            video_id = ((item.get("id") or {}).get("videoId") or "").strip()
            snippet = item.get("snippet") or {}
            if not video_id or not isinstance(snippet, dict):
                continue
            videos.append(
                YouTubeVideo(
                    video_id=video_id,
                    title=str(snippet.get("title", "") or "").strip(),
                    description=str(snippet.get("description", "") or "").strip(),
                    channel_id=str(snippet.get("channelId", "") or "").strip(),
                    channel_title=str(snippet.get("channelTitle", "") or "").strip(),
                    published_at=str(snippet.get("publishedAt", "") or "").strip(),
                )
            )
        return videos

    def list_video_comments(
        self,
        video: YouTubeVideo,
        max_results: int,
        search_terms: str | None = None,
    ) -> list[YouTubeComment]:
        params: dict[str, Any] = {
            "part": "snippet",
            "videoId": video.video_id,
            "order": "time",
            "textFormat": "plainText",
            "maxResults": max(1, min(100, max_results)),
        }
        if search_terms:
            params["searchTerms"] = search_terms[:500]
        data = self._get("commentThreads", params)
        comments: list[YouTubeComment] = []
        for item in data.get("items", []):
            if not isinstance(item, dict):
                continue
            snippet = item.get("snippet") or {}
            top_level = (snippet.get("topLevelComment") or {}) if isinstance(snippet, dict) else {}
            comment_snippet = top_level.get("snippet") or {}
            comment_id = str(top_level.get("id", "") or item.get("id", "") or "").strip()
            text = str(comment_snippet.get("textDisplay", "") or comment_snippet.get("textOriginal", "") or "").strip()
            if not comment_id or not text:
                continue
            published_at = str(comment_snippet.get("publishedAt", "") or "").strip()
            comments.append(
                YouTubeComment(
                    comment_id=comment_id,
                    video_id=video.video_id,
                    video_title=video.title,
                    channel_title=video.channel_title,
                    author_display_name=str(comment_snippet.get("authorDisplayName", "") or "").strip(),
                    text=text,
                    like_count=int(comment_snippet.get("likeCount", 0) or 0),
                    published_at=published_at,
                    permalink=f"https://www.youtube.com/watch?v={video.video_id}&lc={comment_id}",
                    created_at_ts=_parse_youtube_time(published_at),
                )
            )
        return comments


def _parse_youtube_time(value: str) -> float:
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return 0.0
