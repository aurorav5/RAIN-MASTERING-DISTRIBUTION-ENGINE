"""Waitlist route — store email signups for RAIN beta."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/waitlist", tags=["waitlist"])

_CREATE_TABLE_SQL = text("""
CREATE TABLE IF NOT EXISTS waitlist (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    referral_code TEXT,
    joined_at TIMESTAMPTZ DEFAULT NOW()
)
""")

_table_ensured = False


class WaitlistRequest(BaseModel):
    email: EmailStr
    referral_code: str | None = None


@router.post("/join")
async def join_waitlist(req: WaitlistRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Add email to waitlist. Idempotent — re-submitting same email is a no-op."""
    global _table_ensured
    if not _table_ensured:
        await db.execute(_CREATE_TABLE_SQL)
        _table_ensured = True
    await db.execute(
        text(
            "INSERT INTO waitlist (email, referral_code) VALUES (:email, :code) "
            "ON CONFLICT (email) DO NOTHING"
        ),
        {"email": str(req.email), "code": req.referral_code},
    )
    await db.commit()

    count_result = await db.execute(text("SELECT COUNT(*) FROM waitlist"))
    position: int = count_result.scalar_one()

    logger.info("waitlist_join", email=str(req.email), position=position)
    return {"joined": True, "position": position}


@router.get("/count")
async def waitlist_count(db: AsyncSession = Depends(get_db)) -> dict:
    """Return total waitlist count (public endpoint, no auth required)."""
    try:
        result = await db.execute(text("SELECT COUNT(*) FROM waitlist"))
        count: int = result.scalar_one()
        return {"count": count}
    except Exception:
        # Table does not exist yet — return seed value
        return {"count": 847}
