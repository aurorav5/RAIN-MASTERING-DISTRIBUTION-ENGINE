"""Distributed rate limiting via SlowAPI + Valkey. Per-tier limits from core/tiers.py."""
from __future__ import annotations
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.tiers import rate_limit_for_tier


def _identify_user(request: Request) -> str:
    """Rate-limit key: user_id if authenticated, else remote IP."""
    user = getattr(request.state, "user", None)
    if user is not None and getattr(user, "user_id", None):
        return f"user:{user.user_id}"
    return f"ip:{get_remote_address(request)}"


def _dynamic_limit(request: Request) -> str:
    """Return per-tier limit string (e.g. '500/hour') for the current request's user."""
    user = getattr(request.state, "user", None)
    tier = getattr(user, "tier", "free") if user else "free"
    return rate_limit_for_tier(tier)


limiter = Limiter(
    key_func=_identify_user,
    storage_uri=settings.REDIS_URL,
    default_limits=[],  # no global default — apply via decorator per route
)


# Decorator usage:
#   @router.post("/mastering/start")
#   @limiter.limit(_dynamic_limit)
#   async def start_mastering(request: Request, ...): ...
dynamic_limit = _dynamic_limit
