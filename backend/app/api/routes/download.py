from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from uuid import UUID
from app.core.database import get_db
from app.api.dependencies import get_current_user, CurrentUser
from app.models.session import Session as MasteringSession
from app.services.storage import generate_presigned_url
from app.services.quota import check_and_increment_downloads

router = APIRouter(prefix="/sessions", tags=["download"])


@router.get("/{session_id}/download")
async def download_master(
    session_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(current_user.user_id)})

    result = await db.execute(
        select(MasteringSession).where(
            MasteringSession.id == session_id,
            MasteringSession.user_id == current_user.user_id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(404, detail={"code": "RAIN-E200", "message": "Session not found"})
    if session.status != "complete":
        raise HTTPException(400, detail={"code": "RAIN-E200", "message": "Session not complete"})
    if not session.output_file_key:
        raise HTTPException(400, detail={"code": "RAIN-E200", "message": "No output file"})

    # Quota check enforces free tier block (raises 402 for free tier)
    await check_and_increment_downloads(current_user.user_id, current_user.tier, db)

    url = await generate_presigned_url(session.output_file_key, expires_seconds=300)
    return RedirectResponse(url=url, status_code=302)
