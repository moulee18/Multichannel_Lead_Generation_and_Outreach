from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.database.models import Evidence


def upsert_evidence(
    db: Session,
    creator_id: str,
    criterion: str,
    source_url: str,
    excerpt: str,
    verification_status: str = "VERIFIED",
    verification_method: str = "deterministic_adapter",
    source_published_at: datetime | None = None,
    checked_at: datetime | None = None,
    reviewer_notes: str | None = None,
) -> Evidence:
    """Create or update an Evidence record while strictly preserving manually reviewed overrides."""
    now = checked_at or datetime.now(timezone.utc)
    existing = (
        db.query(Evidence)
        .filter(Evidence.creator_id == creator_id, Evidence.criterion == criterion)
        .first()
    )
    if existing:
        if existing.is_manual_override:
            # Never overwrite manually reviewed evidence silently
            return existing
        existing.source_url = source_url
        existing.excerpt = excerpt
        existing.verification_status = verification_status
        existing.verification_method = verification_method
        existing.source_published_at = source_published_at
        existing.checked_at = now
        if reviewer_notes:
            existing.reviewer_notes = reviewer_notes
        db.flush()
        return existing

    ev = Evidence(
        creator_id=creator_id,
        criterion=criterion,
        source_url=source_url,
        excerpt=excerpt,
        source_published_at=source_published_at,
        checked_at=now,
        verification_method=verification_method,
        verification_status=verification_status,
        is_manual_override=False,
        reviewer_notes=reviewer_notes,
    )
    db.add(ev)
    db.flush()
    return ev
