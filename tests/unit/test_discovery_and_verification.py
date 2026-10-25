from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from backend.app.agents.agent1.deduplication import deduplicate_candidates
from backend.app.agents.agent1.discovery import Agent1DiscoveryEngine
from backend.app.agents.agent1.evidence import upsert_evidence
from backend.app.agents.agent1.verification import verify_creator_qualification
from backend.app.database.models import Evidence
from backend.app.database.session import get_session_factory, init_db
from backend.app.integrations.youtube_api import YouTubeAPICollector, parse_iso8601_duration
from backend.app.utils.errors import SourceRestrictionError


@pytest.fixture()
def db_session(tmp_path: Path):
    db_url = f"sqlite:///{(tmp_path / 'test_agent1.db').as_posix()}"
    init_db(db_url)
    SessionLocal = get_session_factory(db_url)
    with SessionLocal() as session:
        yield session


def test_youtube_valid_response_and_pagination(db_session):
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = dict(request.url.params)
        if path.endswith("/search"):
            if params.get("pageToken") == "PAGE_2":
                return httpx.Response(
                    200,
                    json={
                        "items": [{"id": {"channelId": "UC_TEST_CHANNEL_02"}}],
                    },
                )
            return httpx.Response(
                200,
                json={
                    "nextPageToken": "PAGE_2",
                    "items": [
                        {"id": {"channelId": "UC_TEST_CHANNEL_01"}},
                        {"id": {"channelId": "UC_TEST_CHANNEL_01"}},  # duplicate ID in search
                    ],
                },
            )
        if path.endswith("/channels"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "UC_TEST_CHANNEL_01",
                            "snippet": {
                                "title": "Creator One",
                                "description": "Sponsored by Acme. Need video editing for shorts. Email: one@creator.org",
                                "country": "US",
                                "customUrl": "@creator_one",
                                "defaultLanguage": "en",
                            },
                            "statistics": {"subscriberCount": "50000", "viewCount": "1000000", "videoCount": "80"},
                            "contentDetails": {"relatedPlaylists": {"uploads": "UU_TEST_01"}},
                        },
                        {
                            "id": "UC_TEST_CHANNEL_02",
                            "snippet": {
                                "title": "Creator Two",
                                "description": "Podcast host.",
                                "country": "CA",
                            },
                            "statistics": {"subscriberCount": "12000", "viewCount": "200000", "videoCount": "30"},
                            "contentDetails": {"relatedPlaylists": {"uploads": "UU_TEST_02"}},
                        },
                    ]
                },
            )
        if path.endswith("/playlistItems"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "snippet": {
                                "title": "Recent Longform Episode",
                                "description": "Episode notes",
                                "publishedAt": now_iso,
                            },
                            "contentDetails": {"videoId": "VID_101"},
                        }
                    ]
                },
            )
        if path.endswith("/videos"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "VID_101",
                            "snippet": {"defaultAudioLanguage": "en"},
                            "contentDetails": {"duration": "PT25M10S"},
                            "statistics": {"viewCount": "4200"},
                        }
                    ]
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    collector = YouTubeAPICollector(api_key="test-valid-key", http_client=client)
    candidates = collector.discover_candidates(db_session, keyword="podcast", max_candidates=2)
    assert len(candidates) == 2
    assert candidates[0]["platform_id"] == "UC_TEST_CHANNEL_01"
    assert candidates[0]["country"] == "United States"
    assert candidates[0]["content_items"][0]["duration_seconds"] == parse_iso8601_duration("PT25M10S")


def test_youtube_empty_results(db_session):
    client = httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"items": []}))
    )
    collector = YouTubeAPICollector(api_key="test-key", http_client=client)
    assert collector.discover_candidates(db_session, keyword="nothing", max_candidates=5) == []


def test_youtube_invalid_api_key(db_session):
    client = httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(400, text="API key not valid"))
    )
    collector = YouTubeAPICollector(api_key="bad-key", http_client=client)
    with pytest.raises(SourceRestrictionError) as exc_info:
        collector.discover_candidates(db_session, keyword="podcast")
    assert exc_info.value.code == "INVALID_API_KEY"


def test_youtube_quota_exceeded(db_session):
    client = httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(403, text='{"error": "quotaExceeded"}'))
    )
    collector = YouTubeAPICollector(api_key="valid-key", http_client=client)
    with pytest.raises(SourceRestrictionError) as exc_info:
        collector.discover_candidates(db_session, keyword="podcast")
    assert exc_info.value.code == "QUOTA_EXCEEDED"


