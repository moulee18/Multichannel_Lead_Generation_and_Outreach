from __future__ import annotations

import random
from typing import Any

from sqlalchemy.orm import Session

from backend.app.agents.agent3.qualification_audit import (
    run_independent_qualification_and_geo_audit,
)


def run_internal_random_audit(
    db: Session,
    random_seed: int = 42,
    sample_size: int = 20,
    include_synthetic: bool = True,
) -> dict[str, Any]:
    """Feature 6 — Random Audit Simulator (INTERNAL AUDIT).
    Samples up to 20 leads using a recorded random seed and evaluates criterion-level pass/fail and contact accuracy.
    """
    base_audit = run_independent_qualification_and_geo_audit(db, include_synthetic=include_synthetic)
    all_results = sorted(base_audit["creator_audit_results"], key=lambda r: r["creator_id"])

    rng = random.Random(random_seed)
    actual_sample_size = min(sample_size, len(all_results))
    sampled_items = rng.sample(all_results, actual_sample_size) if actual_sample_size > 0 else []

    qual_passed = sum(1 for item in sampled_items if item["passed_all"])
    contact_passed = sum(1 for item in sampled_items if item["contact_accurate"])
    dup_count = sum(1 for item in sampled_items if not item["checks"].get("unique_record", True))

    qual_rate = round((qual_passed / actual_sample_size) * 100.0, 2) if actual_sample_size > 0 else 0.0
    contact_rate = round((contact_passed / actual_sample_size) * 100.0, 2) if actual_sample_size > 0 else 0.0

    meets_min_thresholds = (
        actual_sample_size >= min(20, len(all_results))
        and actual_sample_size > 0
        and qual_rate >= 85.0
        and contact_rate >= 90.0
        and dup_count == 0
    )

    return {
        "audit_label": "INTERNAL AUDIT (Reproducible Simulation — Not Assessor Certification)",
        "random_seed": random_seed,
        "requested_sample_size": sample_size,
        "actual_sample_size": actual_sample_size,
        "qualification_pass_rate": qual_rate,
        "qualification_target_min_pct": 85.0,
        "qualification_exceptional_pct": 90.0,
        "contact_accuracy_rate": contact_rate,
        "contact_target_min_pct": 90.0,
        "contact_exceptional_pct": 95.0,
        "duplicate_findings_count": dup_count,
        "meets_minimum_thresholds": meets_min_thresholds,
        "sampled_leads": sampled_items,
    }
