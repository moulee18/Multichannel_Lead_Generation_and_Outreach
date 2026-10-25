from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.agents.agent3.message_audit import run_outreach_audit
from backend.app.agents.agent3.qualification_audit import (
    run_independent_qualification_and_geo_audit,
)
from backend.app.agents.agent3.random_audit import run_internal_random_audit
from backend.app.agents.agent3.submission import evaluate_submission_readiness
from backend.app.database.models import AuditRun, User
from backend.app.database.session import get_db
from backend.app.schemas.api_schemas import AuditRunRequest
from backend.app.security.auth import get_current_user
from backend.app.services.orchestrator import PipelineOrchestrator

router = APIRouter(prefix="/api/audits", tags=["Quality Audits & Random Audit Simulator"])


def _serialize_audit_run(a: AuditRun) -> dict:
    return {
        "id": a.id,
        "audit_type": a.audit_type,
        "random_seed": a.random_seed,
        "sample_size": a.sample_size,
        "total_qualified_checked": a.total_qualified_checked,
        "qualification_pass_rate": a.qualification_pass_rate,
        "contact_accuracy_rate": a.contact_accuracy_rate,
        "duplicate_count": a.duplicate_count,
        "approved_market_pct": a.approved_market_pct,
        "represented_countries_count": a.represented_countries_count,
        "max_single_country_pct": a.max_single_country_pct,
        "geographic_compliant": a.geographic_compliant,
        "outreach_compliant": a.outreach_compliant,
        "readiness_status": a.readiness_status,
        "summary_payload": a.summary_payload,
        "findings": [
            {
                "id": f.id,
                "creator_id": f.creator_id,
                "category": f.category,
                "severity": f.severity,
                "passed": f.passed,
                "rule_code": f.rule_code,
                "description": f.description,
                "evidence_urls": f.evidence_urls,
            }
            for f in a.findings
        ],
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/overview")
def get_audits_overview(
    include_synthetic: bool = True,
    random_seed: int = 42,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    qual_geo = run_independent_qualification_and_geo_audit(db, include_synthetic=include_synthetic)
    outreach_aud = run_outreach_audit(db, include_synthetic=include_synthetic)
    random_aud = run_internal_random_audit(
        db, random_seed=random_seed, sample_size=20, include_synthetic=include_synthetic
    )
    readiness = evaluate_submission_readiness(db)
    recent_runs = db.query(AuditRun).order_by(AuditRun.created_at.desc()).limit(10).all()

    return {
        "qualification_audit": {
            "total_qualified_checked": qual_geo["total_qualified_checked"],
            "qualification_pass_rate": qual_geo["qualification_pass_rate"],
            "contact_accuracy_rate": qual_geo["contact_accuracy_rate"],
            "duplicate_count": qual_geo["duplicate_count"],
        },
        "geographic_audit": qual_geo["geographic_audit"],
        "outreach_audit": outreach_aud,
        "random_audit": random_aud,
        "readiness": readiness,
        "recent_audit_runs": [_serialize_audit_run(r) for r in recent_runs],
    }


@router.post("/run")
def execute_audit_run(
    payload: AuditRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    orchestrator = PipelineOrchestrator()
    res = orchestrator.run_agent3_audit_stage(
        db=db,
        random_seed=payload.random_seed,
        sample_size=payload.sample_size,
        include_synthetic=payload.include_synthetic,
    )
    audit_run = db.query(AuditRun).filter(AuditRun.id == res["audit_run_id"]).first()
    return _serialize_audit_run(audit_run)


@router.get("/{audit_id}")
def get_audit_by_id(
    audit_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    audit_run = db.query(AuditRun).filter(AuditRun.id == audit_id).first()
    if not audit_run:
        raise HTTPException(status_code=404, detail=f"Audit run '{audit_id}' not found.")
    return _serialize_audit_run(audit_run)
