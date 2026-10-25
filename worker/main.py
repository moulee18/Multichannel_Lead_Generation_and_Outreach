from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.database.models import PipelineJob
from backend.app.database.session import get_session_factory, init_db
from backend.app.services.orchestrator import PipelineOrchestrator
from backend.app.utils.logging import logger


def run_worker_loop(poll_interval: float = 3.0, max_cycles: int | None = None) -> None:
    """Persistent database-backed worker process for queued or interrupted pipeline jobs."""
    init_db()
    SessionLocal = get_session_factory()
    orchestrator = PipelineOrchestrator()
    logger.info("IncuBrix GrowthOS Background Worker started.")

    cycles = 0
    while True:
        cycles += 1
        with SessionLocal() as db:
            queued_job = (
                db.query(PipelineJob)
                .filter(PipelineJob.status == "QUEUED")
                .order_by(PipelineJob.started_at.asc())
                .first()
            )
            if queued_job:
                params = queued_job.input_params or {}
                logger.info(f"Worker picked up job {queued_job.id} ({queued_job.job_type})")
                orchestrator.run_full_pipeline(
                    db=db,
                    keyword=params.get("keyword", "video podcast creator"),
                    category=params.get("category", "Podcaster / Video Podcaster"),
                    countries=params.get("countries"),
                    max_candidates=int(params.get("max_candidates", 35)),
                    source=params.get("source", "synthetic_demo"),
                    run_mode=params.get("run_mode", "synthetic_demo"),
                    skip_discovery=bool(params.get("skip_discovery", False)),
                    resume_job_id=queued_job.id,
                )

        if max_cycles is not None and cycles >= max_cycles:
            break
        time.sleep(poll_interval)


if __name__ == "__main__":
    run_worker_loop()
