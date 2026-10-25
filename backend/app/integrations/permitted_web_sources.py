from __future__ import annotations

import re
import time
import urllib.parse
import urllib.robotparser
from typing import Any

import httpx
from sqlalchemy.orm import Session

from backend.app.database.models import ApiUsage


class PermittedWebCollector:
    """Fetches public business contact & workflow signals from creator-owned websites only when robots.txt allows."""

    USER_AGENT = "IncuBrixGrowthOS-ComplianceBot/1.0"

    @classmethod
    def check_robots_allowed(cls, client: httpx.Client, target_url: str) -> tuple[bool, str]:
        parsed = urllib.parse.urlsplit(target_url)
        if not parsed.scheme or not parsed.netloc:
            return False, "Invalid URL format"
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            resp = client.get(robots_url, timeout=5.0, headers={"User-Agent": cls.USER_AGENT})
            if resp.status_code == 200:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(resp.text.splitlines())
                allowed = rp.can_fetch(cls.USER_AGENT, target_url)
                return allowed, robots_url
            return True, f"{robots_url} (status {resp.status_code}, default permitted)"
        except Exception as exc:
            return False, f"robots.txt check failed: {exc}"

    @classmethod
    def extract_public_business_signals(
        cls,
        db: Session | None,
        target_url: str,
        http_client: httpx.Client | None = None,
    ) -> dict[str, Any]:
        close_client = False
        client = http_client
        if client is None:
            client = httpx.Client(timeout=8.0, follow_redirects=True)
            close_client = True

        try:
            allowed, robots_note = cls.check_robots_allowed(client, target_url)
            if not allowed:
                return {
                    "permitted": False,
                    "restriction_reason": f"Blocked by robots.txt policy at {robots_note}",
                    "emails": [],
                    "social_links": {},
                }

            start = time.perf_counter()
            resp = client.get(target_url, headers={"User-Agent": cls.USER_AGENT})
            latency = (time.perf_counter() - start) * 1000.0
            if db is not None:
                db.add(
                    ApiUsage(
                        provider="permitted_creator_website",
                        endpoint=target_url[:240],
                        operation="fetch_public_page",
                        units_or_tokens=1,
                        status_code=resp.status_code,
                        success=(resp.status_code == 200),
                        latency_ms=round(latency, 2),
                    )
                )
                db.flush()

            if resp.status_code != 200:
                return {
                    "permitted": False,
                    "restriction_reason": f"HTTP {resp.status_code} from {target_url}",
                    "emails": [],
                    "social_links": {},
                }

            html = resp.text[:150000]
            emails = sorted(
                set(
                    e
                    for e in re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", html)
                    if not any(ext in e.lower() for ext in (".png", ".jpg", ".svg", ".webp", "sentry.io", "example.com"))
                )
            )
            linkedin_match = re.search(r"https?://(?:www\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9_-]+", html)
            instagram_match = re.search(r"https?://(?:www\.)?instagram\.com/[a-zA-Z0-9_.-]+", html)
            x_match = re.search(r"https?://(?:www\.)?(?:x|twitter)\.com/[a-zA-Z0-9_]+", html)

            socials = {}
            if linkedin_match:
                socials["linkedin"] = linkedin_match.group(0)
            if instagram_match:
                socials["instagram"] = instagram_match.group(0)
            if x_match:
                socials["x"] = x_match.group(0)

            return {
                "permitted": True,
                "robots_note": robots_note,
                "emails": emails[:3],
                "social_links": socials,
            }
        except Exception as exc:
            return {
                "permitted": False,
                "restriction_reason": f"Request error: {exc}",
                "emails": [],
                "social_links": {},
            }
        finally:
            if close_client and client is not None:
                client.close()
