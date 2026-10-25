from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.app.agents.agent1.contacts import extract_and_verify_contacts
from backend.app.agents.agent1.evidence import upsert_evidence
from backend.app.config import get_settings
from backend.app.database.models import Creator, Evidence, VerificationResult

EXCLUDED_ENTITY_KEYWORDS = [
    "talent management firm",
    "creator management firm",
    "full-service media agency",
    "marketing agency",
    "official fan club",
    "fan account",
    "unaffiliated fan",
    "business directory",
]

COMMERCIAL_KEYWORDS = [
    "sponsor",
    "sponsored by",
    "sponsorship",
    "course",
    "cohort",
    "coaching",
    "consulting",
    "consultant",
    "membership",
    "patreon",
    "substack",
    "newsletter",
    "affiliate",
    "partner",
    "merch",
    "store",
    "shop",
    "book a call",
    "program",
    "masterclass",
    "workshop",
    "academy",
    "training",
    "community",
    "founder",
    "ceo",
    "author",
    "speaker",
    "business",
    "entrepreneur",
    "investing",
    "wealth",
    "finance",
    "marketing",
    "leadership",
    "sales",
    "strategy",
    "clients",
    "services",
    "ad-free",
    "premium",
    "support the show",
    "promo",
    "discount",
    "career",
    "productivity",
    "technology",
    "coach",
    "advisor",
]

WORKFLOW_NEED_KEYWORDS = [
    "repurpos",
    "short-form",
    "shorts",
    "reels",
    "clips",
    "clip",
    "video editor",
    "editing",
    "caption",
    "subtitle",
    "transcript",
    "post-production",
    "backlog",
    "publishing consistency",
    "weekly podcast",
    "weekly episode",
    "multi-channel",
    "content workflow",
    "team workflow",
    "turnaround",
    "new episode",
    "every week",
    "each week",
    "weekly",
    "daily",
    "show notes",
    "interviews",
    "conversations",
    "hosted by",
    "produced by",
    "subscribe",
    "episodes",
    "podcast",
    "educator",
    "teaching",
    "lessons",
    "strategies",
    "insights",
]


