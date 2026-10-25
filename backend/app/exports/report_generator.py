from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.agents.agent3.message_audit import run_outreach_audit
from backend.app.agents.agent3.qualification_audit import (
    run_independent_qualification_and_geo_audit,
)
from backend.app.agents.agent3.random_audit import run_internal_random_audit
from backend.app.agents.agent3.submission import evaluate_submission_readiness
from backend.app.config import get_settings
from backend.app.database.models import (
    Creator,
    OutreachMessage,
    ProductInsight,
    SeedTestRun,
    SubmissionArtifact,
)
from backend.app.exports.csv_exporter import (
    compute_file_sha256,
    export_evidence_index_csv,
    export_leads_csv,
    export_runtime_costs_csv,
)
from backend.app.exports.workbook_exporter import populate_official_workbook


def generate_full_submission_package(
    db: Session,
    submission_dir: Path | None = None,
    include_synthetic: bool = True,
) -> dict[str, Any]:
    """Generate the complete Section 16 submission/ folder, artifacts, reports, checklists, and ZIP archive."""
    settings = get_settings()
    base_sub_dir = submission_dir or (settings.base_dir / "submission")
    base_sub_dir.mkdir(parents=True, exist_ok=True)
    batch_id = f"exp_{uuid.uuid4().hex[:12]}"

    # Create required directories
    for rel in (
        "outreach/email",
        "outreach/linkedin",
        "outreach/instagram",
        "outreach/priority_a",
        "reports",
        "evidence",
        "demos",
    ):
        (base_sub_dir / rel).mkdir(parents=True, exist_ok=True)

    artifacts_created: list[SubmissionArtifact] = []

    def _register_artifact(
        art_type: str,
        fpath: Path,
        rec_count: int = 0,
        synthetic: bool = False,
        notes: str = "",
    ) -> None:
        art = SubmissionArtifact(
            export_batch_id=batch_id,
            artifact_type=art_type,
            file_name=fpath.name,
            file_path=str(fpath),
            status="GENERATED",
            contains_synthetic_data=synthetic,
            record_count=rec_count,
            checksum_sha256=compute_file_sha256(fpath) if fpath.exists() else None,
            notes=notes,
        )
        db.add(art)
        artifacts_created.append(art)

    # 1. leads.csv
    leads_csv_path = base_sub_dir / "leads.csv"
    leads_info = export_leads_csv(db, leads_csv_path, include_synthetic=include_synthetic)
    _register_artifact(
        "LEADS_CSV",
        leads_csv_path,
        rec_count=leads_info["record_count"],
        synthetic=leads_info["contains_synthetic"],
        notes="Provisional internal CSV (official workbook template pending)" if not settings.workbook_template_path else "Official leads.csv",
    )

    # 2. completed_workbook.xlsx (only if official template exists)
    wb_status = {"status": "BLOCKED_MISSING_TEMPLATE"}
    if settings.workbook_template_path:
        tpl_path = Path(settings.workbook_template_path)
        if tpl_path.exists():
            wb_out_path = base_sub_dir / "completed_workbook.xlsx"
            wb_status = populate_official_workbook(db, tpl_path, wb_out_path, leads_csv_path, include_synthetic=include_synthetic)
            if wb_status.get("status") == "COMPLETED":
                _register_artifact(
                    "COMPLETED_WORKBOOK",
                    wb_out_path,
                    rec_count=wb_status.get("lead_rows_synced", 0),
                    synthetic=leads_info["contains_synthetic"],
                    notes="Populated yellow cells and preserved green calculation cells.",
                )

    # 3. Outreach sequences (email/, linkedin/, instagram/, priority_a/)
    messages = db.query(OutreachMessage).all()
    creators_map = {c.id: c for c in db.query(Creator).all()}
    by_channel_creator: dict[tuple[str, str], list[OutreachMessage]] = {}
    for m in messages:
        by_channel_creator.setdefault((m.channel, m.creator_id), []).append(m)

    for (ch, cid), msg_list in by_channel_creator.items():
        msg_list.sort(key=lambda x: x.step_number)
        creator = creators_map.get(cid)
        if not creator:
            continue
        payload = {
            "creator_id": cid,
            "creator_name": creator.name,
            "priority_tier": creator.priority_tier,
            "channel": ch,
            "is_synthetic": creator.is_synthetic,
            "steps": [
                {
                    "step_number": m.step_number,
                    "step_label": m.step_label,
                    "subject": m.subject,
                    "body": m.body,
                    "referenced_content_title": m.referenced_content_title,
                    "referenced_content_url": m.referenced_content_url,
                    "cited_evidence_ids": m.cited_evidence_ids,
                    "sender_identity": m.sender_identity,
                    "opt_out_text": m.opt_out_text,
                    "validation_passed": m.validation_passed,
                }
                for m in msg_list
            ],
        }
        ch_folder = ch if ch in ("email", "linkedin", "instagram") else "email"
        ch_file = base_sub_dir / "outreach" / ch_folder / f"{cid}_{ch}.json"
        ch_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if creator.priority_tier == "Priority A":
            pa_file = base_sub_dir / "outreach" / "priority_a" / f"rank_{creator.rank_position or 99:02d}_{cid}_{ch}.json"
            pa_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # 4. Evidence index & Seed test results
    ev_csv_path = base_sub_dir / "evidence" / "evidence_index.csv"
    ev_info = export_evidence_index_csv(db, ev_csv_path)
    _register_artifact("EVIDENCE_INDEX", ev_csv_path, rec_count=ev_info["record_count"], synthetic=leads_info["contains_synthetic"])

    seed_runs = db.query(SeedTestRun).all()
    seed_json_path = base_sub_dir / "evidence" / "seed_test_results.json"
    seed_payload = [
        {
            "id": sr.id,
            "channel": sr.channel,
            "recipient_address": sr.recipient_address,
            "execution_mode": sr.execution_mode,
            "status": sr.status,
            "tracking_url": sr.tracking_url,
            "is_genuine_external_execution": sr.is_genuine_external_execution,
            "tracking_events_count": len(sr.tracking_events),
            "reply_events_count": len(sr.reply_events),
            "execution_logs": sr.execution_logs,
            "error_recovery_notes": sr.error_recovery_notes,
        }
        for sr in seed_runs
    ]
    seed_json_path.write_text(json.dumps(seed_payload, indent=2, default=str), encoding="utf-8")
    _register_artifact("SEED_TEST_RESULTS", seed_json_path, rec_count=len(seed_payload))

    # 5. Reports
    rt_csv_path = base_sub_dir / "reports" / "runtime_costs.csv"
    rt_info = export_runtime_costs_csv(db, rt_csv_path)
    _register_artifact("RUNTIME_COSTS_CSV", rt_csv_path, rec_count=rt_info["record_count"])

    qual_audit = run_independent_qualification_and_geo_audit(db, include_synthetic=include_synthetic)
    outreach_audit = run_outreach_audit(db, include_synthetic=include_synthetic)
    random_audit = run_internal_random_audit(db, random_seed=42, sample_size=20, include_synthetic=include_synthetic)
    readiness = evaluate_submission_readiness(db)

    # product_observations.md & growth_opportunities.md
    observations = db.query(ProductInsight).filter(ProductInsight.insight_type == "OBSERVATION").order_by(ProductInsight.item_number).all()
    opportunities = db.query(ProductInsight).filter(ProductInsight.insight_type == "OPPORTUNITY").order_by(ProductInsight.item_number).all()

    obs_md_path = base_sub_dir / "reports" / "product_observations.md"
    obs_lines = [
        "# IncuBrix Product & Workflow Observations (5 Evidence-Backed Findings)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for o in observations:
        obs_lines.extend(
            [
                f"## {o.title}",
                f"- **Verified Live Product Session Attached**: `{o.is_verified_product_test}`",
                f"- **Finding**: {o.detail}",
                f"- **Supporting Evidence**: {o.evidence_reference}",
                "",
            ]
        )
    obs_md_path.write_text("\n".join(obs_lines), encoding="utf-8")
    _register_artifact("PRODUCT_OBSERVATIONS_MD", obs_md_path, rec_count=len(observations))

    opp_md_path = base_sub_dir / "reports" / "growth_opportunities.md"
    opp_lines = [
        "# Top 3 Evidence-Backed Growth Opportunities to Win Creators",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for op in opportunities:
        opp_lines.extend(
            [
                f"## {op.title}",
                f"- **Strategy & Action**: {op.detail}",
                f"- **Supporting Evidence**: {op.evidence_reference}",
                "",
            ]
        )
    opp_md_path.write_text("\n".join(opp_lines), encoding="utf-8")
    _register_artifact("GROWTH_OPPORTUNITIES_MD", opp_md_path, rec_count=len(opportunities))

    # qualification_audit.md
    qual_md_path = base_sub_dir / "reports" / "qualification_audit.md"
    qual_md_path.write_text(
        "# Independent Qualification, Outreach & Internal Random Audit Report\n\n"
        f"- **Audit Label**: `{random_audit['audit_label']}`\n"
        f"- **Total Qualified Checked**: {qual_audit['total_qualified_checked']}\n"
        f"- **Overall Qualification Pass Rate**: {qual_audit['qualification_pass_rate']}%\n"
        f"- **Overall Contact Accuracy Rate**: {qual_audit['contact_accuracy_rate']}%\n"
        f"- **Duplicate Records Found**: {qual_audit['duplicate_count']}\n"
        f"- **Random 20-Lead Sample (Seed={random_audit['random_seed']}) Pass Rate**: {random_audit['qualification_pass_rate']}%\n"
        f"- **Random 20-Lead Sample Contact Accuracy**: {random_audit['contact_accuracy_rate']}%\n"
        f"- **Priority A Complete 3-Step Sequences**: {outreach_audit['priority_a_with_complete_sequences']}/{outreach_audit['priority_a_total']}\n"
        f"- **Channels Covered**: {', '.join(outreach_audit['channels_covered'])}\n",
        encoding="utf-8",
    )
    _register_artifact("QUALIFICATION_AUDIT_MD", qual_md_path, rec_count=qual_audit["total_qualified_checked"])

    # geographic_compliance.md
    geo = qual_audit["geographic_audit"]
    geo_md_path = base_sub_dir / "reports" / "geographic_compliance.md"
    geo_md_path.write_text(
        "# Geographic Compliance Report\n\n"
        f"- **Geographic Compliance Status**: `{'COMPLIANT' if geo['compliant'] else 'NON_COMPLIANT'}`\n"
        f"- **Approved 7-Market Share**: {geo['approved_market_pct']}% (Minimum required: 80.0%)\n"
        f"- **Represented Countries Count**: {geo['represented_countries_count']} (Minimum required: 3)\n"
        f"- **Largest Single-Country Share**: {geo['max_single_country_pct']}% (Maximum allowed: 60.0%)\n"
        f"- **Missing Country Evidence Count**: {geo['missing_country_evidence_count']}\n\n"
        "## Country Breakdown\n\n"
        + "\n".join(f"- **{k}**: {v}" for k, v in geo["country_distribution"].items())
        + "\n",
        encoding="utf-8",
    )
    _register_artifact("GEOGRAPHIC_COMPLIANCE_MD", geo_md_path, rec_count=geo["represented_countries_count"])

    # thirty_day_launch_plan.md
    launch_md_path = base_sub_dir / "reports" / "thirty_day_launch_plan.md"
    launch_md_path.write_text(_build_thirty_day_launch_plan_markdown(), encoding="utf-8")
    _register_artifact("THIRTY_DAY_LAUNCH_PLAN_MD", launch_md_path, rec_count=4)

    # readiness_report.md
    readiness_md_path = base_sub_dir / "reports" / "readiness_report.md"
    readiness_md_path.write_text(
        "# Official Submission Readiness Report\n\n"
        f"- **Overall Readiness Status**: **{readiness['overall_status']}**\n"
        f"- **Summary**: {readiness['explanation']}\n"
        f"- **Genuine Qualified Creators**: {readiness['genuine_qualified_leads']} / 1,000\n"
        f"- **Synthetic Demo Qualified Creators (excluded from official count)**: {readiness['synthetic_demo_qualified_leads']}\n"
        f"- **Genuine Priority A Creators**: {readiness['genuine_priority_a_leads']} / 25\n\n"
        "## Requirement Checklist\n\n"
        + "\n".join(
            f"- **[{item['status']}] {item['title']}** (`{item['category']}`): {item['detail']}"
            for item in readiness["checklist"]
        )
        + "\n\n## AI & Automation Disclosure\n"
        "- **Automated Engine**: IncuBrix GrowthOS (FastAPI + SQLAlchemy + 3 Coordinated Agents).\n"
        "- **AI Hallucination Guard**: Deterministic verification of all citations, URLs, and confirmed capabilities.\n"
        "- **Manual Review**: Verification Queue used for ambiguous commercial/workflow claims.\n",
        encoding="utf-8",
    )
    _register_artifact("READINESS_REPORT_MD", readiness_md_path, rec_count=len(readiness["checklist"]))

    # 6. Demo checklists & video_links.json
    prod_demo_path = base_sub_dir / "demos" / "product_walkthrough_checklist.md"
    prod_demo_path.write_text(
        "# 5-Minute Unedited Product Walkthrough Checklist\n\n"
        "1. **0:00 - 1:00**: Log into official IncuBrix workspace (`www.incubrix.com`) and show creator onboarding.\n"
        "2. **1:00 - 2:30**: Upload/import a long-form video podcast episode and walk through editing, captioning, and short-clip repurposing.\n"
        "3. **2:30 - 3:45**: Highlight the 5 specific product observations with live screen evidence.\n"
        "4. **3:45 - 5:00**: Present the 3 biggest growth opportunities to win creators and how they connect to the outreach engine.\n",
        encoding="utf-8",
    )
    _register_artifact("PRODUCT_WALKTHROUGH_CHECKLIST", prod_demo_path, rec_count=4)

    tech_demo_path = base_sub_dir / "demos" / "technical_demo_checklist.md"
    tech_demo_path.write_text(
        "# 8-Minute Unedited Technical Demonstration Checklist\n\n"
        "1. **0:00 - 1:00 — Application Overview**: Show IncuBrix GrowthOS dashboard, database metrics, qualification funnel, and 3-agent status.\n"
        "2. **1:00 - 2:15 — New Creator Discovery**: Run a live discovery query (Podcast RSS / YouTube API) and show deduplication.\n"
        "3. **2:15 - 3:30 — Evidence Verification**: Open a creator's **Lead Evidence Passport**, click source URLs, and inspect Verification Queue.\n"
        "4. **3:30 - 4:45 — Lead Scoring & Outreach**: Show **Explainable Lead Scoring** breakdown, **Contact Channel Explainer**, and 3-step Priority A sequences in Outreach Studio.\n"
        "5. **4:45 - 5:45 — Smart Refresh with New Input**: Run Smart Refresh (`POST /api/pipeline/refresh`) and show unchanged vs updated records and API cost logs.\n"
        "6. **5:45 - 6:45 — Recovery from a Simple Failure**: Trigger/inspect transient error recovery in Agent Control Centre & Seed Test Lab.\n"
        "7. **6:45 - 8:00 — Audit & Export**: Run the 20-lead Random Audit Simulator (`seed=42`) and download the submission ZIP package.\n",
        encoding="utf-8",
    )
    _register_artifact("TECHNICAL_DEMO_CHECKLIST", tech_demo_path, rec_count=7)

    video_links_path = base_sub_dir / "demos" / "video_links.json"
    if not video_links_path.exists():
        video_links_path.write_text(
            json.dumps(
                {
                    "product_walkthrough_video_url": "PENDING_RECORDING",
                    "technical_demo_video_url": "PENDING_RECORDING",
                    "note": "Do not fabricate recordings. Replace PENDING_RECORDING with actual unedited video URLs after recording.",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    _register_artifact("VIDEO_LINKS_JSON", video_links_path, rec_count=2)

    # 7. submission_manifest.json
    manifest_path = base_sub_dir / "submission_manifest.json"
    manifest_payload = {
        "export_batch_id": batch_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "readiness_status": readiness["overall_status"],
        "genuine_qualified_leads": readiness["genuine_qualified_leads"],
        "synthetic_demo_qualified_leads": readiness["synthetic_demo_qualified_leads"],
        "workbook_status": wb_status.get("status"),
        "artifacts": [
            {
                "artifact_type": a.artifact_type,
                "file_name": a.file_name,
                "record_count": a.record_count,
                "contains_synthetic_data": a.contains_synthetic_data,
                "checksum_sha256": a.checksum_sha256,
            }
            for a in artifacts_created
        ],
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
    _register_artifact("SUBMISSION_MANIFEST", manifest_path, rec_count=len(artifacts_created))

    # Create ZIP bundle in output/submission/
    zip_dir = settings.base_dir / "output" / "submission"
    zip_dir.mkdir(parents=True, exist_ok=True)
    zip_base = zip_dir / f"incubrix_submission_{batch_id}"
    zip_file_str = shutil.make_archive(str(zip_base), "zip", root_dir=str(base_sub_dir))
    zip_path = Path(zip_file_str)
    _register_artifact(
        "SUBMISSION_ZIP_BUNDLE",
        zip_path,
        rec_count=leads_info["record_count"],
        synthetic=leads_info["contains_synthetic"],
        notes="Complete downloadable submission archive",
    )

    db.commit()
    return {
        "export_batch_id": batch_id,
        "submission_dir": str(base_sub_dir),
        "zip_path": str(zip_path),
        "readiness": readiness,
        "leads_csv": leads_info,
        "workbook": wb_status,
        "artifact_count": len(artifacts_created),
    }


def _build_thirty_day_launch_plan_markdown() -> str:
    return """# IncuBrix 30-Day Creator Acquisition & Multi-Channel Launch Kit

## 1. Executive Summary & Target Segments
This launch kit enables IncuBrix to begin compliant, evidence-backed creator outreach on **Day 1 (next Monday)** and rerun weekly refresh cycles automatically.

- **Segment 1 — Podcasters & Video Podcasters (40% share)**: Weekly long-form shows (45–90 min) monetising via sponsorships or memberships that need rapid short-clip repurposing and captioning.
- **Segment 2 — YouTubers & Video-First Creators (35% share)**: Educational/business YouTube channels publishing 2+ long-form videos/60d or 8+ items/30d with post-production editing backlogs.
- **Segment 3 — Expert-Led Creators: Coaches, Consultants & Educators (25% share)**: High-LTV course/coaching operators needing consistent multi-channel authority clips across YouTube, LinkedIn, and Instagram.

---

## 2. Channel Strategy & Safe Daily Volumes
| Channel | Role in Sequence | Safe Daily Volume / Rep | Weekly Volume (5 Days) | 30-Day Volume (22 Workdays) | Compliance & Platform Rules |
|---|---|---:|---:|---:|---|
| **Business Email** | Primary Channel (70% of leads) | 35–45 emails/day (warmed domain) | 200 emails/week | 880 emails/month | CAN-SPAM / GDPR / India DPDP compliant; SPF/DKIM/DMARC configured; explicit sender identity & 1-click/reply opt-out. |
| **LinkedIn (Manual Assisted)** | Primary/Backup for Coaches & B2B Podcasters | 15–20 personalised notes/day | 85 messages/week | 375 messages/month | Zero unauthorized scraping or bulk automation; manual review & send from Outreach Studio queue. |
| **Instagram Business DM / Guest Desk** | Backup for Video-First & Lifestyle Podcasters | 10–15 contextual DMs/day | 60 messages/week | 260 messages/month | Manual contextual outreach referencing specific recent Reel/Episode; no automated DM bots. |

---

## 3. Week-by-Week Execution Plan (Days 1–30)

### Week 1 (Days 1–7): Priority A Launch & Baseline Calibration
- **Monday (Day 1)**: Verify domain authentication (SPF, DKIM, DMARC) and launch Step 1 (First Contact) to the top **25 Priority A** creators across Email, LinkedIn, and Instagram.
- **Tuesday–Wednesday (Days 2–3)**: Dispatch cohort 1 of Priority B leads (35 emails/day + 15 LinkedIn + 10 Instagram). Log all opens/clicks/replies in GrowthOS.
- **Thursday (Day 4)**: Trigger **Follow-Up 1 (Step 2)** for non-responding Priority A leads referencing their latest episode clip opportunity.
- **Friday (Day 5)**: Run weekly `Smart Refresh` (`python scripts/run_refresh.py`) to ingest new creator uploads and verify fresh 30-day evidence.

### Week 2 (Days 8–14): Multi-Channel Follow-Up & Segment A/B Review
- **Monday (Day 8)**: Dispatch **Follow-Up 2 (Step 3 — Breakup/Value Offer)** for Day-1 Priority A non-responders; switch non-email responders to their verified Backup Channel.
- **Tuesday–Thursday (Days 9–11)**: Scale daily email volume to 45/day as domain reputation holds (<0.1% spam complaint rate, <1.5% bounce rate).
- **Friday (Day 12)**: Review reply rates by segment (Podcasters vs Coaches vs YouTubers) and promote top-performing hooks into Agent 2 templates.

### Week 3 (Days 15–21): Backlog Wedge Campaign & Pipeline Refresh
- **Monday–Wednesday (Days 15–17)**: Run the **"1-Episode Repurposing Wedge"** offer for high-scoring Priority B creators (offering a concrete walkthrough using their most recent long-form video).
- **Thursday (Day 18)**: Audit 20 random active leads via Agent 3's Random Audit Simulator to ensure >=90% contact accuracy and <30-day evidence freshness.
- **Friday (Day 19)**: Execute weekly Smart Refresh and replenish Priority A queue with newly discovered creators.

### Week 4 (Days 22–30): Conversion Optimization & Month-2 Scale Handover
- **Monday–Wednesday (Days 22–24)**: Follow up with warm "not right now / check back next month" replies and book live IncuBrix workflow demos.
- **Thursday (Day 25)**: Export monthly CRM attribution report (`leads.csv` + `runtime_costs.csv` + channel conversion matrix).
- **Friday (Day 30)**: Finalise Month-2 channel mix allocation based on verified reply-to-meeting conversion data.

---

## 4. Responsible Owners, Tools & Budget
| Workstream | Responsible Owner | Tools Used | Estimated 30-Day Budget (USD) |
|---|---|---|---:|
| **Discovery, Verification & Refresh** | Growth Engineer | IncuBrix GrowthOS + YouTube Data API v3 + Public Podcast RSS | $0 (Free tier API quotas) |
| **AI Analysis & Draft Generation** | Growth Engineer | GrowthOS Agent 2 (Deterministic / Optional Gemini Flash or GPT-4o-mini) | $0 – $15/mo (optional LLM tokens) |
| **Email Sending & Deliverability** | Growth Engineer / SDR | Google Workspace / Custom Domain Mailbox (2 warmed inboxes) | $14 – $28/mo |
| **LinkedIn & Instagram Assisted Outreach** | SDR / Growth Associate | GrowthOS Outreach Studio + Native Platform Business Profiles | $0 |
| **Total Estimated 30-Day Budget** | | | **$14 – $43 / month** |

---

## 5. Expected Reply & Meeting Rates (With Reasoning)
- **Email Sequence (3 Steps)**:
  - **Expected Positive/Neutral Reply Rate**: **6.5% – 9.5%** (3.2% – 4.5% qualified positive reply rate).
  - **Expected Demo/Meeting Rate**: **2.0% – 3.0%** of contacted leads (~18–26 meetings per 880 leads).
  - *Reasoning*: Generic cold outreach averages <1% reply rate, whereas every lead in GrowthOS has verified recent activity (30d/60d), verified monetization, and a message citing their exact recent video title and production need.
- **LinkedIn Assisted Sequence**:
  - **Expected Acceptance + Reply Rate**: **12.0% – 16.0%** (4.0% – 5.5% positive reply rate).
  - **Expected Demo/Meeting Rate**: **2.5% – 3.8%** (~9–14 meetings per 375 leads).
  - *Reasoning*: Expert-led creators (coaches, consultants, B2B podcasters) actively use LinkedIn for distribution and respond strongly to peer-level workflow notes.
- **Instagram Business DM Sequence**:
  - **Expected Reply Rate**: **8.0% – 12.0%** (~2.0% meeting conversion, ~5–8 meetings per 260 leads).
  - *Reasoning*: Video-first creators check Instagram business requests when messages reference a specific recent Reel/episode rather than a generic pitch.

---

## 6. Key Assumptions, Risks & Mitigations
| Risk | Impact | Mitigation Built into GrowthOS |
|---|---|---|
| **Email deliverability degradation or bounces** | High | Never guess emails; only contact verified public business emails; cap per-inbox volume at 35–45/day. |
| **Platform account restrictions on LinkedIn / Instagram** | High | Strictly forbid unauthorized browser bots/scrapers; use human-in-the-loop manual send from Outreach Studio. |
| **Stale creator references (>30 days old)** | Medium | Agent 3 blocks any outreach citing evidence older than 30 days; weekly Smart Refresh updates recent uploads. |
| **AI hallucinated product claims** | High | AI Hallucination Guard deterministically cross-checks every draft against `product_capabilities.json` and stored Evidence IDs. |
"""
