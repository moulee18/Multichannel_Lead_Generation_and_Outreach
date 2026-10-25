from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.agents.agent2.channel_selection import select_creator_channels
from backend.app.agents.agent2.intelligence import generate_creator_intelligence
from backend.app.agents.agent2.outreach import generate_outreach_for_creator
from backend.app.agents.agent2.scoring import (
    compute_creator_score,
    score_and_rank_qualified_leads,
)
from backend.app.database.models import (
    ChannelDecision,
    Creator,
    CreatorIntelligence,
    LeadScore,
    User,
)
from backend.app.database.session import get_db
from backend.app.schemas.api_schemas import IntelligenceRunRequest
from backend.app.security.auth import get_current_user

router = APIRouter(tags=["Lead Intelligence & Scoring"])


def _serialize_lead_row(db: Session, s: LeadScore) -> dict:
    c = s.creator
    decision = db.query(ChannelDecision).filter(ChannelDecision.creator_id == s.creator_id).first()
    intel = db.query(CreatorIntelligence).filter(CreatorIntelligence.creator_id == s.creator_id).first()
    return {
        "creator_id": s.creator_id,
        "creator_name": c.name if c else "Unknown",
        "category": c.category if c else "",
        "niche": c.niche if c else "",
        "country": c.country if c else "",
        "official_url": c.official_url if c else "",
        "is_synthetic": c.is_synthetic if c else False,
        "rank_position": s.rank_position,
        "priority_tier": s.priority_tier,
        "scoring_version": s.scoring_version,
        "total_score": s.total_score,
        "product_relevance_score": s.product_relevance_score,
        "need_evidence_score": s.need_evidence_score,
        "commercial_readiness_score": s.commercial_readiness_score,
        "publishing_activity_score": s.publishing_activity_score,
        "contact_quality_score": s.contact_quality_score,
        "breakdown": s.breakdown,
        "primary_channel": decision.primary_channel if decision else None,
        "primary_contact": decision.primary_contact_value if decision else None,
        "backup_channel": decision.backup_channel if decision else None,
        "backup_contact": decision.backup_contact_value if decision else None,
        "suitable_capabilities": intel.suitable_capabilities if intel else [],
        "pain_points": intel.pain_points if intel else [],
        "hallucination_guard_passed": intel.hallucination_guard_passed if intel else True,
    }


@router.post("/api/intelligence/runs")
def run_lead_intelligence(
    payload: IntelligenceRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scores = score_and_rank_qualified_leads(db)
    processed = 0
    for s in scores:
        if payload.creator_ids and s.creator_id not in payload.creator_ids:
            continue
        if s.creator:
            select_creator_channels(db, s.creator)
            generate_creator_intelligence(db, s.creator)
            if payload.regenerate_outreach or s.priority_tier == "Priority A":
                generate_outreach_for_creator(
                    db, s.creator, force_regenerate=payload.regenerate_outreach
                )
            processed += 1
    db.commit()
    return {
        "status": "COMPLETED",
        "total_scored": len(scores),
        "processed_intelligence": processed,
        "priority_a_count": sum(1 for s in scores if s.priority_tier == "Priority A"),
    }


@router.get("/api/leads/ranked")
def get_ranked_leads(
    include_synthetic: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scores = (
        db.query(LeadScore)
        .order_by(LeadScore.rank_position.is_(None), LeadScore.rank_position.asc())
        .all()
    )
    rows = []
    for s in scores:
        if not include_synthetic and s.creator and s.creator.is_synthetic:
            continue
        rows.append(_serialize_lead_row(db, s))
    return {"total": len(rows), "items": rows}


@router.get("/api/leads/priority-a")
def get_priority_a_leads(
    include_synthetic: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scores = (
        db.query(LeadScore)
        .filter(LeadScore.priority_tier == "Priority A")
        .order_by(LeadScore.rank_position.asc())
        .all()
    )
    rows = []
    for s in scores:
        if not include_synthetic and s.creator and s.creator.is_synthetic:
            continue
        rows.append(_serialize_lead_row(db, s))
    return {"total": len(rows), "items": rows}


@router.get("/api/leads/{creator_id}/score")
def get_explainable_lead_score(
    creator_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Feature 2 — Explainable Lead Scoring."""
    c = db.query(Creator).filter(Creator.id == creator_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Creator '{creator_id}' not found.")
    score_obj = db.query(LeadScore).filter(LeadScore.creator_id == creator_id).first()
    if not score_obj:
        score_obj = compute_creator_score(db, c)
        db.commit()
    return _serialize_lead_row(db, score_obj)


@router.get("/api/leads/{creator_id}/channels")
def get_contact_channel_explainer(
    creator_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Feature 5 — Contact Channel Explainer."""
    c = db.query(Creator).filter(Creator.id == creator_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Creator '{creator_id}' not found.")
    decision = db.query(ChannelDecision).filter(ChannelDecision.creator_id == creator_id).first()
    if not decision:
        decision = select_creator_channels(db, c)
        db.commit()
    if not decision:
        return {
            "creator_id": creator_id,
            "creator_name": c.name,
            "has_verified_channel": False,
            "message": "No verified public business contact channel active within 60 days.",
        }
    return {
        "creator_id": creator_id,
        "creator_name": c.name,
        "has_verified_channel": True,
        "primary_channel": decision.primary_channel,
        "primary_contact_value": decision.primary_contact_value,
        "primary_contact_url": decision.primary_contact_url,
        "backup_channel": decision.backup_channel,
        "backup_contact_value": decision.backup_contact_value,
        "backup_contact_url": decision.backup_contact_url,
        "selection_reason": decision.selection_reason,
        "supporting_evidence_ids": decision.supporting_evidence_ids,
        "restrictions": decision.restrictions,
        "rejected_channels": decision.rejected_channels,
        "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
    }
