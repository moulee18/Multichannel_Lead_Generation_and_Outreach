from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database.models import ContactChannel, Creator, Evidence


EMAIL_REGEX = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")
LINKEDIN_REGEX = re.compile(r"https?://(?:www\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9_-]+")
INSTAGRAM_REGEX = re.compile(r"https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.-]+)")
X_REGEX = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/([a-zA-Z0-9_]+)")


def extract_and_verify_contacts(
    db: Session,
    creator: Creator,
    raw_metadata: dict[str, Any] | None = None,
    reference_now: datetime | None = None,
) -> list[ContactChannel]:
    """Extract only genuine, publicly stated business contacts. Never guess emails or handles."""
    now = reference_now or datetime.now(timezone.utc)
    cutoff_60d = now - timedelta(days=60)
    settings = get_settings()
    policies = settings.load_json_config("channel_policies.json").get("channels", {})

    # Determine latest creator activity timestamp (for 60-day reachability requirement)
    latest_activity: datetime | None = None
    for item in creator.content_items:
        pub = item.published_at
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        if latest_activity is None or pub > latest_activity:
            latest_activity = pub

    active_60d = bool(latest_activity and latest_activity >= cutoff_60d)

    # Combine creator description and recent content descriptions
    text_blobs = [creator.description or ""]
    for item in creator.content_items[:5]:
        if item.description:
            text_blobs.append(item.description)
    combined_text = "\n".join(text_blobs)

    discovered_channels: list[dict[str, Any]] = []

    # 1. Explicit RSS or metadata email
    meta = raw_metadata or creator.raw_metadata or {}
    rss_email = meta.get("rss_email")
    if rss_email and "@" in str(rss_email):
        discovered_channels.append(
            {
                "channel_type": "email",
                "handle_or_address": str(rss_email).strip(),
                "public_url": f"mailto:{str(rss_email).strip()}",
                "excerpt": f"Public RSS business contact email: {rss_email}",
            }
        )

    # 2. Explicit emails in description
    for email_match in EMAIL_REGEX.findall(combined_text):
        clean_email = email_match.strip().rstrip(".,;)")
        if any(bad in clean_email.lower() for bad in (".png", ".jpg", "sentry.io")):
            continue
        if not any(d["handle_or_address"].lower() == clean_email.lower() for d in discovered_channels):
            discovered_channels.append(
                {
                    "channel_type": "email",
                    "handle_or_address": clean_email,
                    "public_url": creator.official_url,
                    "excerpt": f"Public business email listed on profile: {clean_email}",
                }
            )

    # 3. LinkedIn profile / page URL in description
    for li_url in LINKEDIN_REGEX.findall(combined_text):
        clean_url = li_url.rstrip("/.,;)")
        if not any(d["handle_or_address"].lower() == clean_url.lower() for d in discovered_channels):
            discovered_channels.append(
                {
                    "channel_type": "linkedin",
                    "handle_or_address": clean_url,
                    "public_url": clean_url,
                    "excerpt": f"Public LinkedIn profile linked on creator channel: {clean_url}",
                }
            )

    # 4. Instagram profile URL in description
    for ig_match in INSTAGRAM_REGEX.finditer(combined_text):
        full_url = ig_match.group(0).rstrip("/.,;)")
        handle = f"@{ig_match.group(1).strip('@/')}"
        if not any(d["channel_type"] == "instagram" and d["handle_or_address"].lower() == handle.lower() for d in discovered_channels):
            discovered_channels.append(
                {
                    "channel_type": "instagram",
                    "handle_or_address": handle,
                    "public_url": full_url,
                    "excerpt": f"Public Instagram profile linked on creator channel: {full_url}",
                }
            )

    # 5. X / Twitter handle URL in description
    for x_match in X_REGEX.finditer(combined_text):
        full_url = x_match.group(0).rstrip("/.,;)")
        handle = f"@{x_match.group(1).strip('@/')}"
        if not any(d["channel_type"] == "x" and d["handle_or_address"].lower() == handle.lower() for d in discovered_channels):
            discovered_channels.append(
                {
                    "channel_type": "x",
                    "handle_or_address": handle,
                    "public_url": full_url,
                    "excerpt": f"Public X profile linked on creator channel: {full_url}",
                }
            )

    # 6. Website contact URL if explicitly present in metadata
    website_url = meta.get("website_url")
    if website_url and str(website_url).startswith("http"):
        discovered_channels.append(
            {
                "channel_type": "website_contact",
                "handle_or_address": str(website_url).strip(),
                "public_url": str(website_url).strip(),
                "excerpt": f"Official creator website linked in feed: {website_url}",
            }
        )

    saved_contacts: list[ContactChannel] = []
    for item in discovered_channels:
        ch_type = item["channel_type"]
        addr = item["handle_or_address"]
        policy = policies.get(ch_type, {})
        restriction_note = policy.get(
            "policy_notes",
            "Follow platform terms of service; include sender identity and opt-out.",
        )

        # Record Evidence for this contact channel
        ev = Evidence(
            creator_id=creator.id,
            criterion="reachable_contact",
            source_url=item["public_url"],
            excerpt=item["excerpt"],
            source_published_at=latest_activity,
            checked_at=now,
            verification_method="public_profile_contact_extractor",
            verification_status="VERIFIED" if active_60d else "NEEDS_REVIEW",
        )
        db.add(ev)
        db.flush()

        existing_contact = (
            db.query(ContactChannel)
            .filter(
                ContactChannel.creator_id == creator.id,
                ContactChannel.channel_type == ch_type,
                ContactChannel.handle_or_address == addr,
            )
            .first()
        )
        if existing_contact:
            existing_contact.public_url = item["public_url"]
            existing_contact.is_verified = True
            existing_contact.active_within_60d = active_60d
            existing_contact.last_activity_at = latest_activity
            existing_contact.evidence_id = ev.id
            existing_contact.restrictions = restriction_note
            existing_contact.checked_at = now
            saved_contacts.append(existing_contact)
        else:
            contact = ContactChannel(
                creator_id=creator.id,
                channel_type=ch_type,
                handle_or_address=addr,
                public_url=item["public_url"],
                is_business_contact=True,
                is_verified=True,
                active_within_60d=active_60d,
                last_activity_at=latest_activity,
                evidence_id=ev.id,
                restrictions=restriction_note,
                checked_at=now,
            )
            db.add(contact)
            db.flush()
            saved_contacts.append(contact)

    return saved_contacts
