from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database.models import ContactChannel, Creator, Evidence, LeadScore


def score_and_rank_qualified_leads(db: Session) -> list[LeadScore]:
    """Compute explainable 100-point scores for all QUALIFIED creators and assign Priority A (top 25), B, and C."""
    settings = get_settings()
    cfg = settings.load_json_config("scoring.json")
    version = cfg.get("version", "1.0.0")
    weights = cfg.get(
        "weights",
        {
            "product_relevance": 30,
            "need_evidence_strength": 25,
            "commercial_readiness": 20,
            "publishing_activity": 15,
            "contact_channel_quality": 10,
        },
    )
    priority_a_limit = int(cfg.get("priority_a_limit", 25))
    priority_b_min = float(cfg.get("priority_b_min_score", 70.0))

    qualified_creators = (
        db.query(Creator)
        .filter(Creator.qualification_status == "QUALIFIED")
        .all()
    )

    computed_scores: list[LeadScore] = []
    for creator in qualified_creators:
        score_obj = compute_creator_score(db, creator, weights=weights, version=version)
        computed_scores.append(score_obj)

    # Sort deterministically: genuine leads first, then total_score DESC, need_evidence_score DESC, platform_id ASC
    computed_scores.sort(
        key=lambda s: (
            (not s.creator.is_synthetic) if s.creator else False,
            round(s.total_score, 4),
            round(s.need_evidence_score, 4),
            s.creator.platform_id if s.creator else "",
        ),
        reverse=True,
    )

    for idx, score_obj in enumerate(computed_scores, start=1):
        score_obj.rank_position = idx
        if idx <= priority_a_limit:
            tier = "Priority A"
        elif score_obj.total_score >= priority_b_min:
            tier = "Priority B"
        else:
            tier = "Priority C"
        score_obj.priority_tier = tier
        if score_obj.creator:
            score_obj.creator.priority_tier = tier
            score_obj.creator.rank_position = idx

    db.commit()
    return computed_scores


