from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.agents.agent1.verification import verify_creator_qualification
from backend.app.agents.agent2.channel_selection import select_creator_channels
from backend.app.agents.agent2.scoring import score_and_rank_qualified_leads
from backend.app.database.models import (
    ChannelDecision,
    ContactChannel,
    Creator,
    CreatorIntelligence,
    Evidence,
    LeadScore,
    ManualReview,
    User,
    VerificationResult,
)
from backend.app.database.session import get_db
from backend.app.schemas.api_schemas import ManualReviewRequest
from backend.app.security.auth import get_current_user

router = APIRouter(prefix="/api/creators", tags=["Creators & Evidence Passport"])


def _serialize_creator_summary(db: Session, c: Creator) -> dict:
    score_obj = db.query(LeadScore).filter(LeadScore.creator_id == c.id).first()
    decision = db.query(ChannelDecision).filter(ChannelDecision.creator_id == c.id).first()
    verif = db.query(VerificationResult).filter(VerificationResult.creator_id == c.id).first()
    return {
        "id": c.id,
        "platform": c.platform,
        "platform_id": c.platform_id,
        "name": c.name,
        "handle": c.handle,
        "official_url": c.official_url,
        "category": c.category,
        "niche": c.niche,
        "country": c.country,
        "language": c.language,
        "subscriber_count": c.subscriber_count,
        "items_30d": c.items_30d,
        "longform_60d": c.longform_60d,
        "qualification_status": c.qualification_status,
        "priority_tier": c.priority_tier,
        "rank_position": c.rank_position,
        "lead_score": score_obj.total_score if score_obj else None,
        "primary_channel": decision.primary_channel if decision else None,
        "primary_contact": decision.primary_contact_value if decision else None,
        "backup_channel": decision.backup_channel if decision else None,
        "backup_contact": decision.backup_contact_value if decision else None,
        "uncertain_criteria": verif.uncertain_criteria if verif else [],
        "failed_criteria": verif.failed_criteria if verif else [],
        "is_synthetic": c.is_synthetic,
        "discovery_source": c.discovery_source,
        "last_checked_at": c.last_checked_at.isoformat() if c.last_checked_at else None,
    }


@router.get("")
def list_creators(
    search: str | None = None,
    status: str | None = None,
    country: str | None = None,
    category: str | None = None,
    priority_tier: str | None = None,
    is_synthetic: bool | None = None,
    sort_by: str = Query(default="rank", pattern="^(rank|name|country|items_30d|updated_at)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Creator)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Creator.name.ilike(s),
                Creator.platform_id.ilike(s),
                Creator.niche.ilike(s),
                Creator.handle.ilike(s),
            )
        )
    if status:
        query = query.filter(Creator.qualification_status == status)
    if country:
        query = query.filter(Creator.country == country)
    if category:
        query = query.filter(Creator.category == category)
    if priority_tier:
        query = query.filter(Creator.priority_tier == priority_tier)
    if is_synthetic is not None:
        query = query.filter(Creator.is_synthetic == is_synthetic)

    total = query.count()

    if sort_by == "name":
        query = query.order_by(Creator.name.asc())
    elif sort_by == "country":
        query = query.order_by(Creator.country.asc(), Creator.name.asc())
    elif sort_by == "items_30d":
        query = query.order_by(Creator.items_30d.desc())
    elif sort_by == "updated_at":
        query = query.order_by(Creator.updated_at.desc())
    else:
        query = query.order_by(Creator.rank_position.is_(None), Creator.rank_position.asc(), Creator.name.asc())

    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize_creator_summary(db, c) for c in items],
    }


