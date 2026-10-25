from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class DiscoveryRunCreate(BaseModel):
    keyword: str = Field(default="video podcast creator", min_length=2)
    category: str = Field(default="Podcaster / Video Podcaster")
    countries: list[str] = Field(
        default_factory=lambda: ["United States", "Canada", "United Kingdom", "Australia"]
    )
    max_candidates: int = Field(default=25, ge=1, le=500)
    source: str = Field(default="youtube_api")
    run_mode: str = Field(default="live")


class ManualReviewRequest(BaseModel):
    new_status: str = Field(..., pattern="^(QUALIFIED|NEEDS_REVIEW|REJECTED)$")
    notes: str = Field(..., min_length=3)
    evidence_url: str | None = None
    criterion_overrides: dict[str, str] = Field(default_factory=dict)
    country_override: str | None = None


class IntelligenceRunRequest(BaseModel):
    creator_ids: list[str] | None = None
    regenerate_outreach: bool = False


class OutreachGenerateRequest(BaseModel):
    creator_id: str | None = None
    channels: list[str] = Field(default_factory=lambda: ["email", "linkedin", "instagram"])
    force_regenerate: bool = False


class OutreachMessagePatch(BaseModel):
    subject: str | None = None
    body: str = Field(..., min_length=10)
    edit_notes: str | None = "Manual edit in Outreach Studio"


class OutreachMessageReviewRequest(BaseModel):
    approval_status: str = Field(..., pattern="^(APPROVED|NEEDS_REVIEW|REJECTED)$")
    reviewer_notes: str | None = None


class AuditRunRequest(BaseModel):
    random_seed: int = Field(default=42)
    sample_size: int = Field(default=20, ge=1, le=100)
    include_synthetic: bool = True


class SeedTestCreateRequest(BaseModel):
    channel: str = Field(default="email")
    recipient_address: str = Field(...)
    message_preview: str = Field(default="Seed test outreach sequence verification.")
    execution_mode: str = Field(default="DRY_RUN")
    explicit_approval: bool = False
    evidence_attachment_path: str | None = None
    simulate_failure_recovery: bool = False


class SeedReplyCreateRequest(BaseModel):
    sender_address: str
    reply_text: str
    evidence_path_or_url: str | None = None
    is_genuine_external_reply: bool = False


class SeedAccountCreateRequest(BaseModel):
    label: str
    channel: str
    handle_or_address: str
    owner_name: str = "Participant Owner"


class ExportCreateRequest(BaseModel):
    include_synthetic: bool = True


class PipelineRunRequest(BaseModel):
    keyword: str = "video podcast creator"
    category: str = "Podcaster / Video Podcaster"
    countries: list[str] = Field(
        default_factory=lambda: ["United States", "Canada", "United Kingdom", "Australia"]
    )
    max_candidates: int = Field(default=35, ge=1, le=500)
    source: str = "synthetic_demo"
    run_mode: str = "synthetic_demo"
    skip_discovery: bool = False
    include_synthetic_in_exports: bool = True
    resume_job_id: str | None = None


class PipelineRefreshRequest(BaseModel):
    keyword: str | None = None
    source: str = "podcast_rss"
    max_candidates: int = Field(default=10, ge=1, le=200)
    incoming_candidates: list[dict[str, Any]] | None = None


class ProductCapabilityCreate(BaseModel):
    capability_key: str
    feature_name: str
    description: str
    source_evidence: str
    verification_date: str = "2026-10-23"
    confirmed: bool = True
    suitable_use_cases: list[str] = Field(default_factory=list)
    limitations: str = ""


class ProductInsightUpdate(BaseModel):
    id: str
    title: str
    detail: str
    evidence_reference: str
    evidence_url_or_path: str | None = None
    is_verified_product_test: bool = False


class ScoringWeightsUpdate(BaseModel):
    product_relevance: float = 30.0
    need_evidence_strength: float = 25.0
    commercial_readiness: float = 20.0
    publishing_activity: float = 15.0
    contact_channel_quality: float = 10.0
