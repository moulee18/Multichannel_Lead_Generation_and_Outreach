from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def test_cli_one_command_operations():
    python_exe = sys.executable

    # 1. init_database.py
    r1 = subprocess.run(
        [python_exe, "scripts/init_database.py"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r1.returncode == 0

    # 2. run_pipeline.py --demo
    r2 = subprocess.run(
        [python_exe, "scripts/run_pipeline.py", "--demo", "--max-candidates", "35"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r2.returncode == 0
    assert '"status": "COMPLETED"' in r2.stdout

    # 3. run_refresh.py
    r3 = subprocess.run(
        [python_exe, "scripts/run_refresh.py", "--keyword", "podcast", "--source", "synthetic_demo", "--max-candidates", "5"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r3.returncode == 0
    assert '"duplicates_prevented":' in r3.stdout

    # 4. export_submission.py
    r4 = subprocess.run(
        [python_exe, "scripts/export_submission.py"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r4.returncode == 0
    assert '"export_batch_id":' in r4.stdout
