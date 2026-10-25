from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str = "") -> str:
    uid = uuid.uuid4().hex
    return f"{prefix}_{uid[:16]}" if prefix else uid


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("usr"))
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="admin")
    full_name: Mapped[str] = mapped_column(String(256), nullable=False, default="Growth Engineer Admin")
    email: Mapped[str] = mapped_column(String(256), nullable=False, default="admin@example.org")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Creator(Base):
    __tablename__ = "creators"
    __table_args__ = (
        UniqueConstraint("platform", "platform_id", name="uq_creator_platform_id"),
        Index("ix_creators_qual_status", "qualification_status"),
        Index("ix_creators_country", "country"),
        Index("ix_creators_category", "category"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("crt"))
    platform: Mapped[str] = mapped_column(String(64), nullable=False, default="youtube")
    platform_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    handle: Mapped[str] = mapped_column(String(128), nullable=True)
    official_url: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False, default="YouTuber / Video-First Creator")
    niche: Mapped[str] = mapped_column(String(128), nullable=True)
    country: Mapped[str] = mapped_column(String(128), nullable=False, default="UNKNOWN")
    language: Mapped[str] = mapped_column(String(64), nullable=False, default="UNKNOWN")
    description: Mapped[str] = mapped_column(Text, nullable=True)
    subscriber_count: Mapped[int] = mapped_column(Integer, nullable=True)
    total_views: Mapped[int] = mapped_column(Integer, nullable=True)
    total_content_count: Mapped[int] = mapped_column(Integer, nullable=True)
    uploads_playlist_id: Mapped[str] = mapped_column(String(128), nullable=True)
    items_30d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longform_60d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qualification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEEDS_REVIEW")
    priority_tier: Mapped[str] = mapped_column(String(16), nullable=True)
    rank_position: Mapped[int] = mapped_column(Integer, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    discovery_source: Mapped[str] = mapped_column(String(128), nullable=False, default="youtube_api")
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=True)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    content_items: Mapped[list[ContentItem]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    identities: Mapped[list[CreatorIdentity]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    evidence_items: Mapped[list[Evidence]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    verifications: Mapped[list[VerificationResult]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    contacts: Mapped[list[ContactChannel]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    scores: Mapped[list[LeadScore]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    channel_decisions: Mapped[list[ChannelDecision]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    intelligence_records: Mapped[list[CreatorIntelligence]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    outreach_messages: Mapped[list[OutreachMessage]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    manual_reviews: Mapped[list[ManualReview]] = relationship(back_populates="creator", cascade="all, delete-orphan")


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint("creator_id", "external_id", name="uq_creator_content_external_id"),
        Index("ix_content_published_at", "published_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cnt"))
    creator_id: Mapped[str] = mapped_column(String(64), ForeignKey("creators.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="video")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_longform: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(32), nullable=True, default="en")
    view_count: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    creator: Mapped[Creator] = relationship(back_populates="content_items")


class CreatorIdentity(Base):
    __tablename__ = "creator_identities"
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_identity_platform_ext_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cid"))
    creator_id: Mapped[str] = mapped_column(String(64), ForeignKey("creators.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    handle: Mapped[str] = mapped_column(String(256), nullable=True)
    profile_url: Mapped[str] = mapped_column(String(512), nullable=False)
    is_official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    creator: Mapped[Creator] = relationship(back_populates="identities")


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        Index("ix_evidence_creator_criterion", "creator_id", "criterion"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("evd"))
    creator_id: Mapped[str] = mapped_column(String(64), ForeignKey("creators.id", ondelete="CASCADE"), nullable=False, index=True)
    criterion: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(512), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    verification_method: Mapped[str] = mapped_column(String(128), nullable=False, default="deterministic_adapter")
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="VERIFIED")
    is_manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    creator: Mapped[Creator] = relationship(back_populates="evidence_items")


class VerificationResult(Base):
    __tablename__ = "verification_results"
    __table_args__ = (
        Index("ix_verif_creator_status", "creator_id", "overall_status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("vrf"))
    creator_id: Mapped[str] = mapped_column(String(64), ForeignKey("creators.id", ondelete="CASCADE"), nullable=False, index=True)
    real_and_relevant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    commercial_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    needs_incubrix_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    country_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    language_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reachable_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    freshness_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    overall_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEEDS_REVIEW")
    failed_criteria: Mapped[list[str]] = mapped_column(JSON, default=list)
    uncertain_criteria: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    summary_notes: Mapped[str] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    creator: Mapped[Creator] = relationship(back_populates="verifications")


class ContactChannel(Base):
    __tablename__ = "contact_channels"
    __table_args__ = (
        UniqueConstraint("creator_id", "channel_type", "handle_or_address", name="uq_creator_channel_address"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ctc"))
    creator_id: Mapped[str] = mapped_column(String(64), ForeignKey("creators.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_type: Mapped[str] = mapped_column(String(64), nullable=False)
    handle_or_address: Mapped[str] = mapped_column(String(256), nullable=False)
    public_url: Mapped[str] = mapped_column(String(512), nullable=False)
    is_business_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active_within_60d: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    restrictions: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    creator: Mapped[Creator] = relationship(back_populates="contacts")


class LeadScore(Base):
    __tablename__ = "lead_scores"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("scr"))
    creator_id: Mapped[str] = mapped_column(String(64), ForeignKey("creators.id", ondelete="CASCADE"), nullable=False, index=True)
    scoring_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    product_relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    need_evidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    commercial_readiness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    publishing_activity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    contact_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    priority_tier: Mapped[str] = mapped_column(String(16), nullable=False, default="Priority C")
    rank_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    breakdown: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    creator: Mapped[Creator] = relationship(back_populates="scores")


class ChannelDecision(Base):
    __tablename__ = "channel_decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("chd"))
    creator_id: Mapped[str] = mapped_column(String(64), ForeignKey("creators.id", ondelete="CASCADE"), nullable=False, index=True)
    primary_channel: Mapped[str] = mapped_column(String(64), nullable=False)
    primary_contact_value: Mapped[str] = mapped_column(String(256), nullable=False)
    primary_contact_url: Mapped[str] = mapped_column(String(512), nullable=False)
    backup_channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    backup_contact_value: Mapped[str | None] = mapped_column(String(256), nullable=True)
    backup_contact_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    selection_reason: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    restrictions: Mapped[str] = mapped_column(Text, nullable=False)
    rejected_channels: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    creator: Mapped[Creator] = relationship(back_populates="channel_decisions")


class CreatorIntelligence(Base):
    __tablename__ = "creator_intelligence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("int"))
    creator_id: Mapped[str] = mapped_column(String(64), ForeignKey("creators.id", ondelete="CASCADE"), nullable=False, index=True)
    niche_summary: Mapped[str] = mapped_column(String(256), nullable=False)
    recent_content_topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    production_workflow: Mapped[str] = mapped_column(Text, nullable=False)
    pain_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    suitable_capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    personalisation_hooks: Mapped[list[str]] = mapped_column(JSON, default=list)
    cited_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    llm_provider_used: Mapped[str] = mapped_column(String(64), nullable=False, default="none")
    hallucination_guard_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    hallucination_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    creator: Mapped[Creator] = relationship(back_populates="intelligence_records")


class ProductCapability(Base):
    __tablename__ = "product_capabilities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cap"))
    capability_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    feature_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_evidence: Mapped[str] = mapped_column(Text, nullable=False)
    verification_date: Mapped[str] = mapped_column(String(32), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    suitable_use_cases: Mapped[list[str]] = mapped_column(JSON, default=list)
    limitations: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"
    __table_args__ = (
        Index("ix_outreach_creator_channel_step", "creator_id", "channel", "step_number"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("msg"))
    creator_id: Mapped[str] = mapped_column(String(64), ForeignKey("creators.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    step_label: Mapped[str] = mapped_column(String(64), nullable=False, default="First Contact")
    subject: Mapped[str | None] = mapped_column(String(256), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    referenced_content_title: Mapped[str] = mapped_column(String(512), nullable=False)
    referenced_content_url: Mapped[str] = mapped_column(String(512), nullable=False)
    referenced_capability_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
    cited_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    sender_identity: Mapped[str] = mapped_column(String(256), nullable=False)
    opt_out_text: Mapped[str] = mapped_column(String(256), nullable=False)
    validation_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    validation_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False, default="APPROVED")
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    creator: Mapped[Creator] = relationship(back_populates="outreach_messages")
    versions: Mapped[list[OutreachVersion]] = relationship(back_populates="message", cascade="all, delete-orphan")


class OutreachVersion(Base):
    __tablename__ = "outreach_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ver"))
    message_id: Mapped[str] = mapped_column(String(64), ForeignKey("outreach_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str | None] = mapped_column(String(256), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    edited_by: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    edit_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    validation_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    message: Mapped[OutreachMessage] = relationship(back_populates="versions")


class AuditRun(Base):
    __tablename__ = "audit_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("aud"))
    audit_type: Mapped[str] = mapped_column(String(64), nullable=False, default="full_audit")
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    total_qualified_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qualification_pass_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    contact_accuracy_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_market_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    represented_countries_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_single_country_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    geographic_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outreach_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    readiness_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_READY")
    summary_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    findings: Mapped[list[AuditFinding]] = relationship(back_populates="audit_run", cascade="all, delete-orphan")


class AuditFinding(Base):
    __tablename__ = "audit_findings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("fnd"))
    audit_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("audit_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    creator_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="WARNING")
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    audit_run: Mapped[AuditRun] = relationship(back_populates="findings")


class ManualReview(Base):
    __tablename__ = "manual_reviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("rev"))
    creator_id: Mapped[str] = mapped_column(String(64), ForeignKey("creators.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_username: Mapped[str] = mapped_column(String(128), nullable=False, default="admin")
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    criterion_overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    creator: Mapped[Creator] = relationship(back_populates="manual_reviews")


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("dsc"))
    keyword: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    countries: Mapped[list[str]] = mapped_column(JSON, default=list)
    max_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="youtube_api")
    run_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="live")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    discovered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deduplicated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qualified_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    needs_review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_log: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    checkpoints: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("job"))
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED", index=True)
    current_stage: Mapped[str] = mapped_column(String(128), nullable=False, default="INITIALIZING")
    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    can_retry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    input_params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    stage_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checkpoints: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_messages: Mapped[list[str]] = mapped_column(JSON, default=list)
    runtime_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RefreshHistory(Base):
    __tablename__ = "refresh_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("rfr"))
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_creators_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_creators_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_records_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stale_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalidated_qualifications_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_prevented_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    api_calls_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    runtime_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ApiUsage(Base):
    __tablename__ = "api_usage"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("api"))
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(256), nullable=False)
    operation: Mapped[str] = mapped_column(String(128), nullable=False)
    units_or_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SeedTestAccount(Base):
    __tablename__ = "seed_test_accounts"
    __table_args__ = (
        UniqueConstraint("channel", "handle_or_address", name="uq_seed_account_channel_addr"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("sta"))
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    handle_or_address: Mapped[str] = mapped_column(String(256), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_allowlisted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ownership_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SeedTestRun(Base):
    __tablename__ = "seed_test_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("str"))
    test_account_id: Mapped[str] = mapped_column(String(64), ForeignKey("seed_test_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    recipient_address: Mapped[str] = mapped_column(String(256), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="DRY_RUN")
    explicit_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SCHEDULED")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tracking_token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    tracking_url: Mapped[str] = mapped_column(String(512), nullable=False)
    message_preview: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_attachment_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_genuine_external_execution: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    execution_logs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    error_recovery_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tracking_events: Mapped[list[TrackingEvent]] = relationship(back_populates="seed_test_run", cascade="all, delete-orphan")
    reply_events: Mapped[list[ReplyEvent]] = relationship(back_populates="seed_test_run", cascade="all, delete-orphan")


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("trk"))
    seed_test_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("seed_test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, default="CLICK")
    tracking_token: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    seed_test_run: Mapped[SeedTestRun] = relationship(back_populates="tracking_events")


class ReplyEvent(Base):
    __tablename__ = "reply_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("rpl"))
    seed_test_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("seed_test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_address: Mapped[str] = mapped_column(String(256), nullable=False)
    reply_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_path_or_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_genuine_external_reply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    seed_test_run: Mapped[SeedTestRun] = relationship(back_populates="reply_events")


class SubmissionArtifact(Base):
    __tablename__ = "submission_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("art"))
    export_batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="GENERATED")
    contains_synthetic_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checksum_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProductInsight(Base):
    __tablename__ = "product_insights"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ins"))
    insight_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # OBSERVATION or OPPORTUNITY
    item_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_reference: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_url_or_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_verified_product_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
