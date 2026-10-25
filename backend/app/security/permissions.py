from __future__ import annotations

from fastapi import Depends, HTTPException, status

from backend.app.database.models import SeedTestAccount, User
from backend.app.security.auth import get_current_user
from backend.app.utils.errors import IntegrityViolationError


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required.",
        )
    return user


def enforce_seed_test_allowlist(recipient_address: str, channel: str, allowlisted_accounts: list[SeedTestAccount]) -> SeedTestAccount:
    normalized_recipient = recipient_address.strip().lower()
    normalized_channel = channel.strip().lower()

    for acc in allowlisted_accounts:
        if (
            acc.is_allowlisted
            and acc.ownership_verified
            and acc.channel.strip().lower() == normalized_channel
            and acc.handle_or_address.strip().lower() == normalized_recipient
        ):
            return acc

    raise IntegrityViolationError(
        message=(
            f"Outbound seed test blocked: recipient '{recipient_address}' on channel '{channel}' "
            "is NOT in the participant-owned allowlist. Real creator outreach is strictly forbidden during assessment."
        ),
        details={"recipient": recipient_address, "channel": channel},
    )
