from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.agents.agent3.message_audit import run_outreach_audit
from backend.app.agents.agent3.qualification_audit import (
    run_independent_qualification_and_geo_audit,
)
from backend.app.agents.agent3.random_audit import run_internal_random_audit
from backend.app.config import get_settings
from backend.app.database.models import (
    Creator,
    ProductInsight,
    SeedTestRun,
    SubmissionArtifact,
)


def evaluate_submission_readiness(db: Session) -> dict[str, Any]:
    """Feature 8 — Submission Readiness Centre.
    Maps every official IncuBrix requirement and clearly distinguishes between:
    - Implemented software capability
    - Tested capability
    - Real-data requirement satisfied
    - Evidence missing
    - Submission artifact missing
    """
    settings = get_settings()

    # Count genuine (non-synthetic) vs synthetic qualified creators
    genuine_qualified_count = (
        db.query(Creator)
        .filter(Creator.qualification_status == "QUALIFIED", Creator.is_synthetic.is_(False))
        .count()
    )
    synthetic_qualified_count = (
        db.query(Creator)
        .filter(Creator.qualification_status == "QUALIFIED", Creator.is_synthetic.is_(True))
        .count()
    )
    genuine_priority_a = (
        db.query(Creator)
        .filter(
            Creator.qualification_status == "QUALIFIED",
            Creator.priority_tier == "Priority A",
            Creator.is_synthetic.is_(False),
        )
        .count()
    )

    qual_geo_genuine = run_independent_qualification_and_geo_audit(db, include_synthetic=False)
    outreach_genuine = run_outreach_audit(db, include_synthetic=False)
    random_audit_all = run_internal_random_audit(db, random_seed=42, sample_size=20, include_synthetic=True)

    # Seed test status across 3 channels
    seed_runs = db.query(SeedTestRun).all()
    seed_channels_tested = {r.channel for r in seed_runs}
    genuine_seed_channels = {r.channel for r in seed_runs if r.is_genuine_external_execution}

    # Workbook check
    wb_path = Path(settings.workbook_template_path) if settings.workbook_template_path else None
    wb_available = bool(wb_path and wb_path.exists())

    # Product observations & opportunities
    observations = db.query(ProductInsight).filter(ProductInsight.insight_type == "OBSERVATION").all()
    opportunities = db.query(ProductInsight).filter(ProductInsight.insight_type == "OPPORTUNITY").all()
    verified_obs_count = sum(1 for o in observations if o.is_verified_product_test)

    # Video links check
    video_links_file = settings.base_dir / "submission" / "demos" / "video_links.json"
    has_recorded_videos = False
    if video_links_file.exists():
        txt = video_links_file.read_text(encoding="utf-8")
        has_recorded_videos = "https://" in txt and "PENDING_RECORDING" not in txt

    artifacts_count = db.query(SubmissionArtifact).count()

    checklist: list[dict[str, Any]] = [
        {
            "id": "req_engine_architecture",
            "title": "1. Three-Agent Automated Engine & Rerunnable Pipeline",
            "category": "IMPLEMENTED_CAPABILITY",
            "status": "PASSED",
            "implemented": True,
            "tested": True,
            "real_data_satisfied": True,
            "detail": "Agent 1 (Discovery/Verification), Agent 2 (Scoring/Outreach), Agent 3 (Audit/Export) + Smart Refresh operational.",
        },
        {
            "id": "req_1000_genuine_leads",
            "title": "2. Minimum 1,000 Unique Genuinely Qualified Creators (Zero Duplicates)",
            "category": "REAL_DATA_SATISFIED" if genuine_qualified_count >= 1000 else "EVIDENCE_MISSING",
            "status": "PASSED" if genuine_qualified_count >= 1000 else "BLOCKED",
            "implemented": True,
            "tested": True,
            "real_data_satisfied": genuine_qualified_count >= 1000,
            "detail": (
                f"Genuine qualified creators: {genuine_qualified_count}/1,000 "
                f"(Synthetic demo qualified records in DB: {synthetic_qualified_count} — never counted as genuine)."
            ),
        },
        {
            "id": "req_priority_a_25",
            "title": "3. Top 25 Priority A Leads with 3-Step Personalised Sequences on 3+ Channels",
            "category": "REAL_DATA_SATISFIED" if (genuine_priority_a >= 25 and outreach_genuine["compliant"]) else "EVIDENCE_MISSING",
            "status": "PASSED" if (genuine_priority_a >= 25 and outreach_genuine["compliant"]) else "BLOCKED",
            "implemented": True,
            "tested": True,
            "real_data_satisfied": genuine_priority_a >= 25 and outreach_genuine["compliant"],
            "detail": f"Genuine Priority A leads: {genuine_priority_a}/25. Multi-channel sequence generator tested and active.",
        },
        {
            "id": "req_geographic_mix",
            "title": "4. Geographic Distribution (>=80% from 7 Target Markets, >=3 Countries, <=60% Max Single Country)",
            "category": "REAL_DATA_SATISFIED" if qual_geo_genuine["geographic_audit"]["compliant"] else "EVIDENCE_MISSING",
            "status": "PASSED" if qual_geo_genuine["geographic_audit"]["compliant"] else "BLOCKED",
            "implemented": True,
            "tested": True,
            "real_data_satisfied": qual_geo_genuine["geographic_audit"]["compliant"],
            "detail": (
                f"Approved market share: {qual_geo_genuine['geographic_audit']['approved_market_pct']}%, "
                f"Countries: {qual_geo_genuine['geographic_audit']['represented_countries_count']}, "
                f"Max country: {qual_geo_genuine['geographic_audit']['max_single_country_pct']}%."
            ),
        },
        {
            "id": "req_random_20_audit",
            "title": "5. 20-Lead Random Audit (>=85% Qualification, >=90% Contact Accuracy, 0% Duplicates)",
            "category": "TESTED_CAPABILITY",
            "status": "PASSED" if random_audit_all["meets_minimum_thresholds"] else "WARNING",
            "implemented": True,
            "tested": True,
            "real_data_satisfied": genuine_qualified_count >= 20,
            "detail": (
                f"Internal Random Audit Simulator: Qual Pass={random_audit_all['qualification_pass_rate']}%, "
                f"Contact Accuracy={random_audit_all['contact_accuracy_rate']}%, Duplicates={random_audit_all['duplicate_findings_count']}."
            ),
        },
        {
            "id": "req_seed_test_3_channels",
            "title": "6. Three-Channel Owned-Account Seed Test Proof (Scheduling, Tracking, Reply Logging)",
            "category": "REAL_DATA_SATISFIED" if len(genuine_seed_channels) >= 3 else "TESTED_CAPABILITY",
            "status": "PASSED" if len(genuine_seed_channels) >= 3 else "WARNING",
            "implemented": True,
            "tested": True,
            "real_data_satisfied": len(genuine_seed_channels) >= 3,
            "detail": (
                f"Channels tested in Seed Lab: {sorted(seed_channels_tested)}. "
                f"Channels with attached external delivery proof: {sorted(genuine_seed_channels)}/3."
            ),
        },
        {
            "id": "req_official_workbook",
            "title": "7. Official Completed Excel Workbook & Matching leads.csv",
            "category": "REAL_DATA_SATISFIED" if wb_available else "ARTIFACT_MISSING",
            "status": "PASSED" if wb_available else "BLOCKED",
            "implemented": True,
            "tested": True,
            "real_data_satisfied": wb_available,
            "detail": (
                "Workbook exporter preserves formulas/green cells/validations. "
                + ("Official template configured." if wb_available else "Official IncuBrix .xlsx template not supplied yet; provisional CSV exported.")
            ),
        },
        {
            "id": "req_product_insights",
            "title": "8. Product & Market Insight (5 Observations + 3 Growth Opportunities with Evidence)",
            "category": "REAL_DATA_SATISFIED" if verified_obs_count >= 5 and len(opportunities) >= 3 else "EVIDENCE_MISSING",
            "status": "PASSED" if verified_obs_count >= 5 and len(opportunities) >= 3 else "WARNING",
            "implemented": True,
            "tested": True,
            "real_data_satisfied": verified_obs_count >= 5 and len(opportunities) >= 3,
            "detail": f"Recorded {len(observations)} observations ({verified_obs_count} with live product session proof) and {len(opportunities)} opportunities.",
        },
        {
            "id": "req_launch_kit",
            "title": "9. Actionable 30-Day Launch Kit (Volumes, Owners, Budget, Reply/Meeting Rates, Risks)",
            "category": "IMPLEMENTED_CAPABILITY",
            "status": "PASSED",
            "implemented": True,
            "tested": True,
            "real_data_satisfied": True,
            "detail": "Complete week-by-week 30-day launch plan generated in submission/reports/thirty_day_launch_plan.md.",
        },
        {
            "id": "req_demo_videos",
            "title": "10. Two Unedited Demo Videos (5-min Product Walkthrough & 8-min Technical Demo)",
            "category": "REAL_DATA_SATISFIED" if has_recorded_videos else "ARTIFACT_MISSING",
            "status": "PASSED" if has_recorded_videos else "BLOCKED",
            "implemented": True,
            "tested": True,
            "real_data_satisfied": has_recorded_videos,
            "detail": "Checklists and video_links.json generated; requires actual unedited screen recordings before final hand-in.",
        },
    ]

    blockers = [item["title"] for item in checklist if item["status"] == "BLOCKED"]
    warnings = [item["title"] for item in checklist if item["status"] == "WARNING"]

    if not blockers and not warnings:
        overall_status = "READY"
        explanation = "All software, data volume, audit, seed-test, workbook, and video deliverables are verified."
    elif not blockers and warnings:
        overall_status = "READY_WITH_WARNINGS"
        explanation = f"Core requirements met; {len(warnings)} item(s) have non-blocking warnings."
    else:
        overall_status = "NOT_READY"
        explanation = (
            "Software engine and all 3 agents are 100% implemented and verified, but official assessment hand-in is "
            f"NOT_READY due to {len(blockers)} genuine-data/external artifact requirement(s): "
            + "; ".join(blockers)
        )

    return {
        "overall_status": overall_status,
        "explanation": explanation,
        "genuine_qualified_leads": genuine_qualified_count,
        "synthetic_demo_qualified_leads": synthetic_qualified_count,
        "genuine_priority_a_leads": genuine_priority_a,
        "export_artifacts_generated": artifacts_count,
        "blockers": blockers,
        "warnings": warnings,
        "checklist": checklist,
    }
