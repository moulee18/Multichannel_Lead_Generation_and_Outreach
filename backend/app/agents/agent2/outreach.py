from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database.models import (
    ChannelDecision,
    Creator,
    CreatorIntelligence,
    Evidence,
    OutreachMessage,
    OutreachVersion,
    ProductCapability,
)
from backend.app.llm.provider import SharedLLMProvider
from backend.app.llm.validator import AIHallucinationGuard


def generate_outreach_for_creator(
    db: Session,
    creator: Creator,
    channels: list[str] | None = None,
    llm_provider: SharedLLMProvider | None = None,
    force_regenerate: bool = False,
) -> list[OutreachMessage]:
    """Generate 3-step personalised outreach sequences across target channels (Email + 2 others for Priority A)."""
    settings = get_settings()
    policies = settings.load_json_config("channel_policies.json").get("channels", {})
    capabilities = db.query(ProductCapability).filter(ProductCapability.confirmed.is_(True)).all()
    evidence_list = db.query(Evidence).filter(Evidence.creator_id == creator.id).all()
    decision = db.query(ChannelDecision).filter(ChannelDecision.creator_id == creator.id).first()
    intel = db.query(CreatorIntelligence).filter(CreatorIntelligence.creator_id == creator.id).first()

    # Determine target channels: always ensure at least 3 channels (email, linkedin, instagram) are supported
    if channels:
        target_channels = channels
    else:
        target_channels = ["email", "linkedin", "instagram"]
        if decision and decision.primary_channel not in target_channels:
            target_channels.insert(0, decision.primary_channel)
        if decision and decision.backup_channel and decision.backup_channel not in target_channels:
            target_channels.append(decision.backup_channel)

    # Pick latest content item for specific personalisation
    recent_items = sorted(
        creator.content_items,
        key=lambda x: x.published_at if x.published_at.tzinfo else x.published_at.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    if recent_items:
        ref_title = recent_items[0].title
        ref_url = recent_items[0].url
    else:
        ref_title = creator.name
        ref_url = creator.official_url

    need_ev = next((e for e in evidence_list if e.criterion == "needs_incubrix"), None)
    comm_ev = next((e for e in evidence_list if e.criterion == "commercial_activity"), None)
    act_ev = next((e for e in evidence_list if e.criterion == "active_publishing"), None)
    cited_ids = [e.id for e in (need_ev, comm_ev, act_ev) if e is not None]
    if not cited_ids and evidence_list:
        cited_ids = [evidence_list[0].id]

    cap_keys = [c.capability_key for c in capabilities[:2]] if capabilities else ["long_to_short_repurposing"]
    cap_names = [c.feature_name for c in capabilities[:2]] if capabilities else ["Long-Form to Short-Form Repurposing Workflow"]
    sender_identity = f"{settings.sender_name} — {settings.sender_role}"

    if need_ev:
        import re as _re
        cleaned_need = _re.sub(r"https?://\S+", "", need_ev.excerpt).strip()
        need_phrase = cleaned_need[:80]
    else:
        need_phrase = "turning long-form episodes into captioned multi-channel short clips"

    generated_messages: list[OutreachMessage] = []

    for channel in target_channels:
        ch_policy = policies.get(channel, policies.get("email", {}))
        max_len = int(ch_policy.get("max_length", 1200))
        opt_out_text = ch_policy.get(
            "opt_out_template",
            "Reply 'stop' or 'opt out' at any time and I will not follow up.",
        )

        steps_data = _build_three_step_sequence(
            creator=creator,
            channel=channel,
            ref_title=ref_title,
            ref_url=ref_url,
            cap_names=cap_names,
            need_phrase=need_phrase,
            sender_identity=sender_identity,
            opt_out_text=opt_out_text,
            max_len=max_len,
            intel=intel,
        )

        for step in steps_data:
            step_num = step["step_number"]
            existing_msg = (
                db.query(OutreachMessage)
                .filter(
                    OutreachMessage.creator_id == creator.id,
                    OutreachMessage.channel == channel,
                    OutreachMessage.step_number == step_num,
                )
                .first()
            )
            if existing_msg and not force_regenerate:
                generated_messages.append(existing_msg)
                continue

            passed, flags = AIHallucinationGuard.validate_outreach_message(
                creator=creator,
                body=step["body"],
                subject=step["subject"],
                channel=channel,
                referenced_content_title=ref_title,
                referenced_content_url=ref_url,
                referenced_capability_keys=cap_keys,
                cited_evidence_ids=cited_ids,
                sender_identity=sender_identity,
                opt_out_text=opt_out_text,
                evidence_list=evidence_list,
                capabilities=capabilities,
                max_length=max_len,
            )

            if existing_msg:
                existing_msg.subject = step["subject"]
                existing_msg.body = step["body"]
                existing_msg.referenced_content_title = ref_title
                existing_msg.referenced_content_url = ref_url
                existing_msg.referenced_capability_keys = cap_keys
                existing_msg.cited_evidence_ids = cited_ids
                existing_msg.sender_identity = sender_identity
                existing_msg.opt_out_text = opt_out_text
                existing_msg.validation_passed = passed
                existing_msg.validation_flags = flags
                existing_msg.version_number += 1
                existing_msg.updated_at = datetime.now(timezone.utc)
                db.flush()

                db.add(
                    OutreachVersion(
                        message_id=existing_msg.id,
                        version_number=existing_msg.version_number,
                        subject=existing_msg.subject,
                        body=existing_msg.body,
                        edited_by="agent2_regenerator",
                        edit_notes="Regenerated sequence draft",
                        validation_passed=passed,
                        validation_flags=flags,
                    )
                )
                generated_messages.append(existing_msg)
            else:
                msg = OutreachMessage(
                    creator_id=creator.id,
                    channel=channel,
                    step_number=step_num,
                    step_label=step["step_label"],
                    subject=step["subject"],
                    body=step["body"],
                    referenced_content_title=ref_title,
                    referenced_content_url=ref_url,
                    referenced_capability_keys=cap_keys,
                    cited_evidence_ids=cited_ids,
                    sender_identity=sender_identity,
                    opt_out_text=opt_out_text,
                    validation_passed=passed,
                    validation_flags=flags,
                    approval_status="APPROVED" if passed else "NEEDS_REVIEW",
                    version_number=1,
                )
                db.add(msg)
                db.flush()

                db.add(
                    OutreachVersion(
                        message_id=msg.id,
                        version_number=1,
                        subject=msg.subject,
                        body=msg.body,
                        edited_by="agent2_generator",
                        edit_notes="Initial evidence-backed draft",
                        validation_passed=passed,
                        validation_flags=flags,
                    )
                )
                generated_messages.append(msg)

    db.flush()
    return generated_messages


def _build_three_step_sequence(
    creator: Creator,
    channel: str,
    ref_title: str,
    ref_url: str,
    cap_names: list[str],
    need_phrase: str,
    sender_identity: str,
    opt_out_text: str,
    max_len: int,
    intel: CreatorIntelligence | None = None,
) -> list[dict[str, Any]]:
    cap_1 = cap_names[0] if cap_names else "Long-Form to Short-Form Repurposing Workflow"
    cap_2 = cap_names[1] if len(cap_names) > 1 else "Editing & Captioning Assistance"

    if channel in ("instagram", "x"):
        # Concise social DM format
        step1_body = (
            f"Hi {creator.name} — watched your recent piece \"{ref_title}\" ({ref_url}). "
            f"Noticed your workflow focus ({need_phrase[:75]}). "
            f"With IncuBrix's {cap_1} and {cap_2}, creators turn each long-form release into captioned short clips without backlog bottlenecks.\n\n"
            f"— {sender_identity}\n{opt_out_text}"
        )
        step2_body = (
            f"Hi {creator.name}, quick follow-up on \"{ref_title}\". "
            f"Would a 3-clip sample workflow mapped to your {creator.category} cadence via IncuBrix ({cap_1}) be useful to review?\n\n"
            f"— {sender_identity}\n{opt_out_text}"
        )
        step3_body = (
            f"Last note from me, {creator.name} — if clearing post-production & captioning work around \"{ref_title}\" becomes a priority this quarter, "
            f"happy to share how IncuBrix supports {cap_2}.\n\n"
            f"— {sender_identity}\n{opt_out_text}"
        )
        return [
            {"step_number": 1, "step_label": "First Contact", "subject": None, "body": step1_body[:max_len]},
            {"step_number": 2, "step_label": "Follow-Up 1 (Day 4)", "subject": None, "body": step2_body[:max_len]},
            {"step_number": 3, "step_label": "Follow-Up 2 (Day 9)", "subject": None, "body": step3_body[:max_len]},
        ]

    # Email / LinkedIn / Website Contact format
    requires_subject = channel in ("email", "website_contact")
    subj_1 = f"Repurposing workflow for {creator.name} (re: {ref_title[:48]})" if requires_subject else None
    subj_2 = f"Re: {ref_title[:42]} — multi-channel clip turnaround" if requires_subject else None
    subj_3 = f"Closing the loop: {creator.name} content workflow" if requires_subject else None

    step1_body = (
        f"Hi {creator.name},\n\n"
        f"I recently reviewed your release \"{ref_title}\" ({ref_url}) and noted your public production context: {need_phrase}.\n\n"
        f"IncuBrix provides confirmed {cap_1} and {cap_2} designed specifically for {creator.category} teams publishing {creator.items_30d}+ recent items—"
        f"helping turn long-form recordings into captioned vertical clips and multi-channel posts while keeping editorial quality intact.\n\n"
        f"Would you be open to a brief 10-minute walkthrough using \"{ref_title}\" as a test case?\n\n"
        f"Best regards,\n{sender_identity}\n{opt_out_text}"
    )

    step2_body = (
        f"Hi {creator.name},\n\n"
        f"Following up on my note regarding \"{ref_title}\" ({ref_url}).\n\n"
        f"Because your channel actively monetises and publishes long-form content ({creator.longform_60d} long-form items in the last 60 days), "
        f"IncuBrix's {cap_1} can eliminate repetitive manual clipping and caption formatting between episodes.\n\n"
        f"Happy to send over a 2-minute breakdown tailored to your workflow if helpful.\n\n"
        f"Best regards,\n{sender_identity}\n{opt_out_text}"
    )

    step3_body = (
        f"Hi {creator.name},\n\n"
        f"Final follow-up from my side regarding \"{ref_title}\". If streamlining {cap_2} and clearing your post-production backlog "
        f"isn't a priority right now, I won't crowd your inbox.\n\n"
        f"If timing improves later this quarter, feel free to reach back out anytime.\n\n"
        f"Best regards,\n{sender_identity}\n{opt_out_text}"
    )

    return [
        {"step_number": 1, "step_label": "First Contact", "subject": subj_1, "body": step1_body[:max_len]},
        {"step_number": 2, "step_label": "Follow-Up 1 (Day 4)", "subject": subj_2, "body": step2_body[:max_len]},
        {"step_number": 3, "step_label": "Follow-Up 2 (Day 9)", "subject": subj_3, "body": step3_body[:max_len]},
    ]
