from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.database.session import get_session_factory, init_db
from backend.app.integrations.podcast_sources import PodcastRSSCollector
from backend.app.services.refresh import run_smart_refresh
from fixtures.synthetic_demo_data.demo_creators import generate_synthetic_demo_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="IncuBrix GrowthOS — Smart Refresh CLI")
    parser.add_argument("--keyword", default=None, help="Optional keyword to fetch fresh candidates before refresh")
    parser.add_argument("--source", default="synthetic_demo", choices=["synthetic_demo", "podcast_rss"])
    parser.add_argument("--max-candidates", type=int, default=15)
    args = parser.parse_args()

    init_db()
    SessionLocal = get_session_factory()

    with SessionLocal() as db:
        incoming = None
        if args.keyword:
            if args.source == "synthetic_demo":
                incoming = generate_synthetic_demo_candidates()[: args.max_candidates]
            elif args.source == "podcast_rss":
                collector = PodcastRSSCollector()
                incoming = collector.discover_podcasts(db, args.keyword, max_candidates=args.max_candidates)

        history = run_smart_refresh(db, incoming_candidates=incoming)
        print(
            json.dumps(
                {
                    "refresh_id": history.id,
                    "new_creators": history.new_creators_count,
                    "updated_creators": history.updated_creators_count,
                    "unchanged_records": history.unchanged_records_count,
                    "stale_evidence": history.stale_evidence_count,
                    "invalidated_qualifications": history.invalidated_qualifications_count,
                    "duplicates_prevented": history.duplicates_prevented_count,
                    "api_calls_used": history.api_calls_used,
                    "runtime_seconds": history.runtime_seconds,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
