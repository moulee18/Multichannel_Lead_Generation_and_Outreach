from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.agents.agent1.discovery import Agent1DiscoveryEngine
from backend.app.agents.agent2.channel_selection import select_creator_channels
from backend.app.agents.agent2.intelligence import generate_creator_intelligence
from backend.app.agents.agent2.outreach import generate_outreach_for_creator
from backend.app.agents.agent2.scoring import score_and_rank_qualified_leads
from backend.app.agents.agent3.message_audit import run_outreach_audit
from backend.app.agents.agent3.qualification_audit import (
    run_independent_qualification_and_geo_audit,
)
from backend.app.agents.agent3.random_audit import run_internal_random_audit
from backend.app.agents.agent3.submission import evaluate_submission_readiness
from backend.app.config import get_settings
from backend.app.database.models import AuditFinding, AuditRun, Creator, PipelineJob
from backend.app.exports.report_generator import generate_full_submission_package
from backend.app.llm.provider import SharedLLMProvider
from backend.app.services.jobs import JobManager
from backend.app.services.tracking import ensure_default_seed_test_records


class PipelineOrchestrator:
    """Single top-level coordinator for Agent 1, Agent 2, and Agent 3 with partial failure recovery and checkpoints."""

    def __init__(self):
        self.settings = get_settings()
        self.agent1 = Agent1DiscoveryEngine()
        self.llm = SharedLLMProvider()

    def run_full_pipeline(
        self,
        db: Session,
        keyword: str = "video podcast creator",
        category: str = "Podcaster / Video Podcaster",
        countries: list[str] | None = None,
        max_candidates: int = 35,
        source: str = "synthetic_demo",
        run_mode: str = "synthetic_demo",
        skip_discovery: bool = False,
        include_synthetic_in_exports: bool = True,
        resume_job_id: str | None = None,
    ) -> PipelineJob:
        if resume_job_id:
            job = db.query(PipelineJob).filter(PipelineJob.id == resume_job_id).first()
            if job:
                job.status = "RUNNING"
                job.retry_count += 1
                db.commit()
            else:
                job = JobManager.create_job(db, "full_pipeline", {"resumed_from": resume_job_id})
        else:
            job = JobManager.create_job(
                db,
                job_type="full_pipeline",
                input_params={
                    "keyword": keyword,
                    "category": category,
                    "countries": countries or ["United States", "Canada", "United Kingdom", "Australia"],
                    "max_candidates": max_candidates,
                    "source": source,
                    "run_mode": run_mode,
                    "skip_discovery": skip_discovery,
                },
            )

        try:
            # STAGE 1: Validate Configuration
            JobManager.update_stage(
                db,
                job,
                "STAGE_1_VALIDATE_CONFIG",
                10.0,
                stage_data={
                    "status": "COMPLETED",
                    "llm_provider": self.llm.provider,
                    "youtube_api_configured": bool(self.settings.youtube_api_key),
                    "outbound_test_mode": self.settings.outbound_test_mode,
                },
            )

            # STAGE 2: Agent 1 Discovery & Verification
            if not skip_discovery:
                JobManager.update_stage(db, job, "STAGE_2_AGENT1_DISCOVERY_AND_VERIFICATION", 25.0)
                disc_run = self.agent1.execute_discovery_run(
                    db=db,
                    keyword=keyword,
                    category=category,
                    countries=countries,
                    max_candidates=max_candidates,
                    source=source,
                    run_mode=run_mode,
                )
                JobManager.update_stage(
                    db,
                    job,
                    "STAGE_2_AGENT1_DISCOVERY_AND_VERIFICATION",
                    40.0,
                    stage_data={
                        "discovery_run_id": disc_run.id,
                        "status": disc_run.status,
                        "discovered": disc_run.discovered_count,
                        "deduplicated": disc_run.deduplicated_count,
                        "qualified": disc_run.qualified_count,
                        "needs_review": disc_run.needs_review_count,
                        "rejected": disc_run.rejected_count,
                        "errors": disc_run.error_log,
                    },
                    checkpoint_data={"agent1_completed": True, "discovery_run_id": disc_run.id},
                )
                if disc_run.error_log:
                    for err in disc_run.error_log:
                        JobManager.record_error(db, job, str(err.get("message") or err.get("error")))

            # STAGE 3: Agent 2 Scoring, Ranking, Channel Selection, Intelligence & Outreach
            JobManager.update_stage(db, job, "STAGE_3_AGENT2_INTELLIGENCE_AND_OUTREACH", 55.0)
            agent2_summary = self.run_agent2_stage(db, job=job)
            JobManager.update_stage(
                db,
                job,
                "STAGE_3_AGENT2_INTELLIGENCE_AND_OUTREACH",
                70.0,
                stage_data=agent2_summary,
                checkpoint_data={"agent2_completed": True},
            )

            # STAGE 4: Agent 3 Independent Audit, Geographic Checks, Random Sample & Seed Test Lab
            JobManager.update_stage(db, job, "STAGE_4_AGENT3_QUALITY_AUDIT_AND_SEED_LAB", 85.0)
            agent3_summary = self.run_agent3_audit_stage(db, include_synthetic=include_synthetic_in_exports)
            JobManager.update_stage(
                db,
                job,
                "STAGE_4_AGENT3_QUALITY_AUDIT_AND_SEED_LAB",
                92.0,
                stage_data=agent3_summary,
                checkpoint_data={"agent3_audit_completed": True, "audit_run_id": agent3_summary.get("audit_run_id")},
            )

            # STAGE 5: Exports, Launch Kit & Submission Readiness
            JobManager.update_stage(db, job, "STAGE_5_EXPORTS_AND_READINESS", 96.0)
            export_summary = generate_full_submission_package(
                db=db,
                include_synthetic=include_synthetic_in_exports,
            )
            JobManager.update_stage(
                db,
                job,
                "STAGE_5_EXPORTS_AND_READINESS",
                99.0,
                stage_data={
                    "export_batch_id": export_summary["export_batch_id"],
                    "artifact_count": export_summary["artifact_count"],
                    "readiness_status": export_summary["readiness"]["overall_status"],
                },
                checkpoint_data={"exports_completed": True, "export_batch_id": export_summary["export_batch_id"]},
            )

            total_creators = db.query(Creator).count()
            qualified_total = db.query(Creator).filter(Creator.qualification_status == "QUALIFIED").count()
            review_total = db.query(Creator).filter(Creator.qualification_status == "NEEDS_REVIEW").count()
            rejected_total = db.query(Creator).filter(Creator.qualification_status == "REJECTED").count()

            return JobManager.complete_job(
                db=db,
                job=job,
                status="COMPLETED",
                processed=total_creators,
                passed=qualified_total,
                review=review_total,
                rejected=rejected_total,
            )
        except Exception as exc:
            JobManager.record_error(db, job, f"Pipeline fatal error: {exc}")
            return JobManager.complete_job(db=db, job=job, status="FAILED")

    def run_agent2_stage(self, db: Session, job: PipelineJob | None = None) -> dict[str, Any]:
        scores = score_and_rank_qualified_leads(db)
        priority_a_count = 0
        channel_decisions_count = 0
        intelligence_count = 0
        messages_generated = 0
        errors: list[str] = []

        for score_obj in scores:
            creator = score_obj.creator
            if not creator:
                continue
            try:
                dec = select_creator_channels(db, creator)
                if dec:
                    channel_decisions_count += 1

                intel = generate_creator_intelligence(db, creator, llm_provider=self.llm)
                if intel:
                    intelligence_count += 1

                if score_obj.priority_tier == "Priority A":
                    priority_a_count += 1
                    msgs = generate_outreach_for_creator(
                        db,
                        creator,
                        channels=["email", "linkedin", "instagram"],
                        llm_provider=self.llm,
                    )
                    messages_generated += len(msgs)
                db.commit()
            except Exception as exc:
                db.rollback()
                err_str = f"Agent 2 failed on creator {creator.id}: {exc}"
                errors.append(err_str)
                if job:
                    JobManager.record_error(db, job, err_str)

        return {
            "status": "COMPLETED",
            "scored_leads": len(scores),
            "priority_a_selected": priority_a_count,
            "channel_decisions": channel_decisions_count,
            "intelligence_profiles": intelligence_count,
            "outreach_messages_generated": messages_generated,
            "errors": errors,
        }

    def run_agent3_audit_stage(
        self,
        db: Session,
        random_seed: int = 42,
        sample_size: int = 20,
        include_synthetic: bool = True,
    ) -> dict[str, Any]:
        qual_geo = run_independent_qualification_and_geo_audit(db, include_synthetic=include_synthetic)
        outreach_aud = run_outreach_audit(db, include_synthetic=include_synthetic)
        rand_aud = run_internal_random_audit(
            db,
            random_seed=random_seed,
            sample_size=sample_size,
            include_synthetic=include_synthetic,
        )
        seed_runs = ensure_default_seed_test_records(db)
        readiness = evaluate_submission_readiness(db)

        geo = qual_geo["geographic_audit"]
        audit_run = AuditRun(
            audit_type="full_independent_audit",
            random_seed=random_seed,
            sample_size=rand_aud["actual_sample_size"],
            total_qualified_checked=qual_geo["total_qualified_checked"],
            qualification_pass_rate=rand_aud["qualification_pass_rate"],
            contact_accuracy_rate=rand_aud["contact_accuracy_rate"],
            duplicate_count=qual_geo["duplicate_count"],
            approved_market_pct=geo["approved_market_pct"],
            represented_countries_count=geo["represented_countries_count"],
            max_single_country_pct=geo["max_single_country_pct"],
            geographic_compliant=geo["compliant"],
            outreach_compliant=outreach_aud["compliant"],
            readiness_status=readiness["overall_status"],
            summary_payload={
                "qualification_audit": {
                    "total_checked": qual_geo["total_qualified_checked"],
                    "overall_pass_rate": qual_geo["qualification_pass_rate"],
                    "overall_contact_accuracy": qual_geo["contact_accuracy_rate"],
                    "duplicate_count": qual_geo["duplicate_count"],
                },
                "geographic_audit": geo,
                "outreach_audit": {
                    "priority_a_total": outreach_aud["priority_a_total"],
                    "priority_a_complete": outreach_aud["priority_a_with_complete_sequences"],
                    "channels_covered": outreach_aud["channels_covered"],
                    "invalid_messages_count": outreach_aud["invalid_messages_count"],
                    "compliant": outreach_aud["compliant"],
                },
                "random_audit": rand_aud,
                "seed_tests_count": len(seed_runs),
                "readiness": readiness,
            },
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit_run)
        db.flush()

        for f in qual_geo["findings"] + outreach_aud["findings"]:
            db.add(
                AuditFinding(
                    audit_run_id=audit_run.id,
                    creator_id=f.get("creator_id"),
                    category=f["category"],
                    severity=f["severity"],
                    passed=f["passed"],
                    rule_code=f["rule_code"],
                    description=f["description"],
                    evidence_urls=f.get("evidence_urls", []),
                )
            )

        db.commit()
        return {
            "audit_run_id": audit_run.id,
            "qualification_pass_rate": audit_run.qualification_pass_rate,
            "contact_accuracy_rate": audit_run.contact_accuracy_rate,
            "duplicate_count": audit_run.duplicate_count,
            "geographic_compliant": audit_run.geographic_compliant,
            "outreach_compliant": audit_run.outreach_compliant,
            "readiness_status": audit_run.readiness_status,
            "seed_tests_count": len(seed_runs),
        }
