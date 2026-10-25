from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.database.session import get_session_factory, init_db
from backend.app.exports.report_generator import generate_full_submission_package


def main() -> None:
    parser = argparse.ArgumentParser(description="IncuBrix GrowthOS — Submission Exporter CLI")
    parser.add_argument(
        "--genuine-only",
        action="store_true",
        help="Exclude synthetic demo records from leads.csv export",
    )
    args = parser.parse_args()

    init_db()
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        summary = generate_full_submission_package(
            db=db,
            include_synthetic=not args.genuine_only,
        )
        print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
