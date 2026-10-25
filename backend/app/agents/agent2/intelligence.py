from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.database.models import Creator, CreatorIntelligence, Evidence, ProductCapability
from backend.app.llm.prompts import INTELLIGENCE_SYSTEM_PROMPT, build_intelligence_user_prompt
from backend.app.llm.provider import SharedLLMProvider
from backend.app.llm.validator import AIHallucinationGuard


def generate_creator_intelligence(
    db: Session,
    creator: Creator,
    llm_provider: SharedLLMProvider | None = None,
) -> CreatorIntelligence:
    """Analyse recent verified creator information, cite evidence IDs, and validate via AIHallucinationGuard."""
    provider = llm_provider or SharedLLMProvider()
    evidence_list = db.query(Evidence).filter(Evidence.creator_id == creator.id).all()
    capabilities = db.query(ProductCapability).filter(ProductCapability.confirmed.is_(True)).all()

    recent_items = sorted(
        creator.content_items,
        key=lambda x: x.published_at if x.published_at.tzinfo else x.published_at.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:5]
    recent_titles = [item.title for item in recent_items]

    need_ev = next((e for e in evidence_list if e.criterion == "needs_incubrix" and e.verification_status == "VERIFIED"), None)
    comm_ev = next((e for e in evidence_list if e.criterion == "commercial_activity" and e.verification_status == "VERIFIED"), None)
    act_ev = next((e for e in evidence_list if e.criterion == "active_publishing"), None)

    cited_ids = [e.id for e in (need_ev, comm_ev, act_ev) if e is not None]
    if not cited_ids and evidence_list:
        cited_ids = [evidence_list[0].id]

    confirmed_cap_keys = [c.capability_key for c in capabilities]

    pain_points: list[str] = []
    if need_ev:
        pain_points.append(need_ev.excerpt)

    fallback_payload = {
        "niche_summary": f"{creator.category} focused on {creator.niche or 'spoken-word educational and business content'}",
        "recent_content_topics": recent_titles[:3] if recent_titles else [creator.niche or "Creator Content"],
        "production_workflow": (
            f"Publishes {creator.items_30d} content items/30d and {creator.longform_60d} long-form episodes/60d "
            f"on {creator.platform}."
        ),
        "pain_points": pain_points,
        "suitable_capabilities": confirmed_cap_keys[:3],
        "personalisation_hooks": [
            f"Reference recent episode/video: '{recent_titles[0]}'" if recent_titles else f"Reference {creator.name} channel"
        ],
        "cited_evidence_ids": cited_ids,
    }

    user_prompt = build_intelligence_user_prompt(
        creator_name=creator.name,
        category=creator.category,
        recent_titles=recent_titles,
        evidence_items=[{"id": e.id, "criterion": e.criterion, "excerpt": e.excerpt} for e in evidence_list],
        confirmed_capabilities=[{"capability_key": c.capability_key, "feature_name": c.feature_name} for c in capabilities],
    )

    result = provider.generate_json(
        db=db,
        system_prompt=INTELLIGENCE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        fallback_payload=fallback_payload,
        operation="creator_intelligence_analysis",
    )

    # Filter capabilities & evidence IDs if LLM returned unknown keys, then run Hallucination Guard
    passed, flags = AIHallucinationGuard.validate_intelligence(
        creator=creator,
        evidence_list=evidence_list,
        capabilities=capabilities,
        intelligence_payload=result,
    )
    if not passed:
        # Automatically sanitise to deterministic evidence-backed payload while recording the guard audit
        result = {**fallback_payload, "_llm_meta": result.get("_llm_meta", {})}
        passed, flags = AIHallucinationGuard.validate_intelligence(
            creator=creator,
            evidence_list=evidence_list,
            capabilities=capabilities,
            intelligence_payload=result,
        )

    existing = db.query(CreatorIntelligence).filter(CreatorIntelligence.creator_id == creator.id).first()
    used_provider = result.get("_llm_meta", {}).get("provider", "none")

    if existing:
        existing.niche_summary = str(result.get("niche_summary") or fallback_payload["niche_summary"])
        existing.recent_content_topics = list(result.get("recent_content_topics") or fallback_payload["recent_content_topics"])
        existing.production_workflow = str(result.get("production_workflow") or fallback_payload["production_workflow"])
        existing.pain_points = list(result.get("pain_points") or fallback_payload["pain_points"])
        existing.suitable_capabilities = list(result.get("suitable_capabilities") or fallback_payload["suitable_capabilities"])
        existing.personalisation_hooks = list(result.get("personalisation_hooks") or fallback_payload["personalisation_hooks"])
        existing.cited_evidence_ids = list(result.get("cited_evidence_ids") or cited_ids)
        existing.llm_provider_used = used_provider
        existing.hallucination_guard_passed = passed
        existing.hallucination_flags = flags
        existing.generated_at = datetime.now(timezone.utc)
        db.flush()
        return existing

    intel = CreatorIntelligence(
        creator_id=creator.id,
        niche_summary=str(result.get("niche_summary") or fallback_payload["niche_summary"]),
        recent_content_topics=list(result.get("recent_content_topics") or fallback_payload["recent_content_topics"]),
        production_workflow=str(result.get("production_workflow") or fallback_payload["production_workflow"]),
        pain_points=list(result.get("pain_points") or fallback_payload["pain_points"]),
        suitable_capabilities=list(result.get("suitable_capabilities") or fallback_payload["suitable_capabilities"]),
        personalisation_hooks=list(result.get("personalisation_hooks") or fallback_payload["personalisation_hooks"]),
        cited_evidence_ids=list(result.get("cited_evidence_ids") or cited_ids),
        llm_provider_used=used_provider,
        hallucination_guard_passed=passed,
        hallucination_flags=flags,
    )
    db.add(intel)
    db.flush()
    return intel
