from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from fastapi import HTTPException
from datetime import datetime, timezone, timedelta
from uuid import UUID
import structlog

logger = structlog.get_logger()
import calendar
from app.models.quota import UsageQuota

TIER_LIMITS: dict[str, dict[str, int]] = {
    "free":       {"renders": 0,   "downloads": 0,  "claude": 0},
    "spark":      {"renders": 50,  "downloads": 50, "claude": 0},
    "creator":    {"renders": 10,  "downloads": 10, "claude": 10},
    "artist":     {"renders": 25,  "downloads": 25, "claude": 20},
    "studio_pro": {"renders": 75,  "downloads": 75, "claude": 50},
    "enterprise": {"renders": -1,  "downloads": -1, "claude": -1},
}


async def check_and_increment_renders(user_id: UUID, tier: str, db: AsyncSession) -> None:
    limit = TIER_LIMITS.get(tier, {}).get("renders", 0)
    if limit == -1:
        return
    quota = await _get_or_create_quota(user_id, db)
    if quota.renders_used >= limit:
        raise HTTPException(429, detail={
            "code": "RAIN-E701",
            "message": f"Render quota exhausted ({quota.renders_used}/{limit} this period)"
        })
    quota.renders_used += 1
    await db.commit()


async def check_and_increment_downloads(user_id: UUID, tier: str, db: AsyncSession) -> None:
    if tier == "free":
        raise HTTPException(403, detail={"code": "RAIN-E101", "message": "Free tier cannot download"})
    limit = TIER_LIMITS.get(tier, {}).get("downloads", 0)
    if limit == -1:
        return
    quota = await _get_or_create_quota(user_id, db)
    if quota.downloads_used >= limit:
        raise HTTPException(429, detail={
            "code": "RAIN-E702",
            "message": f"Download quota exhausted ({quota.downloads_used}/{limit} this period)"
        })
    quota.downloads_used += 1
    await db.commit()


async def _get_or_create_quota(user_id: UUID, db: AsyncSession) -> UsageQuota:
    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(user_id)})
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(UsageQuota).where(
            UsageQuota.user_id == user_id,
            UsageQuota.period_start == start
        )
    )
    quota = result.scalar_one_or_none()
    if not quota:
        last_day = calendar.monthrange(now.year, now.month)[1]
        end = start.replace(day=last_day, hour=23, minute=59, second=59)
        quota = UsageQuota(user_id=user_id, period_start=start, period_end=end)
        db.add(quota)
        await db.commit()
        await db.refresh(quota)
    return quota
