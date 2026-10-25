from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.agents.agent3.seed_testing import SeedTestLabService
from backend.app.database.models import ReplyEvent, SeedTestRun, TrackingEvent


def log_seed_tracking_event(
    db: Session,
    token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> TrackingEvent | None:
    return SeedTestLabService.record_tracking_click(
        db=db,
        tracking_token=token,
        user_agent=user_agent,
        ip_address=ip_address,
    )


def log_seed_reply(
    db: Session,
    seed_test_run_id: str,
    sender_address: str,
    reply_text: str,
    evidence_path_or_url: str | None = None,
    is_genuine_external_reply: bool = False,
) -> ReplyEvent:
    return SeedTestLabService.record_reply_event(
        db=db,
        seed_test_run_id=seed_test_run_id,
        sender_address=sender_address,
        reply_text=reply_text,
        evidence_path_or_url=evidence_path_or_url,
        is_genuine_external_reply=is_genuine_external_reply,
    )


def ensure_default_seed_test_records(db: Session) -> list[SeedTestRun]:
    """Ensure controlled DRY_RUN seed test records exist across all 3 required channels (email, linkedin, instagram)."""
    existing = db.query(SeedTestRun).all()
    if len(existing) >= 3:
        return existing

    defaults = [
        (
            "email",
            "seedtest.owner@example.org",
            "DRY_RUN Seed Test — Email Step 1 sequence with tracking link and opt-out verification.",
        ),
        (
            "linkedin",
            "https://www.linkedin.com/in/incubrix-seedtest-owner",
            "DRY_RUN Seed Test — LinkedIn personalised connection/message sequence verification.",
        ),
        (
            "instagram",
            "@incubrix_seedtest_owner",
            "DRY_RUN Seed Test — Instagram business profile DM sequence verification.",
        ),
    ]
    created: list[SeedTestRun] = []
    for ch, addr, preview in defaults:
        if not any(r.channel == ch for r in existing):
            run = SeedTestLabService.schedule_or_execute_seed_test(
                db=db,
                channel=ch,
                recipient_address=addr,
                message_preview=preview,
                execution_mode="DRY_RUN",
                explicit_approval=False,
                simulate_failure_recovery=(ch == "email"),
            )
            created.append(run)
    return db.query(SeedTestRun).all()
