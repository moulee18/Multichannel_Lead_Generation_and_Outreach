from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def generate_synthetic_demo_candidates(reference_now: datetime | None = None) -> list[dict[str, Any]]:
    """Generate 35 clearly labelled synthetic demo creators (30 fully qualifying across 7 approved markets + 5 edge/review/rejected cases)."""
    now = reference_now or datetime.now(timezone.utc)
    countries = [
        "United States",
        "United States",
        "United States",
        "Canada",
        "United Kingdom",
        "United Kingdom",
        "Ireland",
        "Australia",
        "New Zealand",
        "Singapore",
    ]
    categories = [
        "Podcaster / Video Podcaster",
        "YouTuber / Video-First Creator",
        "Expert-Led Creator (Coach / Consultant / Educator)",
    ]
    niches = [
        ("B2B SaaS & Founder Growth", "sponsor", "course", "hiring a video editor to repurpose our 60-minute weekly podcast into YouTube Shorts and LinkedIn clips"),
        ("Personal Finance & Investing", "newsletter sponsor", "membership", "struggling with our post-production editing backlog and adding accurate captions to daily clips"),
        ("AI Engineering & Developer Education", "cohort course", "patreon", "need a faster workflow to clip long-form technical tutorials into multi-channel short videos"),
        ("Executive Leadership Coaching", "coaching program", "consulting", "looking to streamline podcast-to-short-form repurposing and maintain weekly publishing consistency"),
        ("Creator Economy & Podcast Strategy", "sponsorships", "digital templates", "our small team workflow between host and freelance editor needs better clip review and caption automation"),
    ]

    candidates: list[dict[str, Any]] = []

    for i in range(1, 31):
        country = countries[(i - 1) % len(countries)]
        category = categories[(i - 1) % len(categories)]
        niche, comm_1, comm_2, need_phrase = niches[(i - 1) % len(niches)]
        slug = f"demo_creator_{i:02d}"
        channel_id = f"UC_SYNTHETIC_DEMO_{i:04d}"
        official_url = f"https://www.youtube.com/channel/{channel_id}"

        # Build 8 recent videos within 30 days AND 3 long-form videos within 60 days
        content_items = []
        for v_idx in range(1, 9):
            pub_dt = now - timedelta(days=v_idx * 3)
            dur = 2400 if v_idx <= 3 else 180
            content_items.append(
                {
                    "external_id": f"vid_{i:02d}_{v_idx:02d}",
                    "title": f"[SYNTHETIC DEMO] {niche} Masterclass Ep {100 + v_idx}: Scaling Content Workflows",
                    "url": f"https://www.youtube.com/watch?v=vid_{i:02d}_{v_idx:02d}",
                    "content_type": "video" if "YouTuber" in category else "podcast_episode",
                    "published_at": pub_dt,
                    "duration_seconds": dur,
                    "is_longform": dur >= 600,
                    "description": (
                        f"In this episode we cover {niche}. Sponsored by AcmeCloud ({comm_1}) and our flagship {comm_2} "
                        f"at https://{slug}.example.org/program. Production note: we are currently {need_phrase}."
                    ),
                    "language": "en",
                    "view_count": 12500 + (i * 350) + (v_idx * 100),
                }
            )

        description = (
            f"[SYNTHETIC DEMO RECORD] Official channel for Creator #{i:02d} ({category} in {niche}). "
            f"Based in {country}. Monetisation: active {comm_1} and flagship {comm_2} at https://{slug}.example.org/offer. "
            f"Workflow note: we are actively {need_phrase}. "
            f"Business inquiries: partnerships@{slug}.example.org | LinkedIn: https://www.linkedin.com/in/{slug} | "
            f"Instagram: https://www.instagram.com/{slug}"
        )

        candidates.append(
            {
                "platform": "youtube",
                "platform_id": channel_id,
                "name": f"Demo Creator {i:02d} ({niche.split('&')[0].strip()})",
                "handle": f"@{slug}",
                "official_url": official_url,
                "category": category,
                "niche": niche,
                "country": country,
                "language": "en",
                "description": description,
                "subscriber_count": 45000 + (i * 2100),
                "total_views": 1800000 + (i * 55000),
                "total_content_count": 140 + i,
                "uploads_playlist_id": f"UU_SYNTHETIC_DEMO_{i:04d}",
                "discovery_source": "synthetic_fixture",
                "is_synthetic": True,
                "content_items": content_items,
            }
        )

    # Add 5 edge cases for NEEDS_REVIEW and REJECTED verification testing
    edge_cases = [
        {
            "platform": "youtube",
            "platform_id": "UC_SYNTHETIC_EDGE_AGENCY_31",
            "name": "Apex Viral Talent Management Agency [SYNTHETIC DEMO]",
            "handle": "@apex_agency_demo",
            "official_url": "https://www.youtube.com/channel/UC_SYNTHETIC_EDGE_AGENCY_31",
            "category": "Agency",
            "niche": "Talent Management Firm",
            "country": "United States",
            "language": "en",
            "description": "We are a creator management firm and full-service media agency. Contact: hello@apexagency.example.org",
            "subscriber_count": 15000,
            "total_views": 300000,
            "total_content_count": 40,
            "discovery_source": "synthetic_fixture",
            "is_synthetic": True,
            "content_items": [
                {
                    "external_id": "vid_31_01",
                    "title": "Our Agency Showreel",
                    "url": "https://www.youtube.com/watch?v=vid_31_01",
                    "content_type": "video",
                    "published_at": now - timedelta(days=5),
                    "duration_seconds": 1200,
                    "is_longform": True,
                    "description": "Agency overview.",
                    "language": "en",
                }
            ],
        },
        {
            "platform": "youtube",
            "platform_id": "UC_SYNTHETIC_EDGE_INACTIVE_32",
            "name": "Dormant Podcast Show [SYNTHETIC DEMO]",
            "handle": "@dormant_show_demo",
            "official_url": "https://www.youtube.com/channel/UC_SYNTHETIC_EDGE_INACTIVE_32",
            "category": "Podcaster / Video Podcaster",
            "niche": "Tech History",
            "country": "Canada",
            "language": "en",
            "description": "Sponsored by TechBook. Need editing help for our backlog. Business email: host@dormant.example.org",
            "subscriber_count": 22000,
            "total_views": 500000,
            "total_content_count": 25,
            "discovery_source": "synthetic_fixture",
            "is_synthetic": True,
            "content_items": [
                {
                    "external_id": "vid_32_01",
                    "title": "Old Episode from Last Year",
                    "url": "https://www.youtube.com/watch?v=vid_32_01",
                    "content_type": "podcast_episode",
                    "published_at": now - timedelta(days=120),
                    "duration_seconds": 1800,
                    "is_longform": True,
                    "description": "Archived episode.",
                    "language": "en",
                }
            ],
        },
        {
            "platform": "youtube",
            "platform_id": "UC_SYNTHETIC_EDGE_NOCOMM_33",
            "name": "Hobbyist Educator Channel [SYNTHETIC DEMO]",
            "handle": "@hobby_educator_demo",
            "official_url": "https://www.youtube.com/channel/UC_SYNTHETIC_EDGE_NOCOMM_33",
            "category": "Expert-Led Creator (Coach / Consultant / Educator)",
            "niche": "Mathematics",
            "country": "United Kingdom",
            "language": "en",
            "description": "Free math videos. Struggling with captioning and editing workflow. Email: math@hobby.example.org",
            "subscriber_count": 18000,
            "total_views": 410000,
            "total_content_count": 60,
            "discovery_source": "synthetic_fixture",
            "is_synthetic": True,
            "content_items": [
                {
                    "external_id": f"vid_33_{k}",
                    "title": f"Calculus Lecture {k}",
                    "url": f"https://www.youtube.com/watch?v=vid_33_{k}",
                    "content_type": "video",
                    "published_at": now - timedelta(days=k * 7),
                    "duration_seconds": 1800,
                    "is_longform": True,
                    "description": "Pure educational lecture with no commercial activity.",
                    "language": "en",
                }
                for k in range(1, 4)
            ],
        },
        {
            "platform": "youtube",
            "platform_id": "UC_SYNTHETIC_EDGE_NOCONTACT_34",
            "name": "Unreachable Finance Creator [SYNTHETIC DEMO]",
            "handle": "@unreachable_fin_demo",
            "official_url": "https://www.youtube.com/channel/UC_SYNTHETIC_EDGE_NOCONTACT_34",
            "category": "YouTuber / Video-First Creator",
            "niche": "Personal Finance",
            "country": "Australia",
            "language": "en",
            "description": "Check out our investing course and sponsorship program. Need help repurposing long videos into shorts.",
            "subscriber_count": 64000,
            "total_views": 2100000,
            "total_content_count": 95,
            "discovery_source": "synthetic_fixture",
            "is_synthetic": True,
            "content_items": [
                {
                    "external_id": f"vid_34_{k}",
                    "title": f"Market Recap {k}",
                    "url": f"https://www.youtube.com/watch?v=vid_34_{k}",
                    "content_type": "video",
                    "published_at": now - timedelta(days=k * 6),
                    "duration_seconds": 1500,
                    "is_longform": True,
                    "description": "Sponsored by FinApp. Need video editing workflow.",
                    "language": "en",
                }
                for k in range(1, 4)
            ],
        },
        {
            "platform": "youtube",
            "platform_id": "UC_SYNTHETIC_EDGE_UNKNOWN_COUNTRY_35",
            "name": "Global Nomad Podcaster [SYNTHETIC DEMO]",
            "handle": "@nomad_pod_demo",
            "official_url": "https://www.youtube.com/channel/UC_SYNTHETIC_EDGE_UNKNOWN_COUNTRY_35",
            "category": "Podcaster / Video Podcaster",
            "niche": "Remote Work",
            "country": "UNKNOWN",
            "language": "en",
            "description": "Sponsored by NomadGear. Looking for podcast repurposing and caption automation. Business: hello@nomadpod.example.org",
            "subscriber_count": 31000,
            "total_views": 890000,
            "total_content_count": 72,
            "discovery_source": "synthetic_fixture",
            "is_synthetic": True,
            "content_items": [
                {
                    "external_id": f"vid_35_{k}",
                    "title": f"Remote Founder Interview {k}",
                    "url": f"https://www.youtube.com/watch?v=vid_35_{k}",
                    "content_type": "podcast_episode",
                    "published_at": now - timedelta(days=k * 5),
                    "duration_seconds": 2100,
                    "is_longform": True,
                    "description": "Sponsored by NomadGear. Need clip editing.",
                    "language": "en",
                }
                for k in range(1, 4)
            ],
        },
    ]

    return candidates + edge_cases
