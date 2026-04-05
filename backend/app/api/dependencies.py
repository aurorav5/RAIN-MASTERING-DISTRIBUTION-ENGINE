from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import jwt
import structlog

from app.core.security import decode_token
from app.core.database import get_db
from app.core.tiers import Tier, TIER_RANK, tier_gte  # re-exported for backward compat

logger = structlog.get_logger()
bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser:
    def __init__(self, user_id: UUID, tier: str, is_admin: bool = False) -> None:
        self.user_id = user_id
        self.tier = tier
        self.is_admin = is_admin


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Decode JWT, return CurrentUser. Stores on request.state for rate-limit key."""
    if credentials is None:
        raise HTTPException(401, detail={"code": "RAIN-E100", "message": "Missing auth token"})
    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, detail={"code": "RAIN-E100", "message": "Token expired"})
    except jwt.PyJWTError:
        raise HTTPException(401, detail={"code": "RAIN-E100", "message": "Invalid token"})

    user_id = UUID(payload["sub"])
    tier = payload.get("tier", "free")
    # Validate tier against canonical enum — unknown tier falls back to free
    try:
        Tier(tier)
    except ValueError:
        logger.warning("unknown_tier_in_token", user_id=str(user_id), tier=tier)
        tier = "free"

    user = CurrentUser(user_id=user_id, tier=tier, is_admin=bool(payload.get("admin")))
    request.state.user = user
    return user


def require_tier(*allowed_tiers: str):
    """Factory for tier-gated endpoints. Accepts str or Tier enum values."""
    allowed = {t.value if isinstance(t, Tier) else t for t in allowed_tiers}

    async def check_tier(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.tier not in allowed and not current_user.is_admin:
            raise HTTPException(403, detail={
                "code": "RAIN-E101",
                "message": f"This feature requires one of: {', '.join(sorted(allowed))}"
            })
        return current_user
    return check_tier


def require_min_tier(minimum: str):
    """Gate endpoint on minimum tier rank (tier_gte semantics)."""
    async def check_min(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not tier_gte(current_user.tier, minimum) and not current_user.is_admin:
            raise HTTPException(403, detail={
                "code": "RAIN-E101",
                "message": f"This feature requires tier >= {minimum}",
            })
        return current_user
    return check_min
