from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database.models import ApiUsage
from backend.app.utils.errors import SourceRestrictionError

ISO_COUNTRY_MAP = {
    "US": "United States",
    "USA": "United States",
    "CA": "Canada",
    "CAN": "Canada",
    "GB": "United Kingdom",
    "GBR": "United Kingdom",
    "UK": "United Kingdom",
    "IE": "Ireland",
    "IRL": "Ireland",
    "AU": "Australia",
    "AUS": "Australia",
    "NZ": "New Zealand",
    "NZL": "New Zealand",
    "SG": "Singapore",
    "SGP": "Singapore",
    "IN": "India",
    "IND": "India",
    "DE": "Germany",
    "DEU": "Germany",
    "NL": "Netherlands",
    "NLD": "Netherlands",
}


def parse_iso8601_duration(duration_str: str | None) -> int:
    """Convert YouTube ISO-8601 duration (e.g. PT1H24M10S) into total seconds."""
    if not duration_str:
        return 0
    match = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", duration_str.strip())
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


class YouTubeAPICollector:
    """Official YouTube Data API v3 adapter with pagination, deduplication, quota/error handling, and usage logging."""

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: str | None = None, http_client: httpx.Client | None = None):
        self.settings = get_settings()
        self.api_key = (api_key if api_key is not None else self.settings.youtube_api_key).strip()
        self._client = http_client

    def _log_usage(
        self,
        db: Session | None,
        endpoint: str,
        operation: str,
        units: int,
        status_code: int,
        success: bool,
        latency_ms: float,
        error_detail: str | None = None,
    ) -> None:
        if db is None:
            return
        db.add(
            ApiUsage(
                provider="youtube_data_api_v3",
                endpoint=endpoint,
                operation=operation,
                units_or_tokens=units,
                estimated_cost_usd=0.0,
                status_code=status_code,
                success=success,
                latency_ms=round(latency_ms, 2),
                error_detail=error_detail,
            )
        )
        db.flush()

    def discover_candidates(
        self,
        db: Session | None,
        keyword: str,
        max_candidates: int = 25,
        category: str = "YouTuber / Video-First Creator",
        export_dir: Path | None = None,
    ) -> list[dict[str, Any]]:
        if not self.api_key:
            self._log_usage(
                db,
                endpoint="/search",
                operation="search_channels",
                units=0,
                status_code=401,
                success=False,
                latency_ms=0.0,
                error_detail="YOUTUBE_API_KEY is not configured in environment.",
            )
            raise SourceRestrictionError(
                message="YouTube Data API v3 key (YOUTUBE_API_KEY) is missing. Configure YOUTUBE_API_KEY in .env or use Podcast RSS / Synthetic Demo mode.",
                source="youtube_data_api_v3",
                restriction_type="MISSING_CREDENTIALS",
            )

        close_client = False
        client = self._client
        if client is None:
            client = httpx.Client(timeout=15.0)
            close_client = True

        try:
            channel_ids: list[str] = []
            seen_ids: set[str] = set()
            next_page_token: str | None = None

            while len(channel_ids) < max_candidates:
                batch_size = min(50, max_candidates - len(channel_ids))
                params: dict[str, Any] = {
                    "part": "snippet",
                    "q": keyword,
                    "type": "channel",
                    "maxResults": batch_size,
                    "key": self.api_key,
                }
                if next_page_token:
                    params["pageToken"] = next_page_token

                start = time.perf_counter()
                try:
                    resp = client.get(f"{self.BASE_URL}/search", params=params)
                except httpx.TimeoutException as exc:
                    latency = (time.perf_counter() - start) * 1000.0
                    self._log_usage(db, "/search", "search_channels", 100, 408, False, latency, str(exc))
                    raise SourceRestrictionError(
                        message=f"YouTube API request timed out while searching keyword '{keyword}'.",
                        source="youtube_data_api_v3",
                        restriction_type="TIMEOUT",
                    ) from exc

                latency = (time.perf_counter() - start) * 1000.0
                if resp.status_code != 200:
                    err_text = resp.text[:400]
                    self._log_usage(db, "/search", "search_channels", 100, resp.status_code, False, latency, err_text)
                    if resp.status_code in (400, 401):
                        raise SourceRestrictionError(
                            message="Invalid YouTube API key provided.",
                            source="youtube_data_api_v3",
                            restriction_type="INVALID_API_KEY",
                            details={"status_code": resp.status_code, "body": err_text},
                        )
                    if resp.status_code == 403 and "quotaExceeded" in err_text:
                        raise SourceRestrictionError(
                            message="YouTube Data API v3 daily quota exceeded.",
                            source="youtube_data_api_v3",
                            restriction_type="QUOTA_EXCEEDED",
                            details={"status_code": 403},
                        )
                    raise SourceRestrictionError(
                        message=f"YouTube API error ({resp.status_code}): {err_text}",
                        source="youtube_data_api_v3",
                        restriction_type="API_ERROR",
                    )

                self._log_usage(db, "/search", "search_channels", 100, 200, True, latency)
                payload = resp.json()
                items = payload.get("items", [])
                if not items:
                    break

                for item in items:
                    cid = (
                        item.get("id", {}).get("channelId")
                        or item.get("snippet", {}).get("channelId")
                        or ""
                    ).strip()
                    if cid and cid.startswith("UC") and cid not in seen_ids:
                        seen_ids.add(cid)
                        channel_ids.append(cid)

                next_page_token = payload.get("nextPageToken")
                if not next_page_token:
                    break

            if not channel_ids:
                return []

            candidates = self._fetch_channels_and_videos(db, client, channel_ids, category)
            if export_dir:
                export_dir.mkdir(parents=True, exist_ok=True)
                out_file = export_dir / f"youtube_candidates_{int(time.time())}.json"
                out_file.write_text(json.dumps(candidates, indent=2, default=str), encoding="utf-8")
            return candidates
        finally:
            if close_client and client is not None:
                client.close()

    def _fetch_channels_and_videos(
        self,
        db: Session | None,
        client: httpx.Client,
        channel_ids: list[str],
        category: str,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for idx in range(0, len(channel_ids), 50):
            chunk = channel_ids[idx : idx + 50]
            start = time.perf_counter()
            resp = client.get(
                f"{self.BASE_URL}/channels",
                params={
                    "part": "snippet,contentDetails,statistics",
                    "id": ",".join(chunk),
                    "key": self.api_key,
                },
            )
            latency = (time.perf_counter() - start) * 1000.0
            if resp.status_code != 200:
                self._log_usage(db, "/channels", "fetch_channel_details", 1, resp.status_code, False, latency, resp.text[:300])
                continue
            self._log_usage(db, "/channels", "fetch_channel_details", 1, 200, True, latency)

            for ch in resp.json().get("items", []):
                cid = ch.get("id", "")
                if not cid:
                    continue
                snippet = ch.get("snippet", {})
                stats = ch.get("statistics", {})
                uploads_playlist = (
                    ch.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
                )
                raw_country = snippet.get("country", "").upper()
                country = ISO_COUNTRY_MAP.get(raw_country, raw_country if raw_country else "UNKNOWN")
                custom_url = snippet.get("customUrl", "")
                official_url = f"https://www.youtube.com/channel/{cid}"

                recent_videos = []
                if uploads_playlist:
                    recent_videos = self._fetch_playlist_videos(db, client, uploads_playlist)

                results.append(
                    {
                        "platform": "youtube",
                        "platform_id": cid,
                        "name": snippet.get("title", "Unknown Creator"),
                        "handle": custom_url or f"@{cid[:10]}",
                        "official_url": official_url,
                        "category": category,
                        "country": country,
                        "language": snippet.get("defaultLanguage") or snippet.get("defaultAudioLanguage") or "en",
                        "description": snippet.get("description", ""),
                        "subscriber_count": int(stats.get("subscriberCount", 0) or 0),
                        "total_views": int(stats.get("viewCount", 0) or 0),
                        "total_content_count": int(stats.get("videoCount", 0) or 0),
                        "uploads_playlist_id": uploads_playlist,
                        "discovery_source": "youtube_api",
                        "is_synthetic": False,
                        "content_items": recent_videos,
                    }
                )
        return results

    def _fetch_playlist_videos(
        self,
        db: Session | None,
        client: httpx.Client,
        playlist_id: str,
        max_items: int = 12,
    ) -> list[dict[str, Any]]:
        start = time.perf_counter()
        resp = client.get(
            f"{self.BASE_URL}/playlistItems",
            params={
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": max_items,
                "key": self.api_key,
            },
        )
        latency = (time.perf_counter() - start) * 1000.0
        if resp.status_code != 200:
            self._log_usage(db, "/playlistItems", "fetch_uploads", 1, resp.status_code, False, latency, resp.text[:250])
            return []
        self._log_usage(db, "/playlistItems", "fetch_uploads", 1, 200, True, latency)

        video_ids: list[str] = []
        basic_map: dict[str, dict[str, Any]] = {}
        for item in resp.json().get("items", []):
            vid = item.get("contentDetails", {}).get("videoId") or item.get("snippet", {}).get("resourceId", {}).get("videoId")
            if not vid:
                continue
            video_ids.append(vid)
            basic_map[vid] = item.get("snippet", {})

        if not video_ids:
            return []

        v_start = time.perf_counter()
        v_resp = client.get(
            f"{self.BASE_URL}/videos",
            params={
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(video_ids),
                "key": self.api_key,
            },
        )
        v_latency = (time.perf_counter() - v_start) * 1000.0
        durations: dict[str, int] = {}
        views_map: dict[str, int] = {}
        lang_map: dict[str, str] = {}
        if v_resp.status_code == 200:
            self._log_usage(db, "/videos", "fetch_video_details", 1, 200, True, v_latency)
            for v_item in v_resp.json().get("items", []):
                vid = v_item.get("id", "")
                dur_iso = v_item.get("contentDetails", {}).get("duration")
                durations[vid] = parse_iso8601_duration(dur_iso)
                views_map[vid] = int(v_item.get("statistics", {}).get("viewCount", 0) or 0)
                v_snip = v_item.get("snippet", {})
                lang_map[vid] = v_snip.get("defaultAudioLanguage") or v_snip.get("defaultLanguage") or "en"
        else:
            self._log_usage(db, "/videos", "fetch_video_details", 1, v_resp.status_code, False, v_latency, v_resp.text[:250])

        videos: list[dict[str, Any]] = []
        for vid in video_ids:
            snip = basic_map[vid]
            pub_raw = snip.get("publishedAt")
            try:
                pub_dt = datetime.fromisoformat(pub_raw.replace("Z", "+00:00")) if pub_raw else datetime.now(timezone.utc)
            except ValueError:
                pub_dt = datetime.now(timezone.utc)
            dur_sec = durations.get(vid, 0)
            videos.append(
                {
                    "external_id": vid,
                    "title": snip.get("title", "Untitled Video"),
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "content_type": "video",
                    "published_at": pub_dt,
                    "duration_seconds": dur_sec,
                    "is_longform": dur_sec >= 600,
                    "description": snip.get("description", ""),
                    "language": lang_map.get(vid, "en"),
                    "view_count": views_map.get(vid, 0),
                }
            )
        return videos

    @staticmethod
    def fetch_public_channel_rss(channel_id: str, timeout: float = 10.0) -> list[dict[str, Any]]:
        """Permitted public YouTube XML feed for a known stable channel ID."""
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(feed_url)
            if resp.status_code != 200:
                return []
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
            items: list[dict[str, Any]] = []
            for entry in root.findall("atom:entry", ns):
                vid_el = entry.find("yt:videoId", ns)
                title_el = entry.find("atom:title", ns)
                pub_el = entry.find("atom:published", ns)
                if vid_el is None or not vid_el.text:
                    continue
                vid = vid_el.text.strip()
                pub_dt = datetime.now(timezone.utc)
                if pub_el is not None and pub_el.text:
                    try:
                        pub_dt = datetime.fromisoformat(pub_el.text.replace("Z", "+00:00"))
                    except ValueError:
                        pass
                items.append(
                    {
                        "external_id": vid,
                        "title": title_el.text.strip() if title_el is not None and title_el.text else "Video",
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "content_type": "video",
                        "published_at": pub_dt,
                        "duration_seconds": 900,
                        "is_longform": True,
                        "description": "",
                        "language": "en",
                    }
                )
            return items
