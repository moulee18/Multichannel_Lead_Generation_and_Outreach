from __future__ import annotations

import hashlib
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings
from backend.app.database.models import (
    Base,
    ProductCapability,
    ProductInsight,
    SeedTestAccount,
    User,
)

_ENGINE_CACHE: dict[str, object] = {}


def get_engine(database_url: str | None = None):
    settings = get_settings()
    url = database_url or settings.database_url
    if url.startswith("sqlite:///"):
        db_file = Path(url.replace("sqlite:///", ""))
        db_file.parent.mkdir(parents=True, exist_ok=True)
    if url not in _ENGINE_CACHE:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _ENGINE_CACHE[url] = create_engine(url, connect_args=connect_args, future=True)
    return _ENGINE_CACHE[url]


def get_session_factory(database_url: str | None = None):
    engine = get_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(raw_password: str) -> str:
    return hashlib.sha256(f"incubrix_salt::{raw_password}".encode("utf-8")).hexdigest()


def init_db(database_url: str | None = None) -> None:
    settings = get_settings()
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = get_session_factory(database_url)
    with SessionLocal() as db:
        # Ensure default admin user
        admin = db.query(User).filter(User.username == settings.admin_username).first()
        if not admin:
            db.add(
                User(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                    role="admin",
                    full_name="IncuBrix GrowthOS Administrator",
                    email=settings.sender_email,
                )
            )

        # Ensure confirmed product capabilities from config
        cap_cfg = settings.load_json_config("product_capabilities.json")
        for cap in cap_cfg.get("capabilities", []):
            existing = (
                db.query(ProductCapability)
                .filter(ProductCapability.capability_key == cap["capability_key"])
                .first()
            )
            if not existing:
                db.add(
                    ProductCapability(
                        capability_key=cap["capability_key"],
                        feature_name=cap["feature_name"],
                        description=cap["description"],
                        source_evidence=cap["source_evidence"],
                        verification_date=cap["verification_date"],
                        confirmed=bool(cap.get("confirmed", True)),
                        suitable_use_cases=cap.get("suitable_use_cases", []),
                        limitations=cap.get("limitations", ""),
                    )
                )

        # Ensure default allowlisted participant-owned seed test accounts for 3 channels
        default_test_accounts = [
            {
                "label": "Participant Owned Email Test Box",
                "channel": "email",
                "handle_or_address": "seedtest.owner@example.org",
                "owner_name": settings.sender_name,
            },
            {
                "label": "Participant Owned LinkedIn Sandbox Profile",
                "channel": "linkedin",
                "handle_or_address": "https://www.linkedin.com/in/incubrix-seedtest-owner",
                "owner_name": settings.sender_name,
            },
            {
                "label": "Participant Owned Instagram Sandbox Handle",
                "channel": "instagram",
                "handle_or_address": "@incubrix_seedtest_owner",
                "owner_name": settings.sender_name,
            },
        ]
        for acc in default_test_accounts:
            exists = (
                db.query(SeedTestAccount)
                .filter(
                    SeedTestAccount.channel == acc["channel"],
                    SeedTestAccount.handle_or_address == acc["handle_or_address"],
                )
                .first()
            )
            if not exists:
                db.add(
                    SeedTestAccount(
                        label=acc["label"],
                        channel=acc["channel"],
                        handle_or_address=acc["handle_or_address"],
                        owner_name=acc["owner_name"],
                        is_allowlisted=True,
                        ownership_verified=True,
                    )
                )

        # Ensure initial structured slots for 5 Product Observations and 3 Growth Opportunities
        if db.query(ProductInsight).count() == 0:
            initial_observations = [
                (
                    1,
                    "Observation 1: Spoken-Word Long-Form to Short-Form Repurposing Bottleneck",
                    "Video podcasters and educators publishing 30–90 minute episodes consistently face a manual clipping, captioning, and aspect-ratio formatting bottleneck when adapting episodes for YouTube Shorts, Reels, and LinkedIn.",
                    "IncuBrix Assessment Brief Page 1 ('repurposing, editing, captions, publishing, consistency, backlog or team workflow') & creator public job postings/descriptions.",
                ),
                (
                    2,
                    "Observation 2: Multi-Destination Publishing Friction",
                    "Creators rarely publish exclusively to one platform; managing metadata, titles, captions, and scheduling across YouTube, podcast feeds, LinkedIn, and Instagram creates repetitive coordination overhead.",
                    "IncuBrix Assessment Briefs (Option 1 & Option 4 Distribution Network Brief).",
                ),
                (
                    3,
                    "Observation 3: Unedited Recording Backlogs Delay Sponsorship Delivery",
                    "Monetised creators with courses, sponsorships, or coaching offers frequently mention recorded episode backlogs waiting on post-production editing and caption turnaround.",
                    "Verified creator descriptions and hiring notes in public creator records.",
                ),
                (
                    4,
                    "Observation 4: Solo Host vs. Small Editor Team Handoff Gaps",
                    "Expert-led creators (coaches, consultants, educators) typically operate either solo or with 1–2 part-time freelance editors, making structured review/approval workflows essential.",
                    "Public creator team/hiring pages and podcast show notes.",
                ),
                (
                    5,
                    "Observation 5: Live Product Walkthrough Evidence Requirement",
                    "Direct hands-on product UI walkthrough observations require authenticated access to www.incubrix.com workspace; until live product session screenshots/video are attached, product UI claims remain conservatively scoped to documented brief capabilities.",
                    "Integrity Rule: No fabricated product screenshots or unverified product claims.",
                ),
            ]
            for num, title, detail, ref in initial_observations:
                db.add(
                    ProductInsight(
                        insight_type="OBSERVATION",
                        item_number=num,
                        title=title,
                        detail=detail,
                        evidence_reference=ref,
                        is_verified_product_test=False,
                    )
                )

            initial_opportunities = [
                (
                    1,
                    "Opportunity 1: Episode-to-Multi-Channel Clip Kit for Weekly Video Podcasters",
                    "Target weekly video podcasters (2+ long-form episodes in 60 days) with a rapid turn-key workflow that extracts 5–8 captioned vertical clips and LinkedIn posts per episode.",
                    "Directly addresses the #1 workflow need identified across qualified podcast and video-first creators.",
                ),
                (
                    2,
                    "Opportunity 2: B2B Authority Repurposing for Coaches, Consultants & Educators",
                    "Position IncuBrix for expert-led creators who monetise via high-ticket courses, coaching, or consulting and need consistent YouTube + LinkedIn publishing without hiring a full agency.",
                    "High commercial readiness (courses/coaching) combined with acute time constraints on founder-led content production.",
                ),
                (
                    3,
                    "Opportunity 3: 'Clear Your Backlog' Onboarding Wedge Campaign",
                    "Offer Priority A prospects a concrete first value experience—clearing or repurposing one recent flagship long-form video/podcast episode cited directly in our personalised outreach.",
                    "Evidence-backed outreach referencing a specific recent creator episode yields substantially higher reply rates than generic SaaS cold pitches.",
                ),
            ]
            for num, title, detail, ref in initial_opportunities:
                db.add(
                    ProductInsight(
                        insight_type="OPPORTUNITY",
                        item_number=num,
                        title=title,
                        detail=detail,
                        evidence_reference=ref,
                        is_verified_product_test=True,
                    )
                )

        db.commit()
