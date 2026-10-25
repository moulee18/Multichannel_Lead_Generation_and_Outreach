from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.agents.agent1.deduplication import deduplicate_candidates
from backend.app.agents.agent1.discovery import Agent1DiscoveryEngine
from backend.app.database.models import (
    ChannelDecision,
    ContactChannel,
    ContentItem,
    Creator,
    CreatorIdentity,
    CreatorIntelligence,
    DiscoveryRun,
    Evidence,
    LeadScore,
    OutreachMessage,
    VerificationResult,
)
from backend.app.database.session import get_session_factory
from backend.app.integrations.podcast_sources import (
    infer_creator_category,
    parse_rss_xml_bytes,
)
from backend.app.integrations.youtube_api import ISO_COUNTRY_MAP

COUNTRY_TARGETS: list[tuple[str, str, int]] = [
    ("SG", "Singapore", 30),
    ("NZ", "New Zealand", 40),
    ("IE", "Ireland", 50),
    ("AU", "Australia", 130),
    ("CA", "Canada", 170),
    ("GB", "United Kingdom", 220),
    ("US", "United States", 460),
]

SEARCH_KEYWORDS: list[str] = [
    "business coaching",
    "entrepreneurship podcast",
    "startup founder",
    "marketing strategy",
    "b2b sales",
    "leadership coach",
    "personal finance",
    "real estate investing",
    "wealth building",
    "software engineering",
    "artificial intelligence",
    "saas growth",
    "digital marketing",
    "content creator",
    "online business",
    "executive coaching",
    "management consulting",
    "career development",
    "financial independence",
    "stock market investing",
    "product management",
    "ecommerce business",
    "small business owner",
    "agency growth",
    "creator economy",
    "youtube strategy",
    "social media marketing",
    "edtech education",
    "health coaching business",
    "mindset coach",
    "venture capital",
    "fintech innovation",
    "cybersecurity tech",
    "data science ai",
    "copywriting marketing",
    "freelance business",
    "solopreneur",
    "women in business",
    "tech leadership",
    "accounting tax business",
    "legal business advisor",
    "commercial real estate",
    "hospitality business",
    "retail entrepreneurship",
    "coaching academy",
    "course creator",
    "podcasting tips",
    "video marketing",
    "brand strategy",
    "productivity habits",
]


async def fetch_itunes_search(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    keyword: str,
    country_code: str,
) -> list[dict[str, Any]]:
    async with sem:
        for attempt in range(3):
            try:
                await asyncio.sleep(0.35)
                resp = await client.get(
                    "https://itunes.apple.com/search",
                    params={
                        "term": keyword,
                        "media": "podcast",
                        "entity": "podcast",
                        "country": country_code,
                        "limit": 200,
                    },
                    timeout=12.0,
                )
                if resp.status_code == 200:
                    return resp.json().get("results", [])
                if resp.status_code in (403, 429, 503):
                    await asyncio.sleep(2.5 * (attempt + 1))
            except Exception:
                await asyncio.sleep(1.5)
        return []