def verify_creator_qualification(
    db: Session,
    creator: Creator,
    reference_now: datetime | None = None,
) -> VerificationResult:
    """Perform all required IncuBrix qualification checks with working source evidence."""
    now = reference_now or datetime.now(timezone.utc)
    settings = get_settings()
    scoring_cfg = settings.load_json_config("scoring.json")
    excluded_categories = {c.lower() for c in scoring_cfg.get("excluded_categories", [])}
    target_segments = {c.lower() for c in scoring_cfg.get("target_segments", [])}

    failed_criteria: list[str] = []
    uncertain_criteria: list[str] = []
    evidence_ids: list[str] = []

    text_blobs = [creator.description or ""]
    for item in creator.content_items:
        text_blobs.append(f"{item.title} {item.description or ''}")
    combined_text = "\n".join(text_blobs)
    lower_text = combined_text.lower()

    # 1. Real and Relevant (Segment & Excluded entity check)
    is_excluded_cat = creator.category.strip().lower() in excluded_categories
    matched_excluded_kw = next((kw for kw in EXCLUDED_ENTITY_KEYWORDS if kw in lower_text), None)
    has_stable_id = bool(creator.platform_id and len(creator.platform_id.strip()) >= 4)
    has_official_url = bool(creator.official_url and creator.official_url.startswith("http"))

    if is_excluded_cat or matched_excluded_kw or not has_stable_id or not has_official_url:
        real_and_relevant = False
        failed_criteria.append("real_and_relevant")
        ev_rel = upsert_evidence(
            db,
            creator.id,
            "real_and_relevant",
            creator.official_url or "https://invalid.local",
            f"Excluded category/entity detected ({creator.category} / {matched_excluded_kw}) or missing stable ID.",
            verification_status="REJECTED",
            checked_at=now,
        )
        evidence_ids.append(ev_rel.id)
    else:
        real_and_relevant = True
        ev_rel = upsert_evidence(
            db,
            creator.id,
            "real_and_relevant",
            creator.official_url,
            f"Verified official creator profile '{creator.name}' ({creator.category}) with stable ID {creator.platform_id}.",
            verification_status="VERIFIED",
            checked_at=now,
        )
        evidence_ids.append(ev_rel.id)

    # 2. Active check: >= 8 items in last 30 days OR >= 2 long-form items in last 60 days
    cutoff_30d = now - timedelta(days=30)
    cutoff_60d = now - timedelta(days=60)
    items_30d = 0
    longform_60d = 0
    latest_item_url = creator.official_url
    latest_pub_dt: datetime | None = None

    for item in creator.content_items:
        pub = item.published_at
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        if latest_pub_dt is None or pub > latest_pub_dt:
            latest_pub_dt = pub
            latest_item_url = item.url
        if pub >= cutoff_30d:
            items_30d += 1
        if pub >= cutoff_60d and (item.is_longform or item.duration_seconds >= 600):
            longform_60d += 1

    creator.items_30d = items_30d
    creator.longform_60d = longform_60d
    active_check = (items_30d >= 8) or (longform_60d >= 2)

    if active_check:
        ev_act = upsert_evidence(
            db,
            creator.id,
            "active_publishing",
            latest_item_url,
            f"Published {items_30d} items in last 30 days and {longform_60d} long-form items in last 60 days.",
            verification_status="VERIFIED",
            source_published_at=latest_pub_dt,
            checked_at=now,
        )
        evidence_ids.append(ev_act.id)
    else:
        uncertain_criteria.append("active_publishing")
        ev_act = upsert_evidence(
            db,
            creator.id,
            "active_publishing",
            latest_item_url,
            f"Insufficient recent activity: {items_30d} items in 30d (need 8) and {longform_60d} long-form in 60d (need 2).",
            verification_status="NEEDS_REVIEW",
            source_published_at=latest_pub_dt,
            checked_at=now,
        )
        evidence_ids.append(ev_act.id)

    # 3. Commercial activity check
    existing_comm_ev = (
        db.query(Evidence)
        .filter(Evidence.creator_id == creator.id, Evidence.criterion == "commercial_activity")
        .first()
    )
    if existing_comm_ev and existing_comm_ev.is_manual_override and existing_comm_ev.verification_status == "VERIFIED":
        commercial_check = True
        evidence_ids.append(existing_comm_ev.id)
    else:
        matched_comm = [kw for kw in COMMERCIAL_KEYWORDS if kw in lower_text]
        if matched_comm:
            commercial_check = True
            snippet = _extract_matching_sentence(combined_text, matched_comm[0])
            ev_comm = upsert_evidence(
                db,
                creator.id,
                "commercial_activity",
                latest_item_url,
                f"Public commercial evidence ({', '.join(matched_comm[:3])}): \"{snippet}\"",
                verification_status="VERIFIED",
                source_published_at=latest_pub_dt,
                checked_at=now,
            )
            evidence_ids.append(ev_comm.id)
        else:
            commercial_check = False
            uncertain_criteria.append("commercial_activity")
            ev_comm = upsert_evidence(
                db,
                creator.id,
                "commercial_activity",
                creator.official_url,
                "Monetisation/commercial offer could not be deterministically confirmed from public text; requires review.",
                verification_status="NEEDS_REVIEW",
                checked_at=now,
            )
            evidence_ids.append(ev_comm.id)

    # 4. Needs IncuBrix workflow check
    existing_need_ev = (
        db.query(Evidence)
        .filter(Evidence.creator_id == creator.id, Evidence.criterion == "needs_incubrix")
        .first()
    )
    if existing_need_ev and existing_need_ev.is_manual_override and existing_need_ev.verification_status == "VERIFIED":
        needs_incubrix_check = True
        evidence_ids.append(existing_need_ev.id)
    else:
        matched_needs = [kw for kw in WORKFLOW_NEED_KEYWORDS if kw in lower_text]
        if matched_needs:
            needs_incubrix_check = True
            snippet = _extract_matching_sentence(combined_text, matched_needs[0])
            ev_need = upsert_evidence(
                db,
                creator.id,
                "needs_incubrix",
                latest_item_url,
                f"Public content/repurposing workflow need ({', '.join(matched_needs[:3])}): \"{snippet}\"",
                verification_status="VERIFIED",
                source_published_at=latest_pub_dt,
                checked_at=now,
            )
            evidence_ids.append(ev_need.id)
        else:
            needs_incubrix_check = False
            uncertain_criteria.append("needs_incubrix")
            ev_need = upsert_evidence(
                db,
                creator.id,
                "needs_incubrix",
                creator.official_url,
                "No explicit workflow/repurposing/editing pain point verified yet; marked NEEDS_REVIEW.",
                verification_status="NEEDS_REVIEW",
                checked_at=now,
            )
            evidence_ids.append(ev_need.id)

    # 5. Country check (never guess country; if UNKNOWN -> NEEDS_REVIEW)
    country_val = (creator.country or "UNKNOWN").strip()
    if country_val.upper() == "UNKNOWN" or not country_val:
        creator.country = "UNKNOWN"
        country_check = False
        uncertain_criteria.append("country")
        ev_ctry = upsert_evidence(
            db,
            creator.id,
            "country",
            creator.official_url,
            "Creator country is UNKNOWN in public metadata. Never inferred from name or accent.",
            verification_status="NEEDS_REVIEW",
            checked_at=now,
        )
        evidence_ids.append(ev_ctry.id)
    else:
        country_check = True
        ev_ctry = upsert_evidence(
            db,
            creator.id,
            "country",
            creator.official_url,
            f"Verified public country metadata: {creator.country}.",
            verification_status="VERIFIED",
            checked_at=now,
        )
        evidence_ids.append(ev_ctry.id)

    # 6. Language check (recent content mainly in English)
    lang_val = (creator.language or " UNKNOWN").strip().lower()
    ascii_ratio = sum(1 for ch in combined_text if ord(ch) < 128) / max(1, len(combined_text))
    is_english = lang_val.startswith("en") and ascii_ratio >= 0.85
    if is_english:
        language_check = True
        ev_lang = upsert_evidence(
            db,
            creator.id,
            "language",
            latest_item_url,
            f"Verified English content language (code='{creator.language}', ASCII ratio={ascii_ratio:.2f}).",
            verification_status="VERIFIED",
            checked_at=now,
        )
        evidence_ids.append(ev_lang.id)
    else:
        language_check = False
        failed_criteria.append("language")
        ev_lang = upsert_evidence(
            db,
            creator.id,
            "language",
            latest_item_url,
            f"Recent content is not verified as mainly English (code='{creator.language}').",
            verification_status="REJECTED",
            checked_at=now,
        )
        evidence_ids.append(ev_lang.id)

    # 7. Reachable business contact check (public, business, active within 60 days)
    contacts = extract_and_verify_contacts(db, creator, reference_now=now)
    valid_contacts = [c for c in contacts if c.is_verified and c.is_business_contact and c.active_within_60d]
    if valid_contacts:
        reachable_check = True
        for c in valid_contacts:
            if c.evidence_id and c.evidence_id not in evidence_ids:
                evidence_ids.append(c.evidence_id)
    else:
        reachable_check = False
        uncertain_criteria.append("reachable_contact")

    # 8. Evidence freshness check (all evidence checked within preceding 30 days)
    cutoff_freshness = now - timedelta(days=30)
    creator_evidences = db.query(Evidence).filter(Evidence.creator_id == creator.id).all()
    stale_evidences = []
    for ev in creator_evidences:
        chk = ev.checked_at
        if chk.tzinfo is None:
            chk = chk.replace(tzinfo=timezone.utc)
        if chk < cutoff_freshness:
            stale_evidences.append(ev.id)
    freshness_check = len(stale_evidences) == 0
    if not freshness_check:
        uncertain_criteria.append("evidence_freshness")

    # Final qualification decision
    if failed_criteria:
        overall_status = "REJECTED"
    elif (
        real_and_relevant
        and active_check
        and commercial_check
        and needs_incubrix_check
        and country_check
        and language_check
        and reachable_check
        and freshness_check
    ):
        overall_status = "QUALIFIED"
    else:
        overall_status = "NEEDS_REVIEW"

    creator.qualification_status = overall_status
    creator.last_checked_at = now

    verif = (
        db.query(VerificationResult)
        .filter(VerificationResult.creator_id == creator.id)
        .first()
    )
    summary_text = (
        f"Status={overall_status} | Active(30d={items_30d}, 60d_long={longform_60d}) | "
        f"Failed={failed_criteria} | NeedsReview={uncertain_criteria}"
    )

    if verif:
        verif.real_and_relevant = real_and_relevant
        verif.active_check = active_check
        verif.commercial_check = commercial_check
        verif.needs_incubrix_check = needs_incubrix_check
        verif.country_check = country_check
        verif.language_check = language_check
        verif.reachable_check = reachable_check
        verif.freshness_check = freshness_check
        verif.overall_status = overall_status
        verif.failed_criteria = failed_criteria
        verif.uncertain_criteria = uncertain_criteria
        verif.evidence_ids = evidence_ids
        verif.summary_notes = summary_text
        verif.checked_at = now
    else:
        verif = VerificationResult(
            creator_id=creator.id,
            real_and_relevant=real_and_relevant,
            active_check=active_check,
            commercial_check=commercial_check,
            needs_incubrix_check=needs_incubrix_check,
            country_check=country_check,
            language_check=language_check,
            reachable_check=reachable_check,
            freshness_check=freshness_check,
            overall_status=overall_status,
            failed_criteria=failed_criteria,
            uncertain_criteria=uncertain_criteria,
            evidence_ids=evidence_ids,
            summary_notes=summary_text,
            checked_at=now,
        )
        db.add(verif)

    db.flush()
    return verif


def _extract_matching_sentence(text: str, keyword: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    kw_lower = keyword.lower()
    for s in sentences:
        if kw_lower in s.lower():
            return s.strip()[:260]
    return text.strip()[:260]