def compute_creator_score(
    db: Session,
    creator: Creator,
    weights: dict[str, float] | None = None,
    version: str = "1.0.0",
) -> LeadScore:
    settings = get_settings()
    cfg = settings.load_json_config("scoring.json")
    w = weights or cfg.get(
        "weights",
        {
            "product_relevance": 30,
            "need_evidence_strength": 25,
            "commercial_readiness": 20,
            "publishing_activity": 15,
            "contact_channel_quality": 10,
        },
    )

    ev_map: dict[str, Evidence] = {
        ev.criterion: ev
        for ev in db.query(Evidence).filter(Evidence.creator_id == creator.id).all()
    }
    contacts = (
        db.query(ContactChannel)
        .filter(
            ContactChannel.creator_id == creator.id,
            ContactChannel.is_verified.is_(True),
            ContactChannel.active_within_60d.is_(True),
        )
        .all()
    )

    breakdown: list[dict[str, Any]] = []

    # 1. Product Relevance (Max 30)
    max_rel = float(w.get("product_relevance", 30))
    cat_lower = (creator.category or "").lower()
    if "podcast" in cat_lower or "video" in cat_lower:
        rel_ratio = 1.0
        rel_reason = f"High-fit spoken-word/video segment ({creator.category}) with multi-channel clip potential."
    elif "coach" in cat_lower or "consultant" in cat_lower or "educator" in cat_lower or "expert" in cat_lower:
        rel_ratio = 0.92
        rel_reason = f"Expert-led creator segment ({creator.category}) publishing educational content."
    else:
        rel_ratio = 0.75
        rel_reason = f"Approved creator segment ({creator.category})."
    rel_points = round(max_rel * rel_ratio, 2)
    rel_ev = ev_map.get("real_and_relevant")
    breakdown.append(
        {
            "criterion": "Product Relevance",
            "max_points": max_rel,
            "awarded_points": rel_points,
            "reasoning": rel_reason,
            "evidence_id": rel_ev.id if rel_ev else None,
            "source_url": rel_ev.source_url if rel_ev else creator.official_url,
        }
    )

    # 2. Strength of Need Evidence (Max 25)
    max_need = float(w.get("need_evidence_strength", 25))
    need_ev = ev_map.get("needs_incubrix")
    need_text = (need_ev.excerpt.lower() if need_ev else "") + " " + (creator.description or "").lower()
    high_intent_signals = sum(
        1
        for kw in ("repurpos", "editor", "editing", "backlog", "caption", "shorts", "clips", "workflow")
        if kw in need_text
    )
    if need_ev and need_ev.verification_status == "VERIFIED":
        need_ratio = min(1.0, 0.76 + (0.06 * min(4, high_intent_signals)))
        need_reason = f"Verified workflow/repurposing need with {high_intent_signals} explicit production signal(s)."
    else:
        need_ratio = 0.0
        need_reason = "No verified workflow need evidence."
    need_points = round(max_need * need_ratio, 2)
    breakdown.append(
        {
            "criterion": "Strength of Need Evidence",
            "max_points": max_need,
            "awarded_points": need_points,
            "reasoning": need_reason,
            "evidence_id": need_ev.id if need_ev else None,
            "source_url": need_ev.source_url if need_ev else creator.official_url,
        }
    )

    # 3. Commercial Readiness (Max 20)
    max_comm = float(w.get("commercial_readiness", 20))
    comm_ev = ev_map.get("commercial_activity")
    comm_text = (comm_ev.excerpt.lower() if comm_ev else "") + " " + (creator.description or "").lower()
    comm_signals = sum(
        1
        for kw in ("sponsor", "course", "coaching", "consulting", "membership", "patreon", "newsletter", "program")
        if kw in comm_text
    )
    if comm_ev and comm_ev.verification_status == "VERIFIED":
        comm_ratio = min(1.0, 0.80 + (0.05 * min(4, comm_signals)))
        comm_reason = f"Verified commercial monetization ({comm_signals} active monetization indicator(s))."
    else:
        comm_ratio = 0.0
        comm_reason = "No verified commercial activity."
    comm_points = round(max_comm * comm_ratio, 2)
    breakdown.append(
        {
            "criterion": "Commercial Readiness",
            "max_points": max_comm,
            "awarded_points": comm_points,
            "reasoning": comm_reason,
            "evidence_id": comm_ev.id if comm_ev else None,
            "source_url": comm_ev.source_url if comm_ev else creator.official_url,
        }
    )

    # 4. Publishing Activity (Max 15)
    max_act = float(w.get("publishing_activity", 15))
    act_ev = ev_map.get("active_publishing")
    if creator.items_30d >= 8 and creator.longform_60d >= 2:
        act_ratio = 1.0
        act_reason = f"Satisfies both activity thresholds ({creator.items_30d} items in 30d & {creator.longform_60d} long-form in 60d)."
    elif creator.items_30d >= 8:
        act_ratio = 0.90
        act_reason = f"High-frequency publisher ({creator.items_30d} items in last 30 days)."
    elif creator.longform_60d >= 2:
        act_ratio = 0.85
        act_reason = f"Consistent long-form publisher ({creator.longform_60d} long-form episodes in last 60 days)."
    else:
        act_ratio = 0.0
        act_reason = "Below activity threshold."
    act_points = round(max_act * act_ratio, 2)
    breakdown.append(
        {
            "criterion": "Publishing Activity",
            "max_points": max_act,
            "awarded_points": act_points,
            "reasoning": act_reason,
            "evidence_id": act_ev.id if act_ev else None,
            "source_url": act_ev.source_url if act_ev else creator.official_url,
        }
    )

    # 5. Contact-Channel Quality (Max 10)
    max_ctc = float(w.get("contact_channel_quality", 10))
    channel_types = {c.channel_type for c in contacts}
    if "email" in channel_types and len(channel_types) >= 2:
        ctc_ratio = 1.0
        ctc_reason = f"Verified business email plus {len(channel_types) - 1} verified backup channel(s) ({', '.join(sorted(channel_types))})."
    elif len(channel_types) >= 2:
        ctc_ratio = 0.85
        ctc_reason = f"Multiple verified business channels ({', '.join(sorted(channel_types))})."
    elif len(channel_types) == 1:
        ctc_ratio = 0.70
        ctc_reason = f"Single verified business contact channel ({next(iter(channel_types))}); no verified backup."
    else:
        ctc_ratio = 0.0
        ctc_reason = "No verified business contact channel."
    ctc_points = round(max_ctc * ctc_ratio, 2)
    ctc_ev_id = contacts[0].evidence_id if contacts else None
    breakdown.append(
        {
            "criterion": "Contact-Channel Quality",
            "max_points": max_ctc,
            "awarded_points": ctc_points,
            "reasoning": ctc_reason,
            "evidence_id": ctc_ev_id,
            "source_url": contacts[0].public_url if contacts else creator.official_url,
        }
    )

    total_score = round(rel_points + need_points + comm_points + act_points + ctc_points, 2)

    existing_score = db.query(LeadScore).filter(LeadScore.creator_id == creator.id).first()
    if existing_score:
        existing_score.scoring_version = version
        existing_score.total_score = total_score
        existing_score.product_relevance_score = rel_points
        existing_score.need_evidence_score = need_points
        existing_score.commercial_readiness_score = comm_points
        existing_score.publishing_activity_score = act_points
        existing_score.contact_quality_score = ctc_points
        existing_score.breakdown = breakdown
        existing_score.calculated_at = datetime.now(timezone.utc)
        db.flush()
        return existing_score

    new_score = LeadScore(
        creator_id=creator.id,
        scoring_version=version,
        total_score=total_score,
        product_relevance_score=rel_points,
        need_evidence_score=need_points,
        commercial_readiness_score=comm_points,
        publishing_activity_score=act_points,
        contact_quality_score=ctc_points,
        priority_tier="Priority C",
        breakdown=breakdown,
    )
    db.add(new_score)
    db.flush()
    return new_score
