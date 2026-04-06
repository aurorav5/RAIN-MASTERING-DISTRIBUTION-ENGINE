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


# ── Multi-format transcode stubs (RAIN-E703) ──────────────────────────────────
# These return structured errors instead of silent 500s.
# Implementation pending: MP3 320, FLAC, AAC, OGG transcoding via ffmpeg.

_TRANSCODE_FORMATS = {"mp3", "flac", "aac", "ogg"}


@router.get("/{session_id}/download/{fmt}")
async def download_master_format(
    session_id: UUID,
    fmt: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    if fmt not in _TRANSCODE_FORMATS:
        raise HTTPException(422, detail={
            "code": "RAIN-E703",
            "message": f"Unknown format '{fmt}'. Supported: {', '.join(sorted(_TRANSCODE_FORMATS))}",
        })
    raise HTTPException(501, detail={
        "code": "RAIN-E703",
        "message": f"Multi-format export ({fmt.upper()}) is not yet implemented. Download WAV and convert locally.",
        "feature": "multi_format_export",
        "status": "planned",
    })


# ── DDP 2.0 export stub (RAIN-E604) ──────────────────────────────────────────

@router.get("/{session_id}/ddp")
async def download_ddp(
    session_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    raise HTTPException(501, detail={
        "code": "RAIN-E604",
        "message": "DDP 2.0 export is not yet implemented. Use WAV export for CD manufacturing.",
        "feature": "ddp_export",
        "status": "planned",
    })
