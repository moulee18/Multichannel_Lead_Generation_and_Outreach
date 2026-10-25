from __future__ import annotations

import email.utils
import html
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from backend.app.database.models import ApiUsage
from backend.app.integrations.youtube_api import ISO_COUNTRY_MAP
from backend.app.utils.errors import SourceRestrictionError


def parse_rss_duration(raw: str | None) -> int:
    if not raw:
        return 1800
    cleaned = raw.strip()
    if cleaned.isdigit():
        val = int(cleaned)
        if 0 < val <= 120:
            return val * 60
        return max(600, val)
    parts = [p for p in cleaned.split(":") if p.strip().isdigit()]
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 1800


def clean_rss_html_preserving_links(raw_html: str | None) -> str:
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    # Preserve href links so contact extractor can see LinkedIn/Instagram/X/Email links in show notes
    text = re.sub(
        r'<a\s+[^>]*href=["\'](https?://[^"\'>\s]+|mailto:[^"\'>\s]+)["\'][^>]*>(.*?)</a>',
        r"\2 (\1) ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def infer_creator_category(title: str, description: str, genre: str, keyword: str = "") -> str:
    blob = f"{title} {description} {genre} {keyword}".lower()
    if any(
        w in blob
        for w in (
            "coach",
            "consultant",
            "consulting",
            "educator",
            "education",
            "course",
            "academy",
            "training",
            "masterclass",
            "leadership",
            "advisor",
            "mentor",
        )
    ):
        return "Expert-Led Creator (Coach / Consultant / Educator)"
    if any(w in blob for w in ("video podcast", "youtube", "video show", "vodcast", "visual")):
        return "YouTuber / Video-First Creator"
    return "Podcaster / Video Podcaster"


def parse_rss_xml_bytes(raw_bytes: bytes, feed_url: str) -> dict[str, Any] | None:
    raw_text = raw_bytes.decode("utf-8", errors="ignore").strip()
    if not raw_text:
        return None

    if "</rss>" not in raw_text and "</feed>" not in raw_text:
        last_item_idx = raw_text.rfind("</item>")
        if last_item_idx != -1:
            raw_text = raw_text[: last_item_idx + len("</item>")] + "</channel></rss>"
        else:
            return None

    try:
        root = ET.fromstring(raw_text)
    except ET.ParseError:
        # Attempt cleanup of invalid XML control chars
        cleaned_xml = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw_text)
        last_item_idx = cleaned_xml.rfind("</item>")
        if last_item_idx != -1 and "</rss>" not in cleaned_xml:
            cleaned_xml = cleaned_xml[: last_item_idx + len("</item>")] + "</channel></rss>"
        try:
            root = ET.fromstring(cleaned_xml)
        except Exception:
            return None

    channel = root.find("channel")
    if channel is None:
        return None

    title = (channel.findtext("title") or "").strip()
    raw_desc = channel.findtext("description") or ""
    itunes_summary = ""
    owner_email = None
    author = ""

    for elem in channel:
        tag_lower = elem.tag.lower()
        if tag_lower.endswith("summary") and elem.text:
            itunes_summary = elem.text
        elif tag_lower.endswith("author") and elem.text and not author:
            author = elem.text.strip()
        elif tag_lower.endswith("owner"):
            for sub in elem:
                if sub.tag.lower().endswith("email") and sub.text and "@" in sub.text:
                    owner_email = sub.text.strip()
        elif tag_lower.endswith("email") and elem.text and "@" in elem.text and not owner_email:
            owner_email = elem.text.strip()

    description = clean_rss_html_preserving_links(f"{raw_desc} {itunes_summary}")
    link = (channel.findtext("link") or feed_url).strip()
    raw_lang = (channel.findtext("language") or "en").strip().lower()
    language = "en" if (not raw_lang or raw_lang.startswith("en") or raw_lang == "und") else raw_lang[:8]

    if not owner_email:
        match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", description)
        if match:
            owner_email = match.group(0).rstrip(".,;)")

    episodes: list[dict[str, Any]] = []
    for item in channel.findall("item")[:12]:
        ep_title = (item.findtext("title") or "Episode").strip()
        ep_link = (item.findtext("link") or link or feed_url).strip()
        ep_guid = (item.findtext("guid") or ep_link or ep_title)[:120]
        ep_raw_desc = item.findtext("description") or ""
        ep_encoded = ""
        dur_raw = None
        for child in item:
            ctag = child.tag.lower()
            if ctag.endswith("duration") and child.text:
                dur_raw = child.text
            elif ctag.endswith("encoded") and child.text:
                ep_encoded = child.text[:2500]
        ep_desc = clean_rss_html_preserving_links(f"{ep_raw_desc} {ep_encoded}")

        if not owner_email:
            match_ep = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", ep_desc)
            if match_ep:
                cand_email = match_ep.group(0).rstrip(".,;)")
                if not any(bad in cand_email.lower() for bad in (".png", ".jpg", "example.com")):
                    owner_email = cand_email

        pub_str = (item.findtext("pubDate") or "").strip()
        pub_dt = datetime.now(timezone.utc)
        if pub_str:
            try:
                parsed_dt = email.utils.parsedate_to_datetime(pub_str)
                pub_dt = parsed_dt if parsed_dt.tzinfo else parsed_dt.replace(tzinfo=timezone.utc)
            except Exception:
                pass

        dur_sec = parse_rss_duration(dur_raw)

        episodes.append(
            {
                "external_id": ep_guid,
                "title": ep_title,
                "url": ep_link if ep_link.startswith("http") else feed_url,
                "content_type": "podcast_episode",
                "published_at": pub_dt,
                "duration_seconds": dur_sec,
                "is_longform": dur_sec >= 600,
                "description": ep_desc[:1200],
                "language": language,
            }
        )

    if not episodes:
        return None

    return {
        "title": title,
        "author": author,
        "description": description[:2500],
        "link": link if link.startswith("http") else feed_url,
        "language": language,
        "owner_email": owner_email,
        "episodes": episodes,
    }


