from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.agents.agent1.deduplication import (
    compute_candidate_hash,
    find_existing_creator,
)
from backend.app.agents.agent1.discovery import Agent1DiscoveryEngine
from backend.app.agents.agent1.verification import verify_creator_qualification
from backend.app.agents.agent2.channel_selection import select_creator_channels
from backend.app.agents.agent2.intelligence import generate_creator_intelligence
from backend.app.agents.agent2.outreach import generate_outreach_for_creator
from backend.app.agents.agent2.scoring import score_and_rank_qualified_leads
from backend.app.database.models import ApiUsage, Creator, Evidence, RefreshHistory


def run_smart_refresh(
    db: Session,
    incoming_candidates: list[dict[str, Any]] | None = None,
    job_id: str | None = None,
    reference_now: datetime | None = None,
) -> RefreshHistory:
    """Feature 4 — Smart Refresh.
    Refreshes stored leads without unnecessarily repeating unchanged processing.
    Tracks new creators, updated creators, unchanged records, stale evidence,
    invalidated qualifications, duplicates prevented, runtime, and API usage.
    """
    start_perf = time.perf_counter()
    now = reference_now or datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)

    api_count_before = db.query(ApiUsage).count()
    engine = Agent1DiscoveryEngine()

    new_creators = 0
    updated_creators = 0
    unchanged_records = 0
    stale_evidence_count = 0
    invalidated_qualifications = 0
    duplicates_prevented = 0

    processed_creator_ids: set[str] = set()

    # 1. Process incoming candidates if provided
    if incoming_candidates:
        seen_batch_keys: set[tuple[str, str]] = set()
        for cand in incoming_candidates:
            platform = str(cand.get("platform") or "youtube").lower()
            pid = str(cand.get("platform_id") or "").strip()
            if not pid:
                continue
            key = (platform, pid)
            if key in seen_batch_keys:
                duplicates_prevented += 1
                continue
            seen_batch_keys.add(key)

            existing = find_existing_creator(db, cand)
            cand_hash = compute_candidate_hash(cand)

            if existing is None:
                creator = engine.ingest_and_verify_candidate(db, cand, reference_now=now)
                new_creators += 1
                processed_creator_ids.add(creator.id)
            else:
                duplicates_prevented += 1
                processed_creator_ids.add(existing.id)
                # Check if content_hash changed or if evidence is stale (>30 days)
                last_chk = existing.last_checked_at
                if last_chk and last_chk.tzinfo is None:
                    last_chk = last_chk.replace(tzinfo=timezone.utc)
                is_stale = bool(not last_chk or last_chk < cutoff_30d)

                if existing.content_hash == cand_hash and not is_stale:
                    unchanged_records += 1
                else:
                    prev_status = existing.qualification_status
                    creator = engine.ingest_and_verify_candidate(db, cand, reference_now=now)
                    updated_creators += 1
                    if prev_status == "QUALIFIED" and creator.qualification_status != "QUALIFIED":
                        invalidated_qualifications += 1

    # 2. Check existing stored creators not in incoming batch for stale evidence (>30 days)
    all_creators = db.query(Creator).all()
    for creator in all_creators:
        if creator.id in processed_creator_ids:
            continue
        evidences = db.query(Evidence).filter(Evidence.creator_id == creator.id).all()
        creator_stale = False
        for ev in evidences:
            chk = ev.checked_at if ev.checked_at.tzinfo else ev.checked_at.replace(tzinfo=timezone.utc)
            if chk < cutoff_30d:
                stale_evidence_count += 1
                creator_stale = True

        if creator_stale:
            prev_status = creator.qualification_status
            # Re-verify without refreshing external timestamps so expired evidence invalidates qualification
            verify_creator_qualification_preserving_evidence_dates(db, creator, reference_now=now)
            updated_creators += 1
            if prev_status == "QUALIFIED" and creator.qualification_status != "QUALIFIED":
                invalidated_qualifications += 1
        else:
            unchanged_records += 1

    # 3. Re-score and update downstream Agent 2 only if new/updated/invalidated records occurred
    if new_creators > 0 or updated_creators > 0 or invalidated_qualifications > 0:
        scores = score_and_rank_qualified_leads(db)
        for s in scores:
            if s.creator:
                select_creator_channels(db, s.creator)
                if s.priority_tier == "Priority A":
                    generate_creator_intelligence(db, s.creator)
                    generate_outreach_for_creator(db, s.creator)

    api_count_after = db.query(ApiUsage).count()
    runtime_sec = round(time.perf_counter() - start_perf, 3)

    history = RefreshHistory(
        job_id=job_id,
        new_creators_count=new_creators,
        updated_creators_count=updated_creators,
        unchanged_records_count=unchanged_records,
        stale_evidence_count=stale_evidence_count,
        invalidated_qualifications_count=invalidated_qualifications,
        duplicates_prevented_count=duplicates_prevented,
        api_calls_used=max(0, api_count_after - api_count_before),
        runtime_seconds=runtime_sec,
        details={
            "checked_at": now.isoformat(),
            "total_creators_in_db": len(all_creators) + new_creators,
        },
        executed_at=now,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


def verify_creator_qualification_preserving_evidence_dates(
    db: Session,
    creator: Creator,
    reference_now: datetime,
) -> None:
    """Re-evaluate whether a creator's existing evidence is still fresh within 30 days and activities within 30d/60d."""
    cutoff_30d = reference_now - timedelta(days=30)
    cutoff_60d = reference_now - timedelta(days=60)

    evidences = db.query(Evidence).filter(Evidence.creator_id == creator.id).all()
    has_stale = any(
        (ev.checked_at if ev.checked_at.tzinfo else ev.checked_at.replace(tzinfo=timezone.utc)) < cutoff_30d
        for ev in evidences
    )

    items_30d = 0
    longform_60d = 0
    for item in creator.content_items:
        pub = item.published_at if item.published_at.tzinfo else item.published_at.replace(tzinfo=timezone.utc)
        if pub >= cutoff_30d:
            items_30d += 1
        if pub >= cutoff_60d and (item.is_longform or item.duration_seconds >= 600):
            longform_60d += 1

    creator.items_30d = items_30d
    creator.longform_60d = longform_60d
    active_ok = (items_30d >= 8) or (longform_60d >= 2)

    if has_stale or not active_ok:
        creator.qualification_status = "NEEDS_REVIEW"
        creator.priority_tier = None
        creator.rank_position = None
    db.flush()
