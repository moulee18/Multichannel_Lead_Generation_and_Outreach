from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.database.models import Creator, Evidence, OutreachMessage, ProductCapability
from backend.app.llm.validator import AIHallucinationGuard


def run_outreach_audit(db: Session, include_synthetic: bool = True) -> dict[str, Any]:
    """Audit Priority A outreach sequences for 3-step completeness, 3-channel coverage, and AI Hallucination Guard compliance."""
    query = db.query(Creator).filter(
        Creator.qualification_status == "QUALIFIED",
        Creator.priority_tier == "Priority A",
    )
    if not include_synthetic:
        query = query.filter(Creator.is_synthetic.is_(False))
    priority_a_creators = query.all()

    capabilities = db.query(ProductCapability).filter(ProductCapability.confirmed.is_(True)).all()
    all_messages = db.query(OutreachMessage).all()
    distinct_channels = sorted({m.channel for m in all_messages})

    findings: list[dict[str, Any]] = []
    complete_priority_a_count = 0
    invalid_messages_count = 0

    for creator in priority_a_creators:
        creator_msgs = [m for m in all_messages if m.creator_id == creator.id]
        evidences = db.query(Evidence).filter(Evidence.creator_id == creator.id).all()

        # Check if at least one channel has all 3 steps (First Contact, Follow-up 1, Follow-up 2)
        by_channel: dict[str, set[int]] = {}
        for m in creator_msgs:
            by_channel.setdefault(m.channel, set()).add(m.step_number)

        has_full_3_step = any({1, 2, 3}.issubset(steps) for steps in by_channel.values())
        if has_full_3_step:
            complete_priority_a_count += 1
        else:
            findings.append(
                {
                    "creator_id": creator.id,
                    "category": "OUTREACH_AUDIT",
                    "severity": "ERROR",
                    "passed": False,
                    "rule_code": "MISSING_3_STEP_SEQUENCE",
                    "description": f"Priority A creator '{creator.name}' lacks a complete 3-step sequence (First message + 2 follow-ups).",
                    "evidence_urls": [creator.official_url],
                }
            )

        for m in creator_msgs:
            passed, flags = AIHallucinationGuard.validate_outreach_message(
                creator=creator,
                body=m.body,
                subject=m.subject,
                channel=m.channel,
                referenced_content_title=m.referenced_content_title,
                referenced_content_url=m.referenced_content_url,
                referenced_capability_keys=m.referenced_capability_keys,
                cited_evidence_ids=m.cited_evidence_ids,
                sender_identity=m.sender_identity,
                opt_out_text=m.opt_out_text,
                evidence_list=evidences,
                capabilities=capabilities,
            )
            if not passed:
                invalid_messages_count += 1
                findings.append(
                    {
                        "creator_id": creator.id,
                        "category": "OUTREACH_AUDIT",
                        "severity": "ERROR",
                        "passed": False,
                        "rule_code": "MESSAGE_COMPLIANCE_FAILURE",
                        "description": f"Message {m.id} ({m.channel} step {m.step_number}) failed validation: {flags}",
                        "evidence_urls": [m.referenced_content_url],
                    }
                )

    three_channel_coverage = len(distinct_channels) >= 3 and "email" in distinct_channels
    if not three_channel_coverage:
        findings.append(
            {
                "creator_id": None,
                "category": "OUTREACH_AUDIT",
                "severity": "ERROR",
                "passed": False,
                "rule_code": "CHANNEL_COVERAGE_BELOW_3",
                "description": f"Outreach sequences cover {distinct_channels}; requires 'email' plus at least 2 other channels.",
                "evidence_urls": [],
            }
        )

    compliant = (
        len(priority_a_creators) > 0
        and complete_priority_a_count == len(priority_a_creators)
        and three_channel_coverage
        and invalid_messages_count == 0
    )

    return {
        "priority_a_total": len(priority_a_creators),
        "priority_a_with_complete_sequences": complete_priority_a_count,
        "channels_covered": distinct_channels,
        "three_channel_requirement_met": three_channel_coverage,
        "total_messages_checked": len(all_messages),
        "invalid_messages_count": invalid_messages_count,
        "compliant": compliant,
        "findings": findings,
    }
