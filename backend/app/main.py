from __future__ import annotations

import json
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.app.agents.agent3.submission import evaluate_submission_readiness
from backend.app.api.audits import router as audits_router
from backend.app.api.creators import router as creators_router
from backend.app.api.discovery import router as discovery_router
from backend.app.api.exports import router as exports_router
from backend.app.api.intelligence import router as intelligence_router
from backend.app.api.outreach import router as outreach_router
from backend.app.api.pipeline import router as pipeline_router
from backend.app.api.seed_tests import router as seed_tests_router
from backend.app.config import get_settings
from backend.app.database.models import (
    ApiUsage,
    AuditRun,
    Creator,
    DiscoveryRun,
    OutreachMessage,
    PipelineJob,
    ProductCapability,
    ProductInsight,
    SeedTestAccount,
    User,
)
from backend.app.database.session import get_db, init_db
from backend.app.llm.provider import SharedLLMProvider
from backend.app.schemas.api_schemas import (
    LoginRequest,
    ProductCapabilityCreate,
    ProductInsightUpdate,
    ScoringWeightsUpdate,
)
from backend.app.security.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "Principal Full-Stack AI-Powered Multi-Channel Creator Lead Generation & Outreach Engine "
        "for IncuBrix 2027 Graduate Hiring — Growth Engineer Role (Option 1)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(discovery_router)
app.include_router(creators_router)
app.include_router(intelligence_router)
app.include_router(outreach_router)
app.include_router(audits_router)
app.include_router(seed_tests_router)
app.include_router(exports_router)
app.include_router(pipeline_router)


