from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.agents.agent1.discovery import (
    INITIAL_KEYWORD_LIBRARY,
    Agent1DiscoveryEngine,
)
from backend.app.database.models import DiscoveryRun, User
from backend.app.database.session import get_db
from backend.app.schemas.api_schemas import DiscoveryRunCreate
from backend.app.security.auth import get_current_user

router = APIRouter(prefix="/api/discovery", tags=["Discovery"])


def _serialize_run(run: DiscoveryRun) -> dict:
    return {
        "id": run.id,
        "keyword": run.keyword,
        "category": run.category,
        "countries": run.countries,
        "max_candidates": run.max_candidates,
        "source": run.source,
        "run_mode": run.run_mode,
        "status": run.status,
        "discovered_count": run.discovered_count,
        "deduplicated_count": run.deduplicated_count,
        "qualified_count": run.qualified_count,
        "needs_review_count": run.needs_review_count,
        "rejected_count": run.rejected_count,
        "error_log": run.error_log,
        "checkpoints": run.checkpoints,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


@router.get("/keywords")
def get_keyword_library(user: User = Depends(get_current_user)):
    return {"keyword_library": INITIAL_KEYWORD_LIBRARY}


@router.post("/runs")
def start_discovery_run(
    payload: DiscoveryRunCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    engine = Agent1DiscoveryEngine()
    run = engine.execute_discovery_run(
        db=db,
        keyword=payload.keyword,
        category=payload.category,
        countries=payload.countries,
        max_candidates=payload.max_candidates,
        source=payload.source,
        run_mode=payload.run_mode,
    )
    return _serialize_run(run)


@router.get("/runs")
def list_discovery_runs(
    limit: int = 25,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    runs = (
        db.query(DiscoveryRun)
        .order_by(DiscoveryRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return {"runs": [_serialize_run(r) for r in runs]}


@router.get("/runs/{run_id}")
def get_discovery_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = db.query(DiscoveryRun).filter(DiscoveryRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Discovery run '{run_id}' not found.")
    return _serialize_run(run)


@router.post("/runs/{run_id}/cancel")
def cancel_discovery_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = db.query(DiscoveryRun).filter(DiscoveryRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Discovery run '{run_id}' not found.")
    run.status = "CANCELLED"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    return _serialize_run(run)
