from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database.models import (
    ChannelDecision,
    ContactChannel,
    Creator,
    Evidence,
)


def run_independent_qualification_and_geo_audit(
    db: Session,
    include_synthetic: bool = True,
    reference_now: datetime | None = None,
) -> dict[str, Any]:
    """Independently re-audit all QUALIFIED creators without trusting Agent 1's status flag."""
    now = reference_now or datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)
    cutoff_60d = now - timedelta(days=60)
    settings = get_settings()
    scoring_cfg = settings.load_json_config("scoring.json")
    approved_countries = set(scoring_cfg.get("approved_countries", []))
    excluded_categories = {c.lower() for c in scoring_cfg.get("excluded_categories", [])}

    query = db.query(Creator).filter(Creator.qualification_status == "QUALIFIED")
    if not include_synthetic:
        query = query.filter(Creator.is_synthetic.is_(False))
    qualified_creators = query.all()

    seen_platform_ids: set[tuple[str, str]] = set()
    seen_urls: set[str] = set()
    duplicate_records: list[str] = []
    creator_audit_results: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    country_counter: Counter[str] = Counter()
    missing_country_count = 0

    for creator in qualified_creators:
        key = (creator.platform.lower(), creator.platform_id.strip())
        norm_url = creator.official_url.strip().lower().rstrip("/")
        is_duplicate = False
        if key in seen_platform_ids or norm_url in seen_urls:
            is_duplicate = True
            duplicate_records.append(creator.id)
        seen_platform_ids.add(key)
        seen_urls.add(norm_url)

        evidences = db.query(Evidence).filter(Evidence.creator_id == creator.id).all()
        ev_by_crit = {e.criterion: e for e in evidences if e.verification_status == "VERIFIED"}
        contacts = (
            db.query(ContactChannel)
            .filter(
                ContactChannel.creator_id == creator.id,
                ContactChannel.is_verified.is_(True),
                ContactChannel.is_business_contact.is_(True),
                ContactChannel.active_within_60d.is_(True),
            )
            .all()
        )
        decision = db.query(ChannelDecision).filter(ChannelDecision.creator_id == creator.id).first()

        # Recompute activity from raw ContentItems
        items_30d = 0
        longform_60d = 0
        for ci in creator.content_items:
            pub = ci.published_at if ci.published_at.tzinfo else ci.published_at.replace(tzinfo=timezone.utc)
            if pub >= cutoff_30d:
                items_30d += 1
            if pub >= cutoff_60d and (ci.is_longform or ci.duration_seconds >= 600):
                longform_60d += 1

        # Freshness check: every verified evidence checked within 30 days
        all_fresh = True
        for ev in evidences:
            chk = ev.checked_at if ev.checked_at.tzinfo else ev.checked_at.replace(tzinfo=timezone.utc)
            if chk < cutoff_30d:
                all_fresh = False

        checks = {
            "segment_valid": creator.category.lower() not in excluded_categories and "real_and_relevant" in ev_by_crit,
            "official_identity": bool(creator.platform_id and creator.official_url.startswith("http")),
            "geographic_evidence": bool(creator.country and creator.country != "UNKNOWN" and "country" in ev_by_crit),
            "language_evidence": bool(creator.language.lower().startswith("en") and "language" in ev_by_crit),
            "recent_activity": (items_30d >= 8) or (longform_60d >= 2),
            "commercial_activity": "commercial_activity" in ev_by_crit,
            "workflow_needs": "needs_incubrix" in ev_by_crit,
            "reachable_contact": len(contacts) >= 1 and decision is not None,
            "evidence_fresh_30d": all_fresh and len(evidences) >= 5,
            "unique_record": not is_duplicate,
        }

        failed_rules = [k for k, v in checks.items() if not v]
        passed_all = len(failed_rules) == 0
        contact_accurate = checks["reachable_contact"] and bool(decision and decision.primary_contact_value)

        if not creator.country or creator.country == "UNKNOWN":
            missing_country_count += 1
        else:
            country_counter[creator.country] += 1

        if not passed_all:
            findings.append(
                {
                    "creator_id": creator.id,
                    "category": "QUALIFICATION_AUDIT",
                    "severity": "ERROR",
                    "passed": False,
                    "rule_code": "INDEPENDENT_QUAL_CHECK",
                    "description": f"Creator '{creator.name}' failed independent audit rules: {failed_rules}",
                    "evidence_urls": [e.source_url for e in evidences[:3]],
                }
            )

        creator_audit_results.append(
            {
                "creator_id": creator.id,
                "name": creator.name,
                "country": creator.country,
                "category": creator.category,
                "is_synthetic": creator.is_synthetic,
                "passed_all": passed_all,
                "contact_accurate": contact_accurate,
                "checks": checks,
                "failed_rules": failed_rules,
                "evidence_count": len(evidences),
                "evidence_urls": [e.source_url for e in evidences],
            }
        )

    total = len(qualified_creators)
    passed_count = sum(1 for r in creator_audit_results if r["passed_all"])
    contact_ok_count = sum(1 for r in creator_audit_results if r["contact_accurate"])

    qual_pass_rate = round((passed_count / total) * 100.0, 2) if total > 0 else 0.0
    contact_acc_rate = round((contact_ok_count / total) * 100.0, 2) if total > 0 else 0.0

    # Geographic audit calculations
    approved_count = sum(cnt for ctry, cnt in country_counter.items() if ctry in approved_countries)
    approved_pct = round((approved_count / total) * 100.0, 2) if total > 0 else 0.0
    represented_countries = len([c for c, cnt in country_counter.items() if cnt > 0])
    max_single_country_pct = (
        round((max(country_counter.values()) / total) * 100.0, 2)
        if total > 0 and country_counter
        else 0.0
    )

    geo_failures: list[str] = []
    if total == 0:
        geo_failures.append("No qualified creators available to evaluate geographic distribution.")
    else:
        if approved_pct < 80.0:
            geo_failures.append(f"Approved market share is {approved_pct}% (minimum required is 80.0%).")
        if represented_countries < 3:
            geo_failures.append(f"Only {represented_countries} countries represented (minimum required is 3).")
        if max_single_country_pct > 60.0:
            geo_failures.append(f"Largest single country share is {max_single_country_pct}% (maximum allowed is 60.0%).")
        if missing_country_count > 0:
            geo_failures.append(f"{missing_country_count} qualified record(s) have UNKNOWN country evidence.")

    geo_compliant = len(geo_failures) == 0 and total > 0
    for gf in geo_failures:
        findings.append(
            {
                "creator_id": None,
                "category": "GEOGRAPHIC_COMPLIANCE",
                "severity": "ERROR",
                "passed": False,
                "rule_code": "GEO_DISTRIBUTION_RULE",
                "description": gf,
                "evidence_urls": [],
            }
        )

    return {
        "total_qualified_checked": total,
        "qualification_pass_rate": qual_pass_rate,
        "contact_accuracy_rate": contact_acc_rate,
        "duplicate_count": len(duplicate_records),
        "duplicate_creator_ids": duplicate_records,
        "creator_audit_results": creator_audit_results,
        "geographic_audit": {
            "country_distribution": dict(country_counter),
            "approved_market_pct": approved_pct,
            "represented_countries_count": represented_countries,
            "max_single_country_pct": max_single_country_pct,
            "missing_country_evidence_count": missing_country_count,
            "compliant": geo_compliant,
            "failures": geo_failures,
        },
        "findings": findings,
    }