def test_youtube_timeout_handling(db_session):
    def timeout_handler(req: httpx.Request):
        raise httpx.TimeoutException("Timed out connecting to YouTube API")

    client = httpx.Client(transport=httpx.MockTransport(timeout_handler))
    collector = YouTubeAPICollector(api_key="valid-key", http_client=client)
    with pytest.raises(SourceRestrictionError) as exc_info:
        collector.discover_candidates(db_session, keyword="podcast")
    assert exc_info.value.code == "TIMEOUT"


def test_deduplication_and_stable_ids(db_session):
    raw = [
        {"platform": "youtube", "platform_id": "UC_STABLE_1", "official_url": "https://www.youtube.com/channel/UC_STABLE_1"},
        {"platform": "youtube", "platform_id": "UC_STABLE_1", "official_url": "https://www.youtube.com/channel/UC_STABLE_1/"},
        {"platform": "youtube", "platform_id": "", "official_url": "https://www.youtube.com/channel/missing"},
    ]
    unique, removed = deduplicate_candidates(db_session, raw)
    assert len(unique) == 1
    assert removed == 2


def test_verification_rules_8_in_30d_and_2_longform_in_60d(db_session):
    now = datetime.now(timezone.utc)
    engine = Agent1DiscoveryEngine()

    # Case A: 8 short items in 30 days -> QUALIFIED
    cand_8_short = {
        "platform": "youtube",
        "platform_id": "UC_QUAL_8_SHORT",
        "name": "Short Clip Educator",
        "official_url": "https://www.youtube.com/channel/UC_QUAL_8_SHORT",
        "category": "YouTuber / Video-First Creator",
        "country": "United States",
        "language": "en",
        "description": "Sponsored by CourseApp. Need help with video editing and captions. Email: team@shortedu.org",
        "content_items": [
            {
                "external_id": f"s_{i}",
                "title": f"Daily Tip {i}",
                "url": f"https://www.youtube.com/watch?v=s_{i}",
                "published_at": now - timedelta(days=i * 2),
                "duration_seconds": 120,
                "is_longform": False,
                "language": "en",
            }
            for i in range(1, 9)
        ],
    }
    c1 = engine.ingest_and_verify_candidate(db_session, cand_8_short, reference_now=now)
    assert c1.qualification_status == "QUALIFIED"
    assert c1.items_30d == 8

    # Case B: Only 2 items in 60 days, both long-form (>=600s) -> QUALIFIED
    cand_2_long = {
        "platform": "youtube",
        "platform_id": "UC_QUAL_2_LONG",
        "name": "Deep Dive Podcaster",
        "official_url": "https://www.youtube.com/channel/UC_QUAL_2_LONG",
        "category": "Podcaster / Video Podcaster",
        "country": "Canada",
        "language": "en",
        "description": "Our coaching program is open. Need podcast repurposing into shorts. Contact: host@deepdive.ca",
        "content_items": [
            {
                "external_id": "lf_1",
                "title": "Episode 1",
                "url": "https://www.youtube.com/watch?v=lf_1",
                "published_at": now - timedelta(days=20),
                "duration_seconds": 2400,
                "is_longform": True,
                "language": "en",
            },
            {
                "external_id": "lf_2",
                "title": "Episode 2",
                "url": "https://www.youtube.com/watch?v=lf_2",
                "published_at": now - timedelta(days=45),
                "duration_seconds": 1800,
                "is_longform": True,
                "language": "en",
            },
        ],
    }
    c2 = engine.ingest_and_verify_candidate(db_session, cand_2_long, reference_now=now)
    assert c2.qualification_status == "QUALIFIED"
    assert c2.longform_60d == 2


