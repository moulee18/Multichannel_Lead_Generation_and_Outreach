from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.database.models import Creator, Evidence, ProductCapability


FORBIDDEN_UNCONFIRMED_CLAIMS = [
    "guaranteed viral",
    "10x your subscribers overnight",
    "automated deepfake avatar",
    "buy followers",
    "auto-dm 10,000 users",
    "official incubrix employee",
    "i work at incubrix",
]


class AIHallucinationGuard:
    """Feature 3 — AI Hallucination Guard.
    Deterministically checks AI-generated intelligence and outreach messages against
    stored creator evidence, content URLs, freshness rules, and confirmed product capabilities.
    """

    @staticmethod
    def validate_intelligence(
        creator: Creator,
        evidence_list: list[Evidence],
        capabilities: list[ProductCapability],
        intelligence_payload: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        flags: list[str] = []
        valid_evidence_ids = {ev.id for ev in evidence_list}
        confirmed_cap_keys = {cap.capability_key for cap in capabilities if cap.confirmed}

        cited_ids = intelligence_payload.get("cited_evidence_ids") or []
        if not cited_ids:
            flags.append("MISSING_SOURCE_REFERENCES: Intelligence record cites zero evidence IDs.")
        for cid in cited_ids:
            if cid not in valid_evidence_ids:
                flags.append(f"UNSUPPORTED_EVIDENCE_ID: Cited evidence ID '{cid}' does not exist for creator.")

        for cap_key in intelligence_payload.get("suitable_capabilities") or []:
            if cap_key not in confirmed_cap_keys:
                flags.append(f"INVENTED_PRODUCT_CLAIM: Capability '{cap_key}' is not in confirmed registry.")

        need_evidence = [ev for ev in evidence_list if ev.criterion == "needs_incubrix" and ev.verification_status == "VERIFIED"]
        if not need_evidence and intelligence_payload.get("pain_points"):
            flags.append("UNSUPPORTED_CREATOR_CLAIM: Pain points listed without verified needs_incubrix evidence.")

        # Check outdated evidence (>30 days)
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        for ev in evidence_list:
            if ev.id in cited_ids:
                checked = ev.checked_at
                if checked.tzinfo is None:
                    checked = checked.replace(tzinfo=timezone.utc)
                if checked < cutoff:
                    flags.append(f"OUTDATED_EVIDENCE: Cited evidence '{ev.id}' was checked more than 30 days ago.")

        return (len(flags) == 0), flags

    @staticmethod
    def validate_outreach_message(
        creator: Creator,
        body: str,
        subject: str | None,
        channel: str,
        referenced_content_title: str,
        referenced_content_url: str,
        referenced_capability_keys: list[str],
        cited_evidence_ids: list[str],
        sender_identity: str,
        opt_out_text: str,
        evidence_list: list[Evidence],
        capabilities: list[ProductCapability],
        max_length: int = 1500,
    ) -> tuple[bool, list[str]]:
        flags: list[str] = []
        combined_text = f"{subject or ''}\n{body}".strip()
        lower_text = combined_text.lower()

        # 1. Creator identity check
        creator_name_tokens = [tok.lower() for tok in re.split(r"\W+", creator.name) if len(tok) >= 3]
        if creator.name.lower() not in lower_text and not any(tok in lower_text for tok in creator_name_tokens[:2]):
            flags.append("INCONSISTENT_CREATOR_IDENTITY: Message does not reference the creator's verified name.")

        # 2. Specific recent content reference check
        if not referenced_content_title or referenced_content_title.lower() not in lower_text:
            flags.append("MISSING_CONTENT_REFERENCE: Message body must explicitly mention the referenced recent content title.")

        known_urls = {c.url for c in creator.content_items} | {ev.source_url for ev in evidence_list} | {creator.official_url}
        if referenced_content_url not in known_urls:
            flags.append(f"INVENTED_URL: Referenced content URL '{referenced_content_url}' is not in stored creator records.")

        # 3. Check any URLs embedded in message body
        urls_in_body = re.findall(r"https?://[^\s)>\"]+", body)
        for u in urls_in_body:
            clean_u = u.rstrip(".,;)")
            if clean_u not in known_urls and "127.0.0.1" not in clean_u and "localhost" not in clean_u and "incubrix.com" not in clean_u:
                flags.append(f"INVENTED_URL_IN_BODY: URL '{clean_u}' in message body is not backed by stored evidence.")

        # 4. Confirmed product capabilities check
        confirmed_cap_keys = {cap.capability_key for cap in capabilities if cap.confirmed}
        if not referenced_capability_keys:
            flags.append("MISSING_PRODUCT_CAPABILITY: Outreach must reference at least one confirmed IncuBrix capability.")
        for ckey in referenced_capability_keys:
            if ckey not in confirmed_cap_keys:
                flags.append(f"INVENTED_PRODUCT_CLAIM: Capability '{ckey}' is not confirmed in product registry.")

        for forbidden in FORBIDDEN_UNCONFIRMED_CLAIMS:
            if forbidden in lower_text:
                flags.append(f"UNSUPPORTED_CLAIM_OR_IMPERSONATION: Forbidden phrase '{forbidden}' detected.")

        # 5. Evidence citations & freshness
        valid_ev_map = {ev.id: ev for ev in evidence_list}
        if not cited_evidence_ids:
            flags.append("MISSING_SOURCE_REFERENCES: Message cites zero evidence IDs.")
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        for eid in cited_evidence_ids:
            ev = valid_ev_map.get(eid)
            if not ev:
                flags.append(f"UNSUPPORTED_EVIDENCE_ID: Evidence ID '{eid}' not found.")
            else:
                checked = ev.checked_at
                if checked.tzinfo is None:
                    checked = checked.replace(tzinfo=timezone.utc)
                if checked < cutoff:
                    flags.append(f"OUTDATED_EVIDENCE: Cited evidence '{eid}' is older than 30 days.")

        # 6. Sender identity & Opt-out
        sender_first_part = sender_identity.split("(")[0].strip().lower()
        if sender_first_part and sender_first_part not in lower_text:
            flags.append("MISSING_SENDER_IDENTITY: Message does not clearly identify the sender.")

        if not opt_out_text or (
            opt_out_text.lower() not in lower_text
            and "opt out" not in lower_text
            and "stop" not in lower_text
            and "never follow up" not in lower_text
            and "won't message again" not in lower_text
            and "no further outreach" not in lower_text
        ):
            flags.append("MISSING_OPT_OUT: Message does not include a compliant opt-out instruction.")

        # 7. Channel length policy
        if len(body) > max_length:
            flags.append(f"CHANNEL_LENGTH_EXCEEDED: Body length ({len(body)}) exceeds {channel} policy limit ({max_length}).")

        return (len(flags) == 0), flags
