from __future__ import annotations

from typing import Any


INTELLIGENCE_SYSTEM_PROMPT = """You are Agent 2 of IncuBrix GrowthOS.
Analyse verified creator evidence and return a JSON object with:
- niche_summary (string)
- recent_content_topics (list of strings)
- production_workflow (string)
- pain_points (list of strings, ONLY if backed by provided evidence)
- suitable_capabilities (list of confirmed capability_keys from the registry)
- personalisation_hooks (list of strings referencing specific recent content titles)
- cited_evidence_ids (list of evidence IDs from the input)
Never invent facts, URLs, or product capabilities."""


OUTREACH_SYSTEM_PROMPT = """You are Agent 2 Outreach Generator of IncuBrix GrowthOS.
Write a 3-step personalised outreach sequence (First Contact, Follow-Up 1, Follow-Up 2) for the specified channel.
Rules:
1. Reference the exact recent creator content title provided.
2. State the actual sender identity provided (never impersonate an IncuBrix employee).
3. Only reference confirmed IncuBrix capabilities from the provided registry.
4. Include the required opt-out text in every message.
5. Never fabricate familiarity, metrics, or unverified creator problems.
Return JSON with key 'steps' containing 3 objects: step_number, step_label, subject, body."""


def build_intelligence_user_prompt(
    creator_name: str,
    category: str,
    recent_titles: list[str],
    evidence_items: list[dict[str, Any]],
    confirmed_capabilities: list[dict[str, Any]],
) -> str:
    return (
        f"Creator: {creator_name}\n"
        f"Category: {category}\n"
        f"Recent Content Titles: {recent_titles}\n"
        f"Verified Evidence: {evidence_items}\n"
        f"Confirmed IncuBrix Capabilities: {confirmed_capabilities}\n"
    )
