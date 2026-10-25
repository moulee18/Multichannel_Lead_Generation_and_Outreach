from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.database.models import (
    ReplyEvent,
    SeedTestAccount,
    SeedTestRun,
    TrackingEvent,
)
from backend.app.security.permissions import enforce_seed_test_allowlist
from backend.app.utils.errors import IntegrityViolationError


class SeedTestLabService:
    """Safe three-channel seed-testing facility with strict participant-owned allowlisting and DRY_RUN default."""

    @staticmethod
    def schedule_or_execute_seed_test(
        db: Session,
        channel: str,
        recipient_address: str,
        message_preview: str,
        execution_mode: str = "DRY_RUN",
        explicit_approval: bool = False,
        evidence_attachment_path: str | None = None,
        simulate_failure_recovery: bool = False,
        base_tracking_url: str = "http://127.0.0.1:8000",
    ) -> SeedTestRun:
        allowlisted_accounts = db.query(SeedTestAccount).all()
        matched_account = enforce_seed_test_allowlist(
            recipient_address=recipient_address,
            channel=channel,
            allowlisted_accounts=allowlisted_accounts,
        )

        mode_upper = execution_mode.strip().upper()
        if mode_upper not in ("DRY_RUN", "MANUAL_COMPLIANT_SEND", "LIVE_TEST_SEND"):
            mode_upper = "DRY_RUN"

        if mode_upper != "DRY_RUN" and not explicit_approval:
            raise IntegrityViolationError(
                message="Explicit approval is required before executing a non-DRY_RUN seed test.",
                details={"execution_mode": mode_upper},
            )

        token = f"seedtrk_{secrets.token_hex(10)}"
        tracking_url = f"{base_tracking_url.rstrip('/')}/api/seed-tests/track/{token}"
        now = datetime.now(timezone.utc)

        logs: list[dict[str, Any]] = [
            {
                "timestamp": now.isoformat(),
                "step": "ALLOWLIST_VERIFIED",
                "detail": f"Recipient '{recipient_address}' verified in participant-owned allowlist ({matched_account.label}).",
            },
            {
                "timestamp": now.isoformat(),
                "step": "TRACKING_LINK_GENERATED",
                "detail": f"Generated unique tracking URL: {tracking_url}",
            },
        ]

        error_recovery_notes = None
        if simulate_failure_recovery:
            logs.append(
                {
                    "timestamp": now.isoformat(),
                    "step": "TRANSIENT_DELIVERY_FAILURE",
                    "detail": f"Simulated rate-limit/timeout on {channel} transport; queued automatic backoff retry #1.",
                }
            )
            logs.append(
                {
                    "timestamp": now.isoformat(),
                    "step": "RECOVERY_SUCCEEDED",
                    "detail": "Retry #1 succeeded with idempotent message token; no duplicate message dispatched.",
                }
            )
            error_recovery_notes = "Recovered from transient delivery error via idempotent retry #1."

        is_genuine = bool(
            mode_upper in ("MANUAL_COMPLIANT_SEND", "LIVE_TEST_SEND")
            and explicit_approval
            and evidence_attachment_path
        )

        if mode_upper == "DRY_RUN":
            status_val = "DRY_RUN_LOGGED"
            logs.append(
                {
                    "timestamp": now.isoformat(),
                    "step": "DRY_RUN_COMPLETE",
                    "detail": "Message validated and logged in DRY_RUN mode. No external network dispatch performed.",
                }
            )
        else:
            status_val = "EXECUTED_WITH_EVIDENCE" if is_genuine else "MANUAL_TEST_PENDING_PROOF"
            logs.append(
                {
                    "timestamp": now.isoformat(),
                    "step": "CONTROLLED_TEST_DISPATCH",
                    "detail": (
                        f"Executed controlled {mode_upper} on owned test account '{recipient_address}'. "
                        f"Genuine external proof attached: {bool(evidence_attachment_path)}."
                    ),
                }
            )

        run = SeedTestRun(
            test_account_id=matched_account.id,
            channel=channel.lower(),
            recipient_address=recipient_address,
            execution_mode=mode_upper,
            explicit_approval=explicit_approval,
            status=status_val,
            scheduled_at=now,
            executed_at=now,
            tracking_token=token,
            tracking_url=tracking_url,
            message_preview=f"{message_preview}\n\n[Seed Test Tracking Link: {tracking_url}]",
            evidence_attachment_path=evidence_attachment_path,
            is_genuine_external_execution=is_genuine,
            execution_logs=logs,
            error_recovery_notes=error_recovery_notes,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def record_tracking_click(
        db: Session,
        tracking_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
        is_synthetic: bool = False,
    ) -> TrackingEvent | None:
        run = db.query(SeedTestRun).filter(SeedTestRun.tracking_token == tracking_token).first()
        if not run:
            return None
        evt = TrackingEvent(
            seed_test_run_id=run.id,
            event_type="CLICK",
            tracking_token=tracking_token,
            user_agent=user_agent or "Browser/HTTP-Client",
            ip_address=ip_address or "127.0.0.1",
            is_synthetic=is_synthetic or (not run.is_genuine_external_execution),
        )
        db.add(evt)
        db.commit()
        db.refresh(evt)
        return evt

    @staticmethod
    def record_reply_event(
        db: Session,
        seed_test_run_id: str,
        sender_address: str,
        reply_text: str,
        evidence_path_or_url: str | None = None,
        is_genuine_external_reply: bool = False,
    ) -> ReplyEvent:
        run = db.query(SeedTestRun).filter(SeedTestRun.id == seed_test_run_id).first()
        if not run:
            raise IntegrityViolationError(f"SeedTestRun '{seed_test_run_id}' does not exist.")
        reply = ReplyEvent(
            seed_test_run_id=run.id,
            sender_address=sender_address,
            reply_text=reply_text,
            evidence_path_or_url=evidence_path_or_url,
            is_genuine_external_reply=bool(is_genuine_external_reply and evidence_path_or_url),
        )
        db.add(reply)
        db.commit()
        db.refresh(reply)
        return reply
