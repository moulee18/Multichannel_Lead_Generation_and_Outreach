from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.app.agents.agent1.discovery import Agent1DiscoveryEngine
from backend.app.agents.agent2.channel_selection import select_creator_channels
from backend.app.agents.agent2.intelligence import generate_creator_intelligence
from backend.app.agents.agent2.outreach import generate_outreach_for_creator
from backend.app.agents.agent2.scoring import score_and_rank_qualified_leads
from backend.app.database.models import ContactChannel, Creator, Evidence, ProductCapability
from backend.app.database.session import get_session_factory, init_db
from backend.app.llm.provider import SharedLLMProvider
from backend.app.llm.validator import AIHallucinationGuard


@pytest.fixture()
def db_session(tmp_path: Path):
    db_url = f"sqlite:///{(tmp_path / 'test_agent2.db').as_posix()}"
    init_db(db_url)
    SessionLocal = get_session_factory(db_url)
    with SessionLocal() as session:
        yield session


def test_agent2_scoring_ranking_and_priority_a(db_session):
    engine = Agent1DiscoveryEngine()
    run = engine.execute_discovery_run(
        db=db_session,
        keyword="demo",
        source="synthetic_demo",
        run_mode="synthetic_demo",
        max_candidates=35,
    )
    assert run.qualified_count == 30
    assert run.needs_review_count == 4
    assert run.rejected_count == 1

    scores = score_and_rank_qualified_leads(db_session)
    assert len(scores) == 30

    # Verify rank ordering is monotonic non-increasing
    for idx in range(len(scores) - 1):
        assert scores[idx].total_score >= scores[idx + 1].total_score
        assert scores[idx].rank_position == idx + 1

    # Top 25 must be Priority A, remaining 5 Priority B or C
    priority_a = [s for s in scores if s.priority_tier == "Priority A"]
    assert len(priority_a) == 25

    # Verify score breakdown arithmetic sums to total_score
    sample = scores[0]
    component_sum = round(
        sample.product_relevance_score
        + sample.need_evidence_score
        + sample.commercial_readiness_score
        + sample.publishing_activity_score
        + sample.contact_quality_score,
        2,
    )
    assert sample.total_score == component_sum
    assert len(sample.breakdown) == 5


def test_channel_selection_and_missing_backup_never_guessed(db_session):
    now = datetime.now(timezone.utc)
    engine = Agent1DiscoveryEngine()
    creator = engine.ingest_and_verify_candidate(
        db_session,
        {
            "platform": "youtube",
            "platform_id": "UC_SINGLE_CHANNEL",
            "name": "Single Contact Creator",
            "official_url": "https://www.youtube.com/channel/UC_SINGLE_CHANNEL",
            "category": "Podcaster / Video Podcaster",
            "country": "United States",
            "language": "en",
            "description": "Sponsored by PodTool. Need help repurposing episodes into clips. Email: onlyone@podcreator.org",
            "content_items": [
                {
                    "external_id": "ep1",
                    "title": "Episode One",
                    "url": "https://www.youtube.com/watch?v=ep1",
                    "published_at": now,
                    "duration_seconds": 1800,
                    "is_longform": True,
                    "language": "en",
                },
                {
                    "external_id": "ep2",
                    "title": "Episode Two",
                    "url": "https://www.youtube.com/watch?v=ep2",
                    "published_at": now,
                    "duration_seconds": 1800,
                    "is_longform": True,
                    "language": "en",
                },
            ],
        },
        reference_now=now,
    )
    contacts = db_session.query(ContactChannel).filter(ContactChannel.creator_id == creator.id).all()
    assert len(contacts) == 1

    decision = select_creator_channels(db_session, creator)
    assert decision is not None
    assert decision.primary_channel == "email"
    assert decision.backup_channel is None
    assert decision.backup_contact_value is None


def test_outreach_generation_and_hallucination_guard(db_session):
    engine = Agent1DiscoveryEngine()
    engine.execute_discovery_run(
        db=db_session,
        keyword="demo",
        source="synthetic_demo",
        run_mode="synthetic_demo",
        max_candidates=5,
    )
    creator = db_session.query(Creator).filter(Creator.qualification_status == "QUALIFIED").first()
    assert creator is not None

    select_creator_channels(db_session, creator)
    intel = generate_creator_intelligence(db_session, creator)
    assert intel.hallucination_guard_passed is True

    msgs = generate_outreach_for_creator(
        db_session,
        creator,
        channels=["email", "linkedin", "instagram"],
    )
    # 3 channels x 3 steps = 9 messages
    assert len(msgs) == 9
    for m in msgs:
        assert m.validation_passed is True
        assert m.referenced_content_title in m.body
        assert m.opt_out_text.split()[0].lower() in m.body.lower()

    # Now test AI Hallucination Guard catches unsupported product claims, missing opt-out, and invented URLs
    evidences = db_session.query(Evidence).filter(Evidence.creator_id == creator.id).all()
    capabilities = db_session.query(ProductCapability).all()

    passed, flags = AIHallucinationGuard.validate_outreach_message(
        creator=creator,
        body="Hi there, we offer guaranteed viral deepfake avatar generation at https://fake-invented-domain.xyz/offer!",
        subject="Fake Subject",
        channel="email",
        referenced_content_title="Nonexistent Video Title",
        referenced_content_url="https://fake-invented-domain.xyz/video",
        referenced_capability_keys=["unconfirmed_quantum_avatar"],
        cited_evidence_ids=["evd_nonexistent"],
        sender_identity="Arjun Mehta",
        opt_out_text="Reply stop to opt out",
        evidence_list=evidences,
        capabilities=capabilities,
    )
    assert passed is False
    assert any("INVENTED_PRODUCT_CLAIM" in f for f in flags)
    assert any("INVENTED_URL" in f for f in flags)
    assert any("MISSING_OPT_OUT" in f for f in flags)


def test_llm_failure_graceful_fallback(db_session, monkeypatch):
    provider = SharedLLMProvider(provider="openai", model="gpt-4o-mini")
    monkeypatch.setattr(provider.settings, "openai_api_key", "sk-test-fake-key")

    def raise_network_err(*args, **kwargs):
        raise RuntimeError("Simulated OpenAI 503 outage")

    monkeypatch.setattr(provider, "_dispatch_request", raise_network_err)

    res = provider.generate_json(
        db=db_session,
        system_prompt="sys",
        user_prompt="usr",
        fallback_payload={"niche_summary": "Fallback Niche"},
        operation="test_llm_fallback",
    )
    assert res["niche_summary"] == "Fallback Niche"
    assert res["_llm_meta"]["fallback_used"] is True
