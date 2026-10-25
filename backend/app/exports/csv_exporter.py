from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.database.models import (
    ApiUsage,
    ChannelDecision,
    Creator,
    Evidence,
    LeadScore,
)

OFFICIAL_LEADS_CSV_COLUMNS = [
    "creator_id",
    "creator_name",
    "platform",
    "platform_id",
    "official_url",
    "category",
    "niche",
    "country",
    "language",
    "items_30d",
    "longform_60d",
    "commercial_evidence_url",
    "commercial_excerpt",
    "workflow_need_evidence_url",
    "workflow_need_excerpt",
    "primary_channel",
    "primary_contact_handle_or_url",
    "backup_channel",
    "backup_contact_handle_or_url",
    "lead_score",
    "priority_tier",
    "rank_position",
    "evidence_checked_at",
    "is_synthetic",
]


def compute_file_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def export_leads_csv(
    db: Session,
    output_path: Path,
    include_synthetic: bool = True,
    custom_columns: list[str] | None = None,
) -> dict[str, Any]:
    """Export qualified creators to leads.csv without duplicates or incomplete rows."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = custom_columns or OFFICIAL_LEADS_CSV_COLUMNS

    query = db.query(Creator).filter(Creator.qualification_status == "QUALIFIED")
    if not include_synthetic:
        query = query.filter(Creator.is_synthetic.is_(False))
    creators = query.all()

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    contains_synthetic = False

    for c in creators:
        if c.platform_id in seen_ids:
            continue
        seen_ids.add(c.platform_id)
        if c.is_synthetic:
            contains_synthetic = True

        evidences = db.query(Evidence).filter(Evidence.creator_id == c.id).all()
        ev_map = {e.criterion: e for e in evidences}
        score_obj = db.query(LeadScore).filter(LeadScore.creator_id == c.id).first()
        decision = db.query(ChannelDecision).filter(ChannelDecision.creator_id == c.id).first()

        comm_ev = ev_map.get("commercial_activity")
        need_ev = ev_map.get("needs_incubrix")

        row_dict = {
            "creator_id": c.id,
            "creator_name": c.name,
            "platform": c.platform,
            "platform_id": c.platform_id,
            "official_url": c.official_url,
            "category": c.category,
            "niche": c.niche or "General Creator",
            "country": c.country,
            "language": c.language,
            "items_30d": c.items_30d,
            "longform_60d": c.longform_60d,
            "commercial_evidence_url": comm_ev.source_url if comm_ev else c.official_url,
            "commercial_excerpt": comm_ev.excerpt if comm_ev else "",
            "workflow_need_evidence_url": need_ev.source_url if need_ev else c.official_url,
            "workflow_need_excerpt": need_ev.excerpt if need_ev else "",
            "primary_channel": decision.primary_channel if decision else "",
            "primary_contact_handle_or_url": decision.primary_contact_value if decision else "",
            "backup_channel": (decision.backup_channel or "") if decision else "",
            "backup_contact_handle_or_url": (decision.backup_contact_value or "") if decision else "",
            "lead_score": score_obj.total_score if score_obj else 0.0,
            "priority_tier": c.priority_tier or (score_obj.priority_tier if score_obj else "Priority C"),
            "rank_position": c.rank_position or (score_obj.rank_position if score_obj else 999),
            "evidence_checked_at": c.last_checked_at.isoformat() if c.last_checked_at else "",
            "is_synthetic": c.is_synthetic,
        }
        rows.append(row_dict)

    rows.sort(key=lambda r: (int(r.get("rank_position") or 9999), str(r.get("creator_id"))))

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    return {
        "file_path": str(output_path),
        "record_count": len(rows),
        "contains_synthetic": contains_synthetic,
        "checksum_sha256": compute_file_sha256(output_path),
    }


def export_evidence_index_csv(db: Session, output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    evidences = db.query(Evidence).order_by(Evidence.checked_at.desc()).all()
    cols = [
        "evidence_id",
        "creator_id",
        "criterion",
        "source_url",
        "excerpt",
        "source_published_at",
        "checked_at",
        "verification_method",
        "verification_status",
        "is_manual_override",
        "reviewer_notes",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for ev in evidences:
            writer.writerow(
                {
                    "evidence_id": ev.id,
                    "creator_id": ev.creator_id,
                    "criterion": ev.criterion,
                    "source_url": ev.source_url,
                    "excerpt": ev.excerpt,
                    "source_published_at": ev.source_published_at.isoformat() if ev.source_published_at else "",
                    "checked_at": ev.checked_at.isoformat() if ev.checked_at else "",
                    "verification_method": ev.verification_method,
                    "verification_status": ev.verification_status,
                    "is_manual_override": ev.is_manual_override,
                    "reviewer_notes": ev.reviewer_notes or "",
                }
            )
    return {
        "file_path": str(output_path),
        "record_count": len(evidences),
        "checksum_sha256": compute_file_sha256(output_path),
    }


def export_runtime_costs_csv(db: Session, output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    usages = db.query(ApiUsage).order_by(ApiUsage.recorded_at.desc()).all()
    cols = [
        "usage_id",
        "provider",
        "endpoint",
        "operation",
        "units_or_tokens",
        "estimated_cost_usd",
        "status_code",
        "success",
        "latency_ms",
        "error_detail",
        "recorded_at",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for u in usages:
            writer.writerow(
                {
                    "usage_id": u.id,
                    "provider": u.provider,
                    "endpoint": u.endpoint,
                    "operation": u.operation,
                    "units_or_tokens": u.units_or_tokens,
                    "estimated_cost_usd": u.estimated_cost_usd,
                    "status_code": u.status_code,
                    "success": u.success,
                    "latency_ms": u.latency_ms,
                    "error_detail": u.error_detail or "",
                    "recorded_at": u.recorded_at.isoformat() if u.recorded_at else "",
                }
            )
    return {
        "file_path": str(output_path),
        "record_count": len(usages),
        "checksum_sha256": compute_file_sha256(output_path),
    }