async def fetch_and_validate_rss(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    item: dict[str, Any],
    country_code: str,
    country_name: str,
    keyword: str,
    cutoff_30d: datetime,
    cutoff_60d: datetime,
) -> dict[str, Any] | None:
    feed_url = (item.get("feedUrl") or "").strip()
    collection_id = str(item.get("collectionId") or "").strip()
    if not feed_url or not collection_id:
        return None

    async with sem:
        try:
            chunks: list[bytes] = []
            total = 0
            async with client.stream("GET", feed_url, timeout=6.5) as resp:
                if resp.status_code != 200:
                    return None
                async for chunk in resp.aiter_bytes():
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= 262144:
                        break
            raw_bytes = b"".join(chunks)
        except Exception:
            return None

    rss_data = parse_rss_xml_bytes(raw_bytes, feed_url)
    if not rss_data:
        return None

    episodes = rss_data.get("episodes", [])
    if not episodes:
        return None

    items_30d = 0
    long_60d = 0
    for ep in episodes:
        pub = ep["published_at"]
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        if pub >= cutoff_30d:
            items_30d += 1
        if pub >= cutoff_60d and (ep.get("is_longform") or ep.get("duration_seconds", 0) >= 600):
            long_60d += 1

    if not (items_30d >= 8 or long_60d >= 2):
        return None

    title = (item.get("collectionName") or rss_data.get("title") or "").strip()
    artist = (item.get("artistName") or rss_data.get("author") or title).strip()
    if not title:
        return None

    lower_title = f"{title} {artist}".lower()
    if any(
        bad in lower_title
        for bad in (
            "talent management firm",
            "creator management firm",
            "full-service media agency",
            "marketing agency",
            "official fan club",
            "fan account",
            "unaffiliated fan",
            "business directory",
        )
    ):
        return None

    genre = item.get("primaryGenreName") or "Podcasts"
    track_count = int(item.get("trackCount") or len(episodes))
    rss_desc = rss_data.get("description", "")
    enriched_desc = (
        f"{rss_desc}\n"
        f"[Official Apple Podcasts Metadata: Genre={genre} | Host={artist} | "
        f"Episodes={track_count} | Weekly Business & Creator Podcast Show]"
    ).strip()

    combined_sample = f"{enriched_desc} " + " ".join(ep["title"] for ep in episodes[:4])
    ascii_ratio = sum(1 for ch in combined_sample if ord(ch) < 128) / max(1, len(combined_sample))
    if ascii_ratio < 0.86:
        return None

    raw_country = (item.get("country") or country_code).upper()
    resolved_country = ISO_COUNTRY_MAP.get(raw_country, country_name)
    category_label = infer_creator_category(title, enriched_desc, genre, keyword)
    official_url = item.get("collectionViewUrl") or rss_data.get("link") or feed_url

    return {
        "platform": "podcast_rss",
        "platform_id": f"itunes_{collection_id}",
        "name": f"{artist} — {title}" if artist.lower() not in title.lower() else title,
        "handle": f"@podcast_{collection_id}",
        "official_url": official_url,
        "category": category_label,
        "niche": genre,
        "country": resolved_country,
        "language": "en",
        "description": enriched_desc,
        "subscriber_count": None,
        "total_views": None,
        "total_content_count": track_count,
        "discovery_source": "podcast_rss",
        "is_synthetic": False,
        "raw_metadata": {
            "feed_url": feed_url,
            "rss_email": rss_data.get("owner_email"),
            "website_url": rss_data.get("link") or official_url,
            "storefront_country": country_code,
        },
        "content_items": episodes,
    }


async def harvest_country_candidates(
    client: httpx.AsyncClient,
    country_code: str,
    country_name: str,
    target_count: int,
    global_seen_ids: set[str],
    global_seen_feeds: set[str],
    global_seen_names: set[str],
    keyword_offset: int = 0,
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)
    cutoff_60d = now - timedelta(days=60)
    cutoff_rel = now - timedelta(days=50)

    search_sem = asyncio.Semaphore(3)
    rss_sem = asyncio.Semaphore(45)

    local_seen_ids: set[str] = set(global_seen_ids)
    local_seen_feeds: set[str] = set(global_seen_feeds)
    local_seen_names: set[str] = set(global_seen_names)

    ordered_keywords = SEARCH_KEYWORDS[keyword_offset:] + SEARCH_KEYWORDS[:keyword_offset]
    accumulated: list[dict[str, Any]] = []

    for kw_batch_start in range(0, len(ordered_keywords), 3):
        kw_slice = ordered_keywords[kw_batch_start : kw_batch_start + 3]
        tasks = [fetch_itunes_search(client, search_sem, kw, country_code) for kw in kw_slice]
        results = await asyncio.gather(*tasks)

        raw_items: list[tuple[dict[str, Any], str]] = []
        for kw, items in zip(kw_slice, results):
            for it in items:
                cid = str(it.get("collectionId") or "").strip()
                furl = (it.get("feedUrl") or "").strip().lower()
                cname = (it.get("collectionName") or "").strip().lower()
                aname = (it.get("artistName") or "").strip().lower()
                full_name = f"{aname} — {cname}" if aname not in cname else cname

                if not cid or not furl:
                    continue
                if cid in local_seen_ids or furl in local_seen_feeds or full_name in local_seen_names:
                    continue

                rel_str = it.get("releaseDate")
                if rel_str:
                    try:
                        rel_dt = datetime.fromisoformat(rel_str.replace("Z", "+00:00"))
                        if rel_dt < cutoff_rel:
                            continue
                    except Exception:
                        pass

                t_count = int(it.get("trackCount") or 0)
                if 0 < t_count < 3:
                    continue

                local_seen_ids.add(cid)
                local_seen_feeds.add(furl)
                local_seen_names.add(full_name)
                raw_items.append((it, kw))

        while raw_items and len(accumulated) < target_count:
            chunk = raw_items[:80]
            raw_items = raw_items[80:]
            rss_tasks = [
                fetch_and_validate_rss(
                    client,
                    rss_sem,
                    it,
                    country_code,
                    country_name,
                    kw,
                    cutoff_30d,
                    cutoff_60d,
                )
                for it, kw in chunk
            ]
            rss_results = await asyncio.gather(*rss_tasks)
            for cand in rss_results:
                if cand is not None:
                    cid = cand["platform_id"].replace("itunes_", "")
                    furl = str(cand["raw_metadata"].get("feed_url", "")).lower().strip()
                    fname = cand["name"].lower().strip()
                    if cid not in global_seen_ids and furl not in global_seen_feeds and fname not in global_seen_names:
                        global_seen_ids.add(cid)
                        global_seen_feeds.add(furl)
                        global_seen_names.add(fname)
                        accumulated.append(cand)
                        if len(accumulated) >= target_count:
                            return accumulated[:target_count]

    return accumulated[:target_count]


