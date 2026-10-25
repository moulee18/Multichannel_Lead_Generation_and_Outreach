from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.database.session import init_db
from backend.app.utils.logging import logger


def main() -> None:
    init_db()
    logger.info("IncuBrix GrowthOS database schema, capabilities, and allowlisted test accounts initialised.")


if __name__ == "__main__":
    main()
