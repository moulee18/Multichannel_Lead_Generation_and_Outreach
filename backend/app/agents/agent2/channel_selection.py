from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database.models import ChannelDecision, ContactChannel, Creator


CHANNEL_PREFERENCE_ORDER = {
    "email": 1,
    "linkedin": 2,
    "instagram": 3,
    "x": 4,
    "website_contact": 5,
}


def select_creator_channels(db: Session, creator: Creator) -> ChannelDecision | None:
    """Feature 5 — Contact Channel Explainer.
    Selects the best verified primary channel and verified backup channel (never invents a backup).
    Records selection rationale, supporting evidence, restrictions, and rejected channels.
    """
    settings = get_settings()
    policies = settings.load_json_config("channel_policies.json").get("channels", {})
    all_contacts = (
        db.query(ContactChannel)
        .filter(ContactChannel.creator_id == creator.id)
        .all()
    )

    eligible: list[ContactChannel] = []
    rejected: list[dict[str, Any]] = []

    for c in all_contacts:
        if not c.is_verified:
            rejected.append(
                {
                    "channel_type": c.channel_type,
                    "handle_or_address": c.handle_or_address,
                    "reason": "Channel is not verified from a public source.",
                }
            )
            continue
        if not c.is_business_contact:
            rejected.append(
                {
                    "channel_type": c.channel_type,
                    "handle_or_address": c.handle_or_address,
                    "reason": "Channel is not designated for public business inquiries.",
                }
            )
            continue
        if not c.active_within_60d:
            rejected.append(
                {
                    "channel_type": c.channel_type,
                    "handle_or_address": c.handle_or_address,
                    "reason": "Creator lacks verified activity within the last 60 days on this profile.",
                }
            )
            continue
        eligible.append(c)

    # Also document candidate channels not present on creator profile
    present_types = {c.channel_type for c in all_contacts}
    for candidate_ch in ("email", "linkedin", "instagram", "x"):
        if candidate_ch not in present_types:
            rejected.append(
                {
                    "channel_type": candidate_ch,
                    "handle_or_address": "Not publicly listed",
                    "reason": f"No public business {candidate_ch} handle/address found on official profile (never guessed).",
                }
            )

    if not eligible:
        return None

    eligible.sort(key=lambda c: CHANNEL_PREFERENCE_ORDER.get(c.channel_type, 99))
    primary = eligible[0]

    # Select backup from a distinct channel_type if available, else second eligible contact
    backup: ContactChannel | None = None
    for cand in eligible[1:]:
        if cand.channel_type != primary.channel_type:
            backup = cand
            break
    if backup is None and len(eligible) > 1:
        backup = eligible[1]

    # Any remaining eligible channels not chosen as primary or backup are noted
    for extra in eligible:
        if extra.id not in {primary.id, getattr(backup, "id", None)}:
            rejected.append(
                {
                    "channel_type": extra.channel_type,
                    "handle_or_address": extra.handle_or_address,
                    "reason": f"Verified, but ranked lower than primary ({primary.channel_type}) and backup ({backup.channel_type if backup else 'none'}).",
                }
            )

    primary_policy = policies.get(primary.channel_type, {})
    backup_policy = policies.get(backup.channel_type, {}) if backup else {}

    reason = (
        f"Selected '{primary.channel_type}' ({primary.handle_or_address}) as Primary because it is publicly listed "
        f"for business contact, supported by creator activity within 60 days, and offers the highest B2B deliverability. "
    )
    if backup:
        reason += (
            f"Selected '{backup.channel_type}' ({backup.handle_or_address}) as Verified Backup for multi-channel follow-up."
        )
    else:
        reason += "No second verified business contact channel exists; backup left empty per anti-guessing rules."

    restrictions = primary_policy.get(
        "policy_notes", "Include sender identity and opt-out; respect platform terms."
    )
    if backup and backup_policy.get("policy_notes"):
        restrictions += f" | Backup ({backup.channel_type}): {backup_policy['policy_notes']}"

    evidence_ids = [eid for eid in (primary.evidence_id, backup.evidence_id if backup else None) if eid]

    existing = db.query(ChannelDecision).filter(ChannelDecision.creator_id == creator.id).first()
    if existing:
        existing.primary_channel = primary.channel_type
        existing.primary_contact_value = primary.handle_or_address
        existing.primary_contact_url = primary.public_url
        existing.backup_channel = backup.channel_type if backup else None
        existing.backup_contact_value = backup.handle_or_address if backup else None
        existing.backup_contact_url = backup.public_url if backup else None
        existing.selection_reason = reason
        existing.supporting_evidence_ids = evidence_ids
        existing.restrictions = restrictions
        existing.rejected_channels = rejected
        existing.decided_at = datetime.now(timezone.utc)
        db.flush()
        return existing

    decision = ChannelDecision(
        creator_id=creator.id,
        primary_channel=primary.channel_type,
        primary_contact_value=primary.handle_or_address,
        primary_contact_url=primary.public_url,
        backup_channel=backup.channel_type if backup else None,
        backup_contact_value=backup.handle_or_address if backup else None,
        backup_contact_url=backup.public_url if backup else None,
        selection_reason=reason,
        supporting_evidence_ids=evidence_ids,
        restrictions=restrictions,
        rejected_channels=rejected,
    )
    db.add(decision)
    db.flush()
    return decision
