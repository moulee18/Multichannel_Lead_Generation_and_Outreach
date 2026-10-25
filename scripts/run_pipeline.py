from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.agents.agent1.discovery import Agent1DiscoveryEngine
from backend.app.database.session import get_session_factory, init_db
from backend.app.services.orchestrator import PipelineOrchestrator
from backend.app.utils.logging import logger


def main() -> None:
    parser = argparse.ArgumentParser(description="IncuBrix GrowthOS — One-Command Pipeline Runner")
    parser.add_argument("--keyword", default="video podcast creator", help="Search keyword")
    parser.add_argument("--category", default="Podcaster / Video Podcaster", help="Creator category")
    parser.add_argument(
        "--source",
        default="synthetic_demo",
        choices=["youtube_api", "podcast_rss", "public_research_import", "synthetic_demo"],
        help="Discovery source adapter",
    )
    parser.add_argument("--max-candidates", type=int, default=35, help="Max candidates to discover")
    parser.add_argument("--demo", action="store_true", help="Run with clearly labelled synthetic demo fixtures")
    parser.add_argument("--live-podcast", action="store_true", help="Run live discovery using public Podcast RSS / iTunes API")
    parser.add_argument("--import-public-research", action="store_true", help="Import existing verified public research records")
    parser.add_argument("--agent", choices=["all", "agent1", "agent2", "agent3"], default="all", help="Run specific agent or full pipeline")
    parser.add_argument("--resume", default=None, help="Resume a previous pipeline job ID")
    args = parser.parse_args()

    init_db()
    SessionLocal = get_session_factory()
    orchestrator = PipelineOrchestrator()

    source = args.source
    run_mode = "live"
    if args.live_podcast:
        source = "podcast_rss"
        run_mode = "live"
    elif args.import_public_research:
        source = "public_research_import"
        run_mode = "live"
    elif args.demo or source == "synthetic_demo":
        source = "synthetic_demo"
        run_mode = "synthetic_demo"

    with SessionLocal() as db:
        if args.agent == "agent1":
            engine = Agent1DiscoveryEngine()
            run = engine.execute_discovery_run(
                db=db,
                keyword=args.keyword,
                category=args.category,
                max_candidates=args.max_candidates,
                source=source,
                run_mode=run_mode,
            )
            print(
                json.dumps(
                    {
                        "agent": "agent1",
                        "discovery_run_id": run.id,
                        "status": run.status,
                        "discovered": run.discovered_count,
                        "deduplicated": run.deduplicated_count,
                        "qualified": run.qualified_count,
                        "needs_review": run.needs_review_count,
                        "rejected": run.rejected_count,
                    },
                    indent=2,
                )
            )
            return

        if args.agent == "agent2":
            summary = orchestrator.run_agent2_stage(db)
            print(json.dumps({"agent": "agent2", **summary}, indent=2))
            return

        if args.agent == "agent3":
            summary = orchestrator.run_agent3_audit_stage(db)
            print(json.dumps({"agent": "agent3", **summary}, indent=2))
            return

        job = orchestrator.run_full_pipeline(
            db=db,
            keyword=args.keyword,
            category=args.category,
            max_candidates=args.max_candidates,
            source=source,
            run_mode=run_mode,
            resume_job_id=args.resume,
        )
        logger.info(f"Full pipeline job {job.id} finished with status={job.status}")
        print(
            json.dumps(
                {
                    "job_id": job.id,
                    "status": job.status,
                    "processed_count": job.processed_count,
                    "passed_count": job.passed_count,
                    "review_count": job.review_count,
                    "rejected_count": job.rejected_count,
                    "runtime_seconds": job.runtime_seconds,
                    "stage_metrics": job.stage_metrics,
                },
                indent=2,
                default=str,
            )
        )


if __name__ == "__main__":
    main()