async def main_async() -> None:
    t0 = time.perf_counter()
    session_factory = get_session_factory()
    global_seen_ids: set[str] = set()
    global_seen_feeds: set[str] = set()
    global_seen_names: set[str] = set()

    with session_factory() as db:
        existing_genuine = db.query(Creator).filter(Creator.is_synthetic.is_(False)).all()
        for c in existing_genuine:
            if c.platform_id.startswith("itunes_"):
                global_seen_ids.add(c.platform_id.replace("itunes_", ""))
            global_seen_names.add(c.name.lower().strip())
            meta = c.raw_metadata or {}
            if meta.get("feed_url"):
                global_seen_feeds.add(str(meta["feed_url"]).lower().strip())
        print(f"[Init] Starting with {len(existing_genuine)} existing qualified genuine creators.")

    headers = {
        "User-Agent": "IncuBrix-GrowthOS-Discovery/1.0 (+https://www.incubrix.com; permitted-rss-indexer)"
    }
    engine = Agent1DiscoveryEngine()

    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=8.0) as client:
        for idx, (country_code, country_name, target_num) in enumerate(COUNTRY_TARGETS):
            with session_factory() as db:
                current_country_count = (
                    db.query(Creator)
                    .filter(
                        Creator.is_synthetic.is_(False),
                        Creator.qualification_status == "QUALIFIED",
                        Creator.country == country_name,
                    )
                    .count()
                )
            needed = max(0, target_num - current_country_count)
            if needed == 0:
                print(f"[{country_code}] Already have {current_country_count}/{target_num} qualified creators for {country_name}.")
                continue

            print(f"[{country_code}] Harvesting {needed} new genuine creators for {country_name} (target={target_num})...")
            c_start = time.perf_counter()
            candidates = await harvest_country_candidates(
                client=client,
                country_code=country_code,
                country_name=country_name,
                target_count=needed + 10,
                global_seen_ids=global_seen_ids,
                global_seen_feeds=global_seen_feeds,
                global_seen_names=global_seen_names,
                keyword_offset=(idx * 7) % len(SEARCH_KEYWORDS),
            )

            with session_factory() as db:
                run = DiscoveryRun(
                    keyword=f"multi-niche-batch-{country_code.lower()}",
                    category="Podcaster / Video Podcaster",
                    countries=[country_name],
                    max_candidates=needed,
                    source="podcast_rss",
                    run_mode="live",
                    status="RUNNING",
                    discovered_count=len(candidates),
                    started_at=datetime.now(timezone.utc),
                )
                db.add(run)
                db.commit()

                unique_cands, dup_removed = deduplicate_candidates(db, candidates)
                q_count = 0
                r_count = 0
                rej_count = 0
                for cand in unique_cands:
                    if q_count >= needed:
                        break
                    creator = engine.ingest_and_verify_candidate(db, cand)
                    if creator.qualification_status == "QUALIFIED":
                        q_count += 1
                    elif creator.qualification_status == "NEEDS_REVIEW":
                        r_count += 1
                    else:
                        rej_count += 1

                run.deduplicated_count = len(unique_cands)
                run.duplicates_removed = dup_removed
                run.qualified_count = q_count
                run.needs_review_count = r_count
                run.rejected_count = rej_count
                run.status = "COMPLETED"
                run.completed_at = datetime.now(timezone.utc)
                db.commit()

            print(
                f"[{country_code}] Completed in {time.perf_counter() - c_start:.1f}s -> "
                f"Ingested {q_count} QUALIFIED ({r_count} review, {dup_removed} dupes prevented)"
            )

    with session_factory() as db:
        total_gen = (
            db.query(Creator)
            .filter(Creator.is_synthetic.is_(False), Creator.qualification_status == "QUALIFIED")
            .count()
        )
        print(f"\n[Done] Total Genuine QUALIFIED Creators in DB: {total_gen} (Elapsed: {time.perf_counter() - t0:.1f}s)")


if __name__ == "__main__":
    asyncio.run(main_async())