def test_verification_negative_and_review_cases(db_session):
    now = datetime.now(timezone.utc)
    engine = Agent1DiscoveryEngine()

    base_items = [
        {
            "external_id": f"v_{k}",
            "title": f"Episode {k}",
            "url": f"https://www.youtube.com/watch?v=v_{k}",
            "published_at": now - timedelta(days=k * 5),
            "duration_seconds": 1800,
            "is_longform": True,
            "language": "en",
        }
        for k in range(1, 4)
    ]

    # 1. Missing commercial activity -> NEEDS_REVIEW
    c_no_comm = engine.ingest_and_verify_candidate(
        db_session,
        {
            "platform": "youtube",
            "platform_id": "UC_NO_COMM",
            "name": "No Commercial Channel",
            "official_url": "https://www.youtube.com/channel/UC_NO_COMM",
            "category": "YouTuber / Video-First Creator",
            "country": "United Kingdom",
            "language": "en",
            "description": "Need video editing and captioning workflow. Email: hi@nocomm.co.uk",
            "content_items": base_items,
        },
        reference_now=now,
    )
    assert c_no_comm.qualification_status == "NEEDS_REVIEW"

    # 2. Missing workflow need -> NEEDS_REVIEW
    c_no_need = engine.ingest_and_verify_candidate(
        db_session,
        {
            "platform": "youtube",
            "platform_id": "UC_NO_NEED",
            "name": "No Workflow Need Channel",
            "official_url": "https://www.youtube.com/channel/UC_NO_NEED",
            "category": "YouTuber / Video-First Creator",
            "country": "Australia",
            "language": "en",
            "description": "Sponsored by BrandX. Email: biz@noneed.com.au",
            "content_items": base_items,
        },
        reference_now=now,
    )
    assert c_no_need.qualification_status == "NEEDS_REVIEW"

    # 3. Unknown country -> NEEDS_REVIEW
    c_unk_country = engine.ingest_and_verify_candidate(
        db_session,
        {
            "platform": "youtube",
            "platform_id": "UC_UNK_CTRY",
            "name": "Unknown Country Creator",
            "official_url": "https://www.youtube.com/channel/UC_UNK_CTRY",
            "category": "Podcaster / Video Podcaster",
            "country": "UNKNOWN",
            "language": "en",
            "description": "Sponsored by BrandX. Need video editing for shorts. Email: biz@unk.org",
            "content_items": base_items,
        },
        reference_now=now,
    )
    assert c_unk_country.country == "UNKNOWN"
    assert c_unk_country.qualification_status == "NEEDS_REVIEW"

    # 4. Missing contact -> NEEDS_REVIEW
    c_no_contact = engine.ingest_and_verify_candidate(
        db_session,
        {
            "platform": "youtube",
            "platform_id": "UC_NO_CTC",
            "name": "No Contact Creator",
            "official_url": "https://www.youtube.com/channel/UC_NO_CTC",
            "category": "Podcaster / Video Podcaster",
            "country": "Ireland",
            "language": "en",
            "description": "Sponsored by BrandX. Need video editing and captioning workflow.",
            "content_items": base_items,
        },
        reference_now=now,
    )
    assert c_no_contact.qualification_status == "NEEDS_REVIEW"

    # 5. Non-English language -> REJECTED
    c_non_en = engine.ingest_and_verify_candidate(
        db_session,
        {
            "platform": "youtube",
            "platform_id": "UC_NON_EN",
            "name": "Spanish Channel",
            "official_url": "https://www.youtube.com/channel/UC_NON_EN",
            "category": "YouTuber / Video-First Creator",
            "country": "United States",
            "language": "es",
            "description": "Sponsored by BrandX. Need video editing. Email: hola@spanish.org",
            "content_items": base_items,
        },
        reference_now=now,
    )
    assert c_non_en.qualification_status == "REJECTED"

    # 6. Expired evidence (>30 days old)
    c_exp = engine.ingest_and_verify_candidate(
        db_session,
        {
            "platform": "youtube",
            "platform_id": "UC_EXP_EV",
            "name": "Expired Evidence Creator",
            "official_url": "https://www.youtube.com/channel/UC_EXP_EV",
            "category": "Podcaster / Video Podcaster",
            "country": "Singapore",
            "language": "en",
            "description": "Sponsored by BrandX. Need video editing and clips. Email: hi@sgpod.sg",
            "content_items": base_items,
        },
        reference_now=now,
    )
    assert c_exp.qualification_status == "QUALIFIED"
    # Manually age an evidence record past 30 days and lock it as manual override so checked_at stays old
    ev = db_session.query(Evidence).filter(Evidence.creator_id == c_exp.id).first()
    ev.checked_at = now - timedelta(days=40)
    ev.is_manual_override = True
    db_session.commit()
    verif_after = verify_creator_qualification(db_session, c_exp, reference_now=now)
    assert verif_after.freshness_check is False
    assert c_exp.qualification_status == "NEEDS_REVIEW"
