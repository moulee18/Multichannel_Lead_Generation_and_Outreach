from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.app.agents.agent3.seed_testing import SeedTestLabService
from backend.app.database.models import SeedTestAccount, SeedTestRun, User
from backend.app.database.session import get_db
from backend.app.schemas.api_schemas import (
    SeedAccountCreateRequest,
    SeedReplyCreateRequest,
    SeedTestCreateRequest,
)
from backend.app.security.auth import get_current_user
from backend.app.services.tracking import (
    ensure_default_seed_test_records,
    log_seed_reply,
    log_seed_tracking_event,
)
from backend.app.utils.errors import GrowthOSError, to_http_exception

router = APIRouter(prefix="/api/seed-tests", tags=["Seed Test Lab"])


def _serialize_seed_run(r: SeedTestRun) -> dict:
    return {
        "id": r.id,
        "test_account_id": r.test_account_id,
        "channel": r.channel,
        "recipient_address": r.recipient_address,
        "execution_mode": r.execution_mode,
        "explicit_approval": r.explicit_approval,
        "status": r.status,
        "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
        "executed_at": r.executed_at.isoformat() if r.executed_at else None,
        "tracking_token": r.tracking_token,
        "tracking_url": r.tracking_url,
        "message_preview": r.message_preview,
        "evidence_attachment_path": r.evidence_attachment_path,
        "is_genuine_external_execution": r.is_genuine_external_execution,
        "execution_logs": r.execution_logs,
        "error_recovery_notes": r.error_recovery_notes,
        "tracking_events": [
            {
                "id": t.id,
                "event_type": t.event_type,
                "user_agent": t.user_agent,
                "ip_address": t.ip_address,
                "is_synthetic": t.is_synthetic,
                "occurred_at": t.occurred_at.isoformat() if t.occurred_at else None,
            }
            for t in r.tracking_events
        ],
        "reply_events": [
            {
                "id": rp.id,
                "sender_address": rp.sender_address,
                "reply_text": rp.reply_text,
                "evidence_path_or_url": rp.evidence_path_or_url,
                "is_genuine_external_reply": rp.is_genuine_external_reply,
                "received_at": rp.received_at.isoformat() if rp.received_at else None,
            }
            for rp in r.reply_events
        ],
    }


@router.get("/accounts/list")
def list_allowlisted_accounts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    accounts = db.query(SeedTestAccount).order_by(SeedTestAccount.channel.asc()).all()
    return {
        "accounts": [
            {
                "id": a.id,
                "label": a.label,
                "channel": a.channel,
                "handle_or_address": a.handle_or_address,
                "owner_name": a.owner_name,
                "is_allowlisted": a.is_allowlisted,
                "ownership_verified": a.ownership_verified,
            }
            for a in accounts
        ]
    }


@router.post("/accounts")
def add_allowlisted_account(
    payload: SeedAccountCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = (
        db.query(SeedTestAccount)
        .filter(
            SeedTestAccount.channel == payload.channel.lower().strip(),
            SeedTestAccount.handle_or_address == payload.handle_or_address.strip(),
        )
        .first()
    )
    if existing:
        return {
            "id": existing.id,
            "label": existing.label,
            "channel": existing.channel,
            "handle_or_address": existing.handle_or_address,
            "owner_name": existing.owner_name,
            "is_allowlisted": existing.is_allowlisted,
        }
    acc = SeedTestAccount(
        label=payload.label,
        channel=payload.channel.lower().strip(),
        handle_or_address=payload.handle_or_address.strip(),
        owner_name=payload.owner_name,
        is_allowlisted=True,
        ownership_verified=True,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return {
        "id": acc.id,
        "label": acc.label,
        "channel": acc.channel,
        "handle_or_address": acc.handle_or_address,
        "owner_name": acc.owner_name,
        "is_allowlisted": acc.is_allowlisted,
    }


@router.post("")
def create_seed_test(
    payload: SeedTestCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        run = SeedTestLabService.schedule_or_execute_seed_test(
            db=db,
            channel=payload.channel,
            recipient_address=payload.recipient_address,
            message_preview=payload.message_preview,
            execution_mode=payload.execution_mode,
            explicit_approval=payload.explicit_approval,
            evidence_attachment_path=payload.evidence_attachment_path,
            simulate_failure_recovery=payload.simulate_failure_recovery,
        )
        return _serialize_seed_run(run)
    except GrowthOSError as exc:
        raise to_http_exception(exc, status_code=403) from exc


@router.get("")
def list_seed_tests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    runs = ensure_default_seed_test_records(db)
    return {"items": [_serialize_seed_run(r) for r in runs]}


@router.get("/{test_id}")
def get_seed_test_detail(
    test_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = db.query(SeedTestRun).filter(SeedTestRun.id == test_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Seed test '{test_id}' not found.")
    return _serialize_seed_run(run)


@router.get("/track/{token}")
def track_seed_test_click(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    ua = request.headers.get("user-agent", "UnknownClient")
    ip = request.client.host if request.client else "127.0.0.1"
    evt = log_seed_tracking_event(db, token=token, user_agent=ua, ip_address=ip)
    if not evt:
        raise HTTPException(status_code=404, detail="Invalid tracking token.")
    return {
        "status": "TRACKING_EVENT_LOGGED",
        "event_id": evt.id,
        "tracking_token": token,
        "is_synthetic": evt.is_synthetic,
        "occurred_at": evt.occurred_at.isoformat() if evt.occurred_at else None,
    }


@router.post("/{test_id}/replies")
def record_seed_test_reply(
    test_id: str,
    payload: SeedReplyCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        reply = log_seed_reply(
            db=db,
            seed_test_run_id=test_id,
            sender_address=payload.sender_address,
            reply_text=payload.reply_text,
            evidence_path_or_url=payload.evidence_path_or_url,
            is_genuine_external_reply=payload.is_genuine_external_reply,
        )
        return {
            "id": reply.id,
            "seed_test_run_id": reply.seed_test_run_id,
            "sender_address": reply.sender_address,
            "reply_text": reply.reply_text,
            "is_genuine_external_reply": reply.is_genuine_external_reply,
            "received_at": reply.received_at.isoformat() if reply.received_at else None,
        }
    except GrowthOSError as exc:
        raise to_http_exception(exc, status_code=400) from exc
