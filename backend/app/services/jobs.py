from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.database.models import PipelineJob


class JobManager:
    """Persistent database-backed job tracker supporting checkpoints, progress reporting, and retry/resume."""

    @staticmethod
    def create_job(
        db: Session,
        job_type: str,
        input_params: dict[str, Any] | None = None,
    ) -> PipelineJob:
        job = PipelineJob(
            job_type=job_type,
            status="RUNNING",
            current_stage="INITIALIZING",
            progress_pct=0.0,
            input_params=input_params or {},
            stage_metrics={},
            checkpoints={},
            error_messages=[],
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def update_stage(
        db: Session,
        job: PipelineJob,
        stage_name: str,
        progress_pct: float,
        stage_data: dict[str, Any] | None = None,
        checkpoint_data: dict[str, Any] | None = None,
    ) -> PipelineJob:
        job.current_stage = stage_name
        job.progress_pct = round(progress_pct, 2)
        if stage_data:
            metrics = dict(job.stage_metrics or {})
            metrics[stage_name] = stage_data
            job.stage_metrics = metrics
        if checkpoint_data:
            cp = dict(job.checkpoints or {})
            cp.update(checkpoint_data)
            job.checkpoints = cp
        now = datetime.now(timezone.utc)
        started = job.started_at if job.started_at.tzinfo else job.started_at.replace(tzinfo=timezone.utc)
        job.runtime_seconds = round((now - started).total_seconds(), 2)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def record_error(db: Session, job: PipelineJob, error_msg: str) -> None:
        errs = list(job.error_messages or [])
        errs.append(f"[{datetime.now(timezone.utc).isoformat()}] {error_msg}")
        job.error_messages = errs
        job.error_count = len(errs)
        db.commit()

    @staticmethod
    def complete_job(
        db: Session,
        job: PipelineJob,
        status: str = "COMPLETED",
        processed: int = 0,
        passed: int = 0,
        review: int = 0,
        rejected: int = 0,
    ) -> PipelineJob:
        now = datetime.now(timezone.utc)
        started = job.started_at if job.started_at.tzinfo else job.started_at.replace(tzinfo=timezone.utc)
        job.status = status
        job.current_stage = "COMPLETED" if status == "COMPLETED" else job.current_stage
        job.progress_pct = 100.0 if status == "COMPLETED" else job.progress_pct
        job.processed_count = processed
        job.passed_count = passed
        job.review_count = review
        job.rejected_count = rejected
        job.completed_at = now
        job.runtime_seconds = round((now - started).total_seconds(), 2)
        db.commit()
        db.refresh(job)
        return job
