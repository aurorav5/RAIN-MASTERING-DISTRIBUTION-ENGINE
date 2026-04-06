from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.models.subscription import Subscription
from uuid import UUID
import structlog

logger = structlog.get_logger()


async def get_current_tier(user_id: UUID, db: AsyncSession) -> str:
    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(user_id)})
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.status == "active")
        .order_by(Subscription.current_period_end.desc())
    )
    sub = result.scalar_one_or_none()
    return sub.tier if sub else "free"