class PodcastRSSCollector:
    """Permitted public Podcast Discovery (Apple iTunes Search API + Public Podcast RSS Feeds)."""

    ITUNES_SEARCH_URL = "https://itunes.apple.com/search"

    def __init__(self, http_client: httpx.Client | None = None):
        self._client = http_client

    def discover_podcasts(
        self,
        db: Session | None,
        keyword: str,
        country_code: str = "US",
        max_candidates: int = 20,
    ) -> list[dict[str, Any]]:
        close_client = False
        client = self._client
        if client is None:
            client = httpx.Client(timeout=12.0, follow_redirects=True)
            close_client = True

        try:
            start = time.perf_counter()
            try:
                resp = client.get(
                    self.ITUNES_SEARCH_URL,
                    params={
                        "term": keyword,
                        "media": "podcast",
                        "entity": "podcast",
                        "country": country_code.upper()[:2],
                        "limit": min(200, max(50, max_candidates * 3)),
                    },
                )
            except Exception as exc:
                latency = (time.perf_counter() - start) * 1000.0
                if db is not None:
                    db.add(
                        ApiUsage(
                            provider="apple_itunes_podcast_api",
                            endpoint="/search",
                            operation="search_podcasts",
                            units_or_tokens=1,
                            status_code=503,
                            success=False,
                            latency_ms=round(latency, 2),
                            error_detail=str(exc)[:300],
                        )
                    )
                    db.flush()
                raise SourceRestrictionError(
                    message=f"Podcast discovery API unreachable: {exc}",
                    source="podcast_rss",
                    restriction_type="NETWORK_RESTRICTED",
                ) from exc

            latency = (time.perf_counter() - start) * 1000.0
            if resp.status_code != 200:
                if db is not None:
                    db.add(
                        ApiUsage(
                            provider="apple_itunes_podcast_api",
                            endpoint="/search",
                            operation="search_podcasts",
                            units_or_tokens=1,
                            status_code=resp.status_code,
                            success=False,
                            latency_ms=round(latency, 2),
                            error_detail=resp.text[:300],
                        )
                    )
                    db.flush()
                return []

            if db is not None:
                db.add(
                    ApiUsage(
                        provider="apple_itunes_podcast_api",
                        endpoint="/search",
                        operation="search_podcasts",
                        units_or_tokens=1,
                        status_code=200,
                        success=True,
                        latency_ms=round(latency, 2),
                    )
                )
                db.flush()

            items = resp.json().get("results", [])
            candidates: list[dict[str, Any]] = []
            seen_ids: set[str] = set()
            cutoff_recent = datetime.now(timezone.utc) - timedelta(days=55)

            for item in items:
                collection_id = str(item.get("collectionId") or "").strip()
                feed_url = (item.get("feedUrl") or "").strip()
                if not collection_id or not feed_url or collection_id in seen_ids:
                    continue

                track_count = int(item.get("trackCount") or 0)
                if track_count > 0 and track_count < 2:
                    continue

                rel_str = item.get("releaseDate")
                if rel_str:
                    try:
                        rel_dt = datetime.fromisoformat(rel_str.replace("Z", "+00:00"))
                        if rel_dt < cutoff_recent:
                            continue
                    except Exception:
                        pass

                seen_ids.add(collection_id)

                rss_data = self.parse_rss_feed(db, client, feed_url)
                if not rss_data:
                    continue

                raw_country = (item.get("country") or country_code or "US").upper()
                country_name = ISO_COUNTRY_MAP.get(raw_country, ISO_COUNTRY_MAP.get(country_code.upper()[:2], "United States"))
                title = item.get("collectionName") or rss_data.get("title") or "Unknown Podcast"
                artist = item.get("artistName") or rss_data.get("author") or title
                genre = item.get("primaryGenreName") or "Podcasts"
                rss_desc = rss_data.get("description", "")
                enriched_desc = (
                    f"{rss_desc}\n"
                    f"[Official Apple Podcasts Metadata: Genre={genre} | Host={artist} | "
                    f"Episodes={track_count or len(rss_data.get('episodes', []))} | Weekly Podcast Show]"
                ).strip()

                category_label = infer_creator_category(title, enriched_desc, genre, keyword)

                candidates.append(
                    {
                        "platform": "podcast_rss",
                        "platform_id": f"itunes_{collection_id}",
                        "name": f"{artist} — {title}" if artist.lower() not in title.lower() else title,
                        "handle": f"@podcast_{collection_id}",
                        "official_url": item.get("collectionViewUrl") or rss_data.get("link") or feed_url,
                        "category": category_label,
                        "niche": genre,
                        "country": country_name,
                        "language": rss_data.get("language", "en"),
                        "description": enriched_desc,
                        "subscriber_count": None,
                        "total_views": None,
                        "total_content_count": int(track_count or len(rss_data.get("episodes", []))),
                        "discovery_source": "podcast_rss",
                        "is_synthetic": False,
                        "raw_metadata": {
                            "feed_url": feed_url,
                            "rss_email": rss_data.get("owner_email"),
                            "website_url": rss_data.get("link") or item.get("collectionViewUrl"),
                        },
                        "content_items": rss_data.get("episodes", []),
                    }
                )
                if len(candidates) >= max_candidates:
                    break

            return candidates
        finally:
            if close_client and client is not None:
                client.close()

    def parse_rss_feed(self, db: Session | None, client: httpx.Client, feed_url: str) -> dict[str, Any] | None:
        start = time.perf_counter()
        try:
            raw_bytes = b""
            status_code = 200
            if hasattr(client, "stream"):
                with client.stream("GET", feed_url, timeout=8.0) as resp:
                    status_code = resp.status_code
                    if status_code != 200:
                        return None
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in resp.iter_bytes():
                        chunks.append(chunk)
                        total += len(chunk)
                        if total >= 262144:
                            break
                    raw_bytes = b"".join(chunks)
            else:
                resp = client.get(feed_url, timeout=8.0)
                status_code = resp.status_code
                if status_code != 200:
                    return None
                raw_bytes = resp.content[:262144]

            latency = (time.perf_counter() - start) * 1000.0
            if db is not None:
                db.add(
                    ApiUsage(
                        provider="public_podcast_rss",
                        endpoint=feed_url[:240],
                        operation="fetch_rss_feed",
                        units_or_tokens=1,
                        status_code=status_code,
                        success=True,
                        latency_ms=round(latency, 2),
                    )
                )
                db.flush()

            return parse_rss_xml_bytes(raw_bytes, feed_url)
        except Exception:
            return None
