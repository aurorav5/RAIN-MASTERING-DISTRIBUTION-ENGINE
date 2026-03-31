"""Distribution delivery task — async LabelGrid submission + status polling."""
from celery import shared_task
import asyncio
import structlog

logger = structlog.get_logger()


@shared_task(name="app.tasks.distribution.submit_distribution", bind=True, max_retries=3)
def submit_distribution(self, release_id: str, user_id: str) -> None:
    """
    Background task for distribution submission.
    Called after release creation if async delivery is needed.
    """
    asyncio.run(_submit_distribution_async(release_id, user_id))


async def _submit_distribution_async(release_id: str, user_id: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.release import Release
    from app.services import labelgrid
    from sqlalchemy import select, text
    from uuid import UUID

    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(user_id)})
        result = await db.execute(
            select(Release).where(
                Release.id == UUID(release_id),
                Release.user_id == UUID(user_id),
            )
        )
        release = result.scalar_one_or_none()
        if not release:
            logger.error("distribution_release_not_found", release_id=release_id)
            return

        if release.labelgrid_release_id:
            # Poll status
            try:
                status = await labelgrid.get_release_status(release.labelgrid_release_id)
                release.labelgrid_status = status.get("status", release.labelgrid_status)
                await db.commit()
                logger.info(
                    "distribution_status_updated",
                    release_id=release_id,
                    status=release.labelgrid_status,
                    stage="distribution",
                    user_id=user_id,
                )
            except Exception as e:
                logger.warning(
                    "distribution_poll_failed",
                    release_id=release_id,
                    error=str(e),
                    error_code="RAIN-E600",
                    stage="distribution",
                )