@router.get("/{creator_id}")
def get_creator_detail(
    creator_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.query(Creator).filter(Creator.id == creator_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Creator '{creator_id}' not found.")
    summary = _serialize_creator_summary(db, c)
    summary["description"] = c.description
    summary["content_items"] = [
        {
            "id": ci.id,
            "external_id": ci.external_id,
            "title": ci.title,
            "url": ci.url,
            "content_type": ci.content_type,
            "published_at": ci.published_at.isoformat() if ci.published_at else None,
            "duration_seconds": ci.duration_seconds,
            "is_longform": ci.is_longform,
            "view_count": ci.view_count,
        }
        for ci in c.content_items
    ]
    return summary


@router.get("/{creator_id}/evidence")
def get_lead_evidence_passport(
    creator_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Feature 1 — Lead Evidence Passport.
    Returns full creator identity, qualification status, activity counts, commercial/workflow evidence,
    primary/backup contacts, supporting source URLs, timestamps, scoring rationale, and review history.
    """
    c = db.query(Creator).filter(Creator.id == creator_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Creator '{creator_id}' not found.")

    evidences = db.query(Evidence).filter(Evidence.creator_id == c.id).order_by(Evidence.checked_at.desc()).all()
    verif = db.query(VerificationResult).filter(VerificationResult.creator_id == c.id).first()
    contacts = db.query(ContactChannel).filter(ContactChannel.creator_id == c.id).all()
    decision = db.query(ChannelDecision).filter(ChannelDecision.creator_id == c.id).first()
    score_obj = db.query(LeadScore).filter(LeadScore.creator_id == c.id).first()
    intel = db.query(CreatorIntelligence).filter(CreatorIntelligence.creator_id == c.id).first()
    reviews = db.query(ManualReview).filter(ManualReview.creator_id == c.id).order_by(ManualReview.created_at.desc()).all()

    return {
        "passport_version": "1.0.0",
        "creator": {
            "id": c.id,
            "name": c.name,
            "platform": c.platform,
            "platform_id": c.platform_id,
            "handle": c.handle,
            "official_url": c.official_url,
            "category": c.category,
            "niche": c.niche,
            "country": c.country,
            "language": c.language,
            "qualification_status": c.qualification_status,
            "priority_tier": c.priority_tier,
            "rank_position": c.rank_position,
            "is_synthetic": c.is_synthetic,
            "discovery_source": c.discovery_source,
            "items_30d": c.items_30d,
            "longform_60d": c.longform_60d,
            "last_checked_at": c.last_checked_at.isoformat() if c.last_checked_at else None,
        },
        "verification": {
            "overall_status": verif.overall_status if verif else c.qualification_status,
            "real_and_relevant": verif.real_and_relevant if verif else False,
            "active_check": verif.active_check if verif else False,
            "commercial_check": verif.commercial_check if verif else False,
            "needs_incubrix_check": verif.needs_incubrix_check if verif else False,
            "country_check": verif.country_check if verif else False,
            "language_check": verif.language_check if verif else False,
            "reachable_check": verif.reachable_check if verif else False,
            "freshness_check": verif.freshness_check if verif else False,
            "failed_criteria": verif.failed_criteria if verif else [],
            "uncertain_criteria": verif.uncertain_criteria if verif else [],
            "summary_notes": verif.summary_notes if verif else "",
        },
        "evidence_claims": [
            {
                "id": ev.id,
                "criterion": ev.criterion,
                "source_url": ev.source_url,
                "excerpt": ev.excerpt,
                "source_published_at": ev.source_published_at.isoformat() if ev.source_published_at else None,
                "checked_at": ev.checked_at.isoformat() if ev.checked_at else None,
                "verification_method": ev.verification_method,
                "verification_status": ev.verification_status,
                "is_manual_override": ev.is_manual_override,
                "reviewer_notes": ev.reviewer_notes,
            }
            for ev in evidences
        ],
        "contacts": [
            {
                "id": ct.id,
                "channel_type": ct.channel_type,
                "handle_or_address": ct.handle_or_address,
                "public_url": ct.public_url,
                "is_business_contact": ct.is_business_contact,
                "is_verified": ct.is_verified,
                "active_within_60d": ct.active_within_60d,
                "restrictions": ct.restrictions,
                "evidence_id": ct.evidence_id,
            }
            for ct in contacts
        ],
        "channel_decision": {
            "primary_channel": decision.primary_channel if decision else None,
            "primary_contact_value": decision.primary_contact_value if decision else None,
            "primary_contact_url": decision.primary_contact_url if decision else None,
            "backup_channel": decision.backup_channel if decision else None,
            "backup_contact_value": decision.backup_contact_value if decision else None,
            "backup_contact_url": decision.backup_contact_url if decision else None,
            "selection_reason": decision.selection_reason if decision else None,
            "restrictions": decision.restrictions if decision else None,
            "rejected_channels": decision.rejected_channels if decision else [],
        },
        "scoring_rationale": {
            "scoring_version": score_obj.scoring_version if score_obj else "1.0.0",
            "total_score": score_obj.total_score if score_obj else 0.0,
            "priority_tier": score_obj.priority_tier if score_obj else None,
            "rank_position": score_obj.rank_position if score_obj else None,
            "breakdown": score_obj.breakdown if score_obj else [],
        },
        "intelligence": {
            "niche_summary": intel.niche_summary if intel else None,
            "recent_content_topics": intel.recent_content_topics if intel else [],
            "production_workflow": intel.production_workflow if intel else None,
            "pain_points": intel.pain_points if intel else [],
            "suitable_capabilities": intel.suitable_capabilities if intel else [],
            "hallucination_guard_passed": intel.hallucination_guard_passed if intel else True,
            "hallucination_flags": intel.hallucination_flags if intel else [],
        },
        "review_history": [
            {
                "id": r.id,
                "reviewer_username": r.reviewer_username,
                "previous_status": r.previous_status,
                "new_status": r.new_status,
                "criterion_overrides": r.criterion_overrides,
                "notes": r.notes,
                "evidence_url": r.evidence_url,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ],
    }


@router.post("/{creator_id}/review")
def submit_manual_creator_review(
    creator_id: str,
    payload: ManualReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.query(Creator).filter(Creator.id == creator_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Creator '{creator_id}' not found.")

    prev_status = c.qualification_status
    now = datetime.now(timezone.utc)

    if payload.country_override:
        c.country = payload.country_override.strip()

    # Apply manual criterion overrides as protected Evidence records (is_manual_override=True)
    for crit, excerpt_text in payload.criterion_overrides.items():
        if not excerpt_text:
            continue
        existing_ev = (
            db.query(Evidence)
            .filter(Evidence.creator_id == c.id, Evidence.criterion == crit)
            .first()
        )
        if existing_ev:
            existing_ev.excerpt = excerpt_text
            existing_ev.source_url = payload.evidence_url or existing_ev.source_url or c.official_url
            existing_ev.verification_status = "VERIFIED" if payload.new_status == "QUALIFIED" else payload.new_status
            existing_ev.verification_method = "human_reviewer_override"
            existing_ev.is_manual_override = True
            existing_ev.reviewer_notes = payload.notes
            existing_ev.checked_at = now
        else:
            db.add(
                Evidence(
                    creator_id=c.id,
                    criterion=crit,
                    source_url=payload.evidence_url or c.official_url,
                    excerpt=excerpt_text,
                    checked_at=now,
                    verification_method="human_reviewer_override",
                    verification_status="VERIFIED" if payload.new_status == "QUALIFIED" else payload.new_status,
                    is_manual_override=True,
                    reviewer_notes=payload.notes,
                )
            )

    db.flush()
    verify_creator_qualification(db, c, reference_now=now)
    # Apply explicit reviewer status decision if all required evidence exists or if rejecting/sending to review
    if payload.new_status in ("REJECTED", "NEEDS_REVIEW"):
        c.qualification_status = payload.new_status
    elif payload.new_status == "QUALIFIED":
        c.qualification_status = "QUALIFIED"

    review_rec = ManualReview(
        creator_id=c.id,
        reviewer_username=user.username,
        previous_status=prev_status,
        new_status=c.qualification_status,
        criterion_overrides=payload.criterion_overrides,
        notes=payload.notes,
        evidence_url=payload.evidence_url,
        created_at=now,
    )
    db.add(review_rec)
    db.commit()

    if c.qualification_status == "QUALIFIED":
        score_and_rank_qualified_leads(db)
        select_creator_channels(db, c)
        db.commit()

    return get_lead_evidence_passport(creator_id=c.id, db=db, user=user)
