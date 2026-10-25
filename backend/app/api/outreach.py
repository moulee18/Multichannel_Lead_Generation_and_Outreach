from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.agents.agent2.outreach import generate_outreach_for_creator
from backend.app.config import get_settings
from backend.app.database.models import (
    ChannelDecision,
    Creator,
    Evidence,
    OutreachMessage,
    OutreachVersion,
    ProductCapability,
    User,
)
from backend.app.database.session import get_db
from backend.app.llm.validator import AIHallucinationGuard
from backend.app.schemas.api_schemas import (
    OutreachGenerateRequest,
    OutreachMessagePatch,
    OutreachMessageReviewRequest,
)
from backend.app.security.auth import get_current_user

router = APIRouter(prefix="/api/outreach", tags=["Outreach Studio"])


def _serialize_message(m: OutreachMessage) -> dict:
    return {
        "id": m.id,
        "creator_id": m.creator_id,
        "channel": m.channel,
        "step_number": m.step_number,
        "step_label": m.step_label,
        "subject": m.subject,
        "body": m.body,
        "referenced_content_title": m.referenced_content_title,
        "referenced_content_url": m.referenced_content_url,
        "referenced_capability_keys": m.referenced_capability_keys,
        "cited_evidence_ids": m.cited_evidence_ids,
        "sender_identity": m.sender_identity,
        "opt_out_text": m.opt_out_text,
        "validation_passed": m.validation_passed,
        "validation_flags": m.validation_flags,
        "approval_status": m.approval_status,
        "version_number": m.version_number,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        "versions": [
            {
                "version_number": v.version_number,
                "edited_by": v.edited_by,
                "edit_notes": v.edit_notes,
                "validation_passed": v.validation_passed,
                "validation_flags": v.validation_flags,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in m.versions
        ],
    }


@router.post("/generate")
def generate_outreach_endpoint(
    payload: OutreachGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.creator_id:
        creator = db.query(Creator).filter(Creator.id == payload.creator_id).first()
        if not creator:
            raise HTTPException(status_code=404, detail=f"Creator '{payload.creator_id}' not found.")
        msgs = generate_outreach_for_creator(
            db,
            creator,
            channels=payload.channels,
            force_regenerate=payload.force_regenerate,
        )
        db.commit()
        return {"generated_count": len(msgs), "messages": [_serialize_message(m) for m in msgs]}

    # Otherwise generate for all Priority A creators
    priority_a = (
        db.query(Creator)
        .filter(Creator.qualification_status == "QUALIFIED", Creator.priority_tier == "Priority A")
        .all()
    )
    total_msgs = 0
    for c in priority_a:
        msgs = generate_outreach_for_creator(
            db,
            c,
            channels=payload.channels,
            force_regenerate=payload.force_regenerate,
        )
        total_msgs += len(msgs)
    db.commit()
    return {"creators_processed": len(priority_a), "generated_count": total_msgs}


@router.get("/creators/{creator_id}")
def get_creator_outreach(
    creator_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.query(Creator).filter(Creator.id == creator_id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Creator '{creator_id}' not found.")
    decision = db.query(ChannelDecision).filter(ChannelDecision.creator_id == creator_id).first()
    msgs = (
        db.query(OutreachMessage)
        .filter(OutreachMessage.creator_id == creator_id)
        .order_by(OutreachMessage.channel.asc(), OutreachMessage.step_number.asc())
        .all()
    )
    return {
        "creator_id": c.id,
        "creator_name": c.name,
        "category": c.category,
        "priority_tier": c.priority_tier,
        "primary_channel": decision.primary_channel if decision else None,
        "backup_channel": decision.backup_channel if decision else None,
        "messages": [_serialize_message(m) for m in msgs],
    }


@router.patch("/messages/{message_id}")
def update_outreach_message(
    message_id: str,
    payload: OutreachMessagePatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    m = db.query(OutreachMessage).filter(OutreachMessage.id == message_id).first()
    if not m:
        raise HTTPException(status_code=404, detail=f"Message '{message_id}' not found.")
    creator = m.creator
    settings = get_settings()
    policies = settings.load_json_config("channel_policies.json").get("channels", {})
    max_len = int(policies.get(m.channel, {}).get("max_length", 1500))
    evidences = db.query(Evidence).filter(Evidence.creator_id == m.creator_id).all()
    capabilities = db.query(ProductCapability).filter(ProductCapability.confirmed.is_(True)).all()

    passed, flags = AIHallucinationGuard.validate_outreach_message(
        creator=creator,
        body=payload.body,
        subject=payload.subject if payload.subject is not None else m.subject,
        channel=m.channel,
        referenced_content_title=m.referenced_content_title,
        referenced_content_url=m.referenced_content_url,
        referenced_capability_keys=m.referenced_capability_keys,
        cited_evidence_ids=m.cited_evidence_ids,
        sender_identity=m.sender_identity,
        opt_out_text=m.opt_out_text,
        evidence_list=evidences,
        capabilities=capabilities,
        max_length=max_len,
    )

    if payload.subject is not None:
        m.subject = payload.subject
    m.body = payload.body
    m.validation_passed = passed
    m.validation_flags = flags
    m.approval_status = "APPROVED" if passed else "NEEDS_REVIEW"
    m.version_number += 1
    m.updated_at = datetime.now(timezone.utc)

    db.add(
        OutreachVersion(
            message_id=m.id,
            version_number=m.version_number,
            subject=m.subject,
            body=m.body,
            edited_by=user.username,
            edit_notes=payload.edit_notes,
            validation_passed=passed,
            validation_flags=flags,
        )
    )
    db.commit()
    db.refresh(m)
    return _serialize_message(m)


@router.post("/messages/{message_id}/review")
def review_outreach_message(
    message_id: str,
    payload: OutreachMessageReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    m = db.query(OutreachMessage).filter(OutreachMessage.id == message_id).first()
    if not m:
        raise HTTPException(status_code=404, detail=f"Message '{message_id}' not found.")

    if payload.approval_status == "APPROVED" and not m.validation_passed:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "HALLUCINATION_GUARD_BLOCK",
                "message": "Cannot approve a message that has unresolved AI Hallucination Guard flags.",
                "flags": m.validation_flags,
            },
        )
    m.approval_status = payload.approval_status
    m.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(m)
    return _serialize_message(m)
