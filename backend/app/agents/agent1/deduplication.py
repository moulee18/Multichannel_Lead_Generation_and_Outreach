from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from backend.app.database.models import Creator


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlsplit(url.strip())
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/").lower()
    return f"{host}{path}"


def compute_candidate_hash(candidate: dict[str, Any]) -> str:
    stable_payload = {
        "platform": candidate.get("platform"),
        "platform_id": candidate.get("platform_id"),
        "name": candidate.get("name"),
        "country": candidate.get("country"),
        "description": candidate.get("description"),
        "content_ids": sorted(
            str(c.get("external_id", "")) for c in (candidate.get("content_items") or [])
        ),
    }
    raw = json.dumps(stable_payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def deduplicate_candidates(
    db: Session,
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Deduplicate incoming candidate dictionaries against each other and flag existing DB records."""
    unique_candidates: list[dict[str, Any]] = []
    seen_platform_ids: set[tuple[str, str]] = set()
    seen_urls: set[str] = set()
    duplicates_removed = 0

    for cand in candidates:
        platform = str(cand.get("platform") or "youtube").strip().lower()
        platform_id = str(cand.get("platform_id") or "").strip()
        norm_url = normalize_url(cand.get("official_url"))

        if not platform_id:
            duplicates_removed += 1
            continue

        key = (platform, platform_id)
        if key in seen_platform_ids or (norm_url and norm_url in seen_urls):
            duplicates_removed += 1
            continue

        seen_platform_ids.add(key)
        if norm_url:
            seen_urls.add(norm_url)
        unique_candidates.append(cand)

    return unique_candidates, duplicates_removed


def find_existing_creator(db: Session, candidate: dict[str, Any]) -> Creator | None:
    platform = str(candidate.get("platform") or "youtube").strip().lower()
    platform_id = str(candidate.get("platform_id") or "").strip()
    existing = (
        db.query(Creator)
        .filter(Creator.platform == platform, Creator.platform_id == platform_id)
        .first()
    )
    if existing:
        return existing
    official_url = str(candidate.get("official_url") or "").strip()
    if official_url:
        existing_by_url = db.query(Creator).filter(Creator.official_url == official_url).first()
        if existing_by_url:
            return existing_by_url
    return None
