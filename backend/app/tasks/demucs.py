"""Demucs stem separation task. Full implementation deferred — requires GPU worker."""
from celery import shared_task
import asyncio
import structlog

logger = structlog.get_logger()


@shared_task(name="app.tasks.demucs.separate_stems", bind=True, max_retries=2)
def separate_stems(self, session_id: str, user_id: str) -> None:
    """
    Run Demucs htdemucs_6s stem separation on uploaded audio.
    Dispatched for paid-tier sessions that need stems (Creator+).
    Suno imports skip this task (stems already separated).
    """
    asyncio.run(_separate_stems_async(session_id, user_id))


async def _separate_stems_async(session_id: str, user_id: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.session import Session as MasteringSession
    from sqlalchemy import select, text
    from uuid import UUID

    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(user_id)})
        result = await db.execute(
            select(MasteringSession).where(
                MasteringSession.id == UUID(session_id),
                MasteringSession.user_id == UUID(user_id),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            logger.error("demucs_session_not_found", session_id=session_id)
            return

        # Stub: full Demucs integration requires GPU worker + htdemucs_6s model
        logger.info(
            "demucs_stub",
            session_id=session_id,
            user_id=user_id,
            stage="demucs",
            note="GPU worker required — stem separation deferred",
        )
