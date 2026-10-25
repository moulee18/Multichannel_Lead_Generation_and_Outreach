from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database.models import PipelineJob, RefreshHistory, User
from backend.app.database.session import get_db
from backend.app.integrations.podcast_sources import PodcastRSSCollector
from backend.app.schemas.api_schemas import PipelineRefreshRequest, PipelineRunRequest
from backend.app.security.auth import get_current_user
from backend.app.services.orchestrator import PipelineOrchestrator
from backend.app.services.refresh import run_smart_refresh
from fixtures.synthetic_demo_data.demo_creators import generate_synthetic_demo_candidates

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline & Smart Refresh"])


def _serialize_job(job: PipelineJob) -> dict:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "current_stage": job.current_stage,
        "progress_pct": job.progress_pct,
        "processed_count": job.processed_count,
        "passed_count": job.passed_count,
        "review_count": job.review_count,
        "rejected_count": job.rejected_count,
        "error_count": job.error_count,
        "retry_count": job.retry_count,
        "can_retry": job.can_retry,
        "input_params": job.input_params,
        "stage_metrics": job.stage_metrics,
        "checkpoints": job.checkpoints,
        "error_messages": job.error_messages,
        "runtime_seconds": job.runtime_seconds,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.post("/run")
def run_pipeline_endpoint(
    payload: PipelineRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    orchestrator = PipelineOrchestrator()
    job = orchestrator.run_full_pipeline(
        db=db,
        keyword=payload.keyword,
        category=payload.category,
        countries=payload.countries,
        max_candidates=payload.max_candidates,
        source=payload.source,
        run_mode=payload.run_mode,
        skip_discovery=payload.skip_discovery,
        include_synthetic_in_exports=payload.include_synthetic_in_exports,
        resume_job_id=payload.resume_job_id,
    )
    return _serialize_job(job)


@router.post("/refresh")
def run_refresh_endpoint(
    payload: PipelineRefreshRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    incoming = payload.incoming_candidates
    if incoming is None and payload.keyword:
        if payload.source == "synthetic_demo":
            incoming = generate_synthetic_demo_candidates()[: payload.max_candidates]
        elif payload.source == "podcast_rss":
            try:
                collector = PodcastRSSCollector()
                incoming = collector.discover_podcasts(
                    db=db,
                    keyword=payload.keyword,
                    max_candidates=payload.max_candidates,
                )
            except Exception:
                incoming = []

    history = run_smart_refresh(db=db, incoming_candidates=incoming)
    return {
        "id": history.id,
        "new_creators_count": history.new_creators_count,
        "updated_creators_count": history.updated_creators_count,
        "unchanged_records_count": history.unchanged_records_count,
        "stale_evidence_count": history.stale_evidence_count,
        "invalidated_qualifications_count": history.invalidated_qualifications_count,
        "duplicates_prevented_count": history.duplicates_prevented_count,
        "api_calls_used": history.api_calls_used,
        "runtime_seconds": history.runtime_seconds,
        "details": history.details,
        "executed_at": history.executed_at.isoformat() if history.executed_at else None,
    }


@router.get("/runs")
def list_pipeline_runs(
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    jobs = (
        db.query(PipelineJob)
        .order_by(PipelineJob.started_at.desc())
        .limit(limit)
        .all()
    )
    refreshes = (
        db.query(RefreshHistory)
        .order_by(RefreshHistory.executed_at.desc())
        .limit(10)
        .all()
    )
    return {
        "jobs": [_serialize_job(j) for j in jobs],
        "refresh_history": [
            {
                "id": r.id,
                "new_creators_count": r.new_creators_count,
                "updated_creators_count": r.updated_creators_count,
                "unchanged_records_count": r.unchanged_records_count,
                "stale_evidence_count": r.stale_evidence_count,
                "invalidated_qualifications_count": r.invalidated_qualifications_count,
                "duplicates_prevented_count": r.duplicates_prevented_count,
                "api_calls_used": r.api_calls_used,
                "runtime_seconds": r.runtime_seconds,
                "executed_at": r.executed_at.isoformat() if r.executed_at else None,
            }
            for r in refreshes
        ],
    }


@router.get("/runs/{run_id}")
def get_pipeline_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(PipelineJob).filter(PipelineJob.id == run_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Pipeline job '{run_id}' not found.")
    return _serialize_job(job)