@app.get("/api/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    total_creators = db.query(Creator).count()
    return {
        "status": "healthy",
        "application": settings.app_name,
        "version": settings.version,
        "database_connected": True,
        "total_creators_in_db": total_creators,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/auth/login", tags=["System"])
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = create_access_token(user.username, user.role)
    response.set_cookie(
        key="growthos_token",
        value=token,
        httponly=True,
        samesite="lax",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name,
    }


@app.get("/api/overview", tags=["System"])
def get_dashboard_overview(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    creators = db.query(Creator).all()
    total = len(creators)
    qualified = [c for c in creators if c.qualification_status == "QUALIFIED"]
    priority_a = [c for c in qualified if c.priority_tier == "Priority A"]
    needs_review = [c for c in creators if c.qualification_status == "NEEDS_REVIEW"]
    rejected = [c for c in creators if c.qualification_status == "REJECTED"]

    genuine_qualified = [c for c in qualified if not c.is_synthetic]
    synthetic_qualified = [c for c in qualified if c.is_synthetic]

    country_counts = Counter(c.country for c in qualified)
    category_counts = Counter(c.category for c in creators)

    latest_disc = db.query(DiscoveryRun).order_by(DiscoveryRun.started_at.desc()).first()
    latest_job = db.query(PipelineJob).order_by(PipelineJob.started_at.desc()).first()
    latest_audit = db.query(AuditRun).order_by(AuditRun.created_at.desc()).first()
    total_messages = db.query(OutreachMessage).count()
    readiness = evaluate_submission_readiness(db)

    return {
        "metrics": {
            "total_discovered": total,
            "qualified_leads": len(qualified),
            "genuine_qualified_leads": len(genuine_qualified),
            "synthetic_qualified_leads": len(synthetic_qualified),
            "priority_a_count": len(priority_a),
            "pending_review": len(needs_review),
            "rejected_leads": len(rejected),
            "outreach_messages_count": total_messages,
        },
        "country_distribution": dict(country_counts),
        "category_distribution": dict(category_counts),
        "qualification_funnel": {
            "discovered": total,
            "verified_candidates": total,
            "qualified": len(qualified),
            "priority_a": len(priority_a),
            "needs_review": len(needs_review),
            "rejected": len(rejected),
        },
        "agent_statuses": {
            "agent1": {
                "name": "Agent 1 — Creator Discovery & Verification",
                "status": latest_disc.status if latest_disc else "IDLE",
                "processed": total,
                "passed": len(qualified),
                "needs_review": len(needs_review),
                "rejected": len(rejected),
            },
            "agent2": {
                "name": "Agent 2 — Lead Intelligence & Outreach",
                "status": "READY" if len(priority_a) > 0 else "IDLE",
                "scored_leads": len(qualified),
                "priority_a": len(priority_a),
                "messages_drafted": total_messages,
            },
            "agent3": {
                "name": "Agent 3 — Quality Control & Delivery",
                "status": latest_audit.readiness_status if latest_audit else readiness["overall_status"],
                "last_audit_pass_rate": latest_audit.qualification_pass_rate if latest_audit else 0.0,
                "last_contact_accuracy": latest_audit.contact_accuracy_rate if latest_audit else 0.0,
            },
        },
        "latest_pipeline_job": {
            "id": latest_job.id,
            "status": latest_job.status,
            "current_stage": latest_job.current_stage,
            "progress_pct": latest_job.progress_pct,
            "runtime_seconds": latest_job.runtime_seconds,
        }
        if latest_job
        else None,
        "submission_readiness": readiness,
    }


@app.get("/api/config/status", tags=["System"])
def get_config_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cur_settings = get_settings()
    llm = SharedLLMProvider()
    scoring_cfg = cur_settings.load_json_config("scoring.json")
    channel_cfg = cur_settings.load_json_config("channel_policies.json")
    capabilities = db.query(ProductCapability).order_by(ProductCapability.capability_key.asc()).all()
    insights = db.query(ProductInsight).order_by(ProductInsight.insight_type.asc(), ProductInsight.item_number.asc()).all()
    test_accounts = db.query(SeedTestAccount).all()
    api_usages = db.query(ApiUsage).order_by(ApiUsage.recorded_at.desc()).limit(30).all()

    return {
        "integrations": {
            "youtube_data_api_v3": {
                "configured": bool(cur_settings.youtube_api_key),
                "status": "READY" if cur_settings.youtube_api_key else "MISSING_KEY (Use Podcast RSS / Public Research / Synthetic Demo)",
            },
            "podcast_rss_itunes": {
                "configured": True,
                "status": "READY (Public No-Key API + XML RSS)",
            },
            "permitted_creator_websites": {
                "configured": True,
                "status": "READY (robots.txt enforced)",
            },
            "official_workbook_template": {
                "configured": bool(cur_settings.workbook_template_path),
                "path": cur_settings.workbook_template_path or None,
                "status": "READY" if cur_settings.workbook_template_path else "NOT_SUPPLIED (Exports provisional CSV)",
            },
        },
        "llm": {
            "selected_provider": llm.provider,
            "selected_model": llm.model,
            "configured": llm.is_configured(),
            "supported_providers": list(SharedLLMProvider.SUPPORTED_PROVIDERS),
            "gemini_key_present": bool(cur_settings.gemini_api_key),
            "openai_key_present": bool(cur_settings.openai_api_key),
            "anthropic_key_present": bool(cur_settings.anthropic_api_key),
            "ollama_base_url": cur_settings.ollama_base_url,
        },
        "sender_identity": {
            "sender_name": cur_settings.sender_name,
            "sender_role": cur_settings.sender_role,
            "sender_email": cur_settings.sender_email,
            "outbound_test_mode": cur_settings.outbound_test_mode,
        },
        "scoring": scoring_cfg,
        "channel_policies": channel_cfg,
        "product_capabilities": [
            {
                "id": c.id,
                "capability_key": c.capability_key,
                "feature_name": c.feature_name,
                "description": c.description,
                "source_evidence": c.source_evidence,
                "verification_date": c.verification_date,
                "confirmed": c.confirmed,
                "suitable_use_cases": c.suitable_use_cases,
                "limitations": c.limitations,
            }
            for c in capabilities
        ],
        "product_insights": [
            {
                "id": i.id,
                "insight_type": i.insight_type,
                "item_number": i.item_number,
                "title": i.title,
                "detail": i.detail,
                "evidence_reference": i.evidence_reference,
                "evidence_url_or_path": i.evidence_url_or_path,
                "is_verified_product_test": i.is_verified_product_test,
            }
            for i in insights
        ],
        "seed_test_accounts": [
            {
                "id": a.id,
                "label": a.label,
                "channel": a.channel,
                "handle_or_address": a.handle_or_address,
                "owner_name": a.owner_name,
                "is_allowlisted": a.is_allowlisted,
            }
            for a in test_accounts
        ],
        "recent_api_usage": [
            {
                "id": u.id,
                "provider": u.provider,
                "endpoint": u.endpoint,
                "operation": u.operation,
                "units_or_tokens": u.units_or_tokens,
                "status_code": u.status_code,
                "success": u.success,
                "latency_ms": u.latency_ms,
                "error_detail": u.error_detail,
                "recorded_at": u.recorded_at.isoformat() if u.recorded_at else None,
            }
            for u in api_usages
        ],
    }


@app.post("/api/config/scoring", tags=["System"])
def update_scoring_weights(
    payload: ScoringWeightsUpdate,
    user: User = Depends(get_current_user),
):
    cur_settings = get_settings()
    cfg = cur_settings.load_json_config("scoring.json")
    cfg["weights"] = {
        "product_relevance": payload.product_relevance,
        "need_evidence_strength": payload.need_evidence_strength,
        "commercial_readiness": payload.commercial_readiness,
        "publishing_activity": payload.publishing_activity,
        "contact_channel_quality": payload.contact_channel_quality,
    }
    path = cur_settings.base_dir / "config" / "scoring.json"
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return {"status": "UPDATED", "scoring": cfg}


@app.post("/api/config/capabilities", tags=["System"])
def add_or_update_capability(
    payload: ProductCapabilityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = (
        db.query(ProductCapability)
        .filter(ProductCapability.capability_key == payload.capability_key)
        .first()
    )
    if existing:
        existing.feature_name = payload.feature_name
        existing.description = payload.description
        existing.source_evidence = payload.source_evidence
        existing.verification_date = payload.verification_date
        existing.confirmed = payload.confirmed
        existing.suitable_use_cases = payload.suitable_use_cases
        existing.limitations = payload.limitations
    else:
        existing = ProductCapability(
            capability_key=payload.capability_key,
            feature_name=payload.feature_name,
            description=payload.description,
            source_evidence=payload.source_evidence,
            verification_date=payload.verification_date,
            confirmed=payload.confirmed,
            suitable_use_cases=payload.suitable_use_cases,
            limitations=payload.limitations,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return {"status": "SAVED", "capability_key": existing.capability_key}


@app.post("/api/config/insights", tags=["System"])
def update_product_insight(
    payload: ProductInsightUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    insight = db.query(ProductInsight).filter(ProductInsight.id == payload.id).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight record not found.")
    insight.title = payload.title
    insight.detail = payload.detail
    insight.evidence_reference = payload.evidence_reference
    insight.evidence_url_or_path = payload.evidence_url_or_path
    insight.is_verified_product_test = payload.is_verified_product_test
    db.commit()
    return {"status": "UPDATED", "id": insight.id}


# Mount Frontend Static Files
FRONTEND_DIR = settings.base_dir / "frontend"
if FRONTEND_DIR.exists():
    if (FRONTEND_DIR / "css").exists():
        app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    if (FRONTEND_DIR / "js").exists():
        app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    if (FRONTEND_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")


@app.get("/", include_in_schema=False)
def serve_frontend_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "IncuBrix GrowthOS API is running. Visit /docs for OpenAPI documentation."}
