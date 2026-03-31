"""Distribution pipeline routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from uuid import UUID
from datetime import datetime, timezone
from app.core.database import get_db
from app.api.dependencies import get_current_user, CurrentUser, require_tier
from app.models.session import Session as MasteringSession
from app.models.cert import RainCert
from app.models.release import Release
from app.schemas.release import ReleaseCreateRequest, ReleaseResponse
from app.services.identifiers import generate_isrc, generate_upc
from app.services.ddex import generate_ddex_ern43
from app.services import labelgrid
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/releases", tags=["distribution"])


@router.post("/", response_model=ReleaseResponse, status_code=201)
async def create_release(
    req: ReleaseCreateRequest,
    current_user: CurrentUser = Depends(require_tier("artist", "studio_pro", "enterprise")),
    db: AsyncSession = Depends(get_db),
) -> ReleaseResponse:
    """
    Create a release from a completed session.
    Generates ISRC/UPC, builds DDEX ERN 4.3 XML, submits to LabelGrid.
    Requires: Artist tier+, completed session, RAIN-CERT.
    """
    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(current_user.user_id)})

    # 1. Verify session is complete and owned by user
    sess_result = await db.execute(
        select(MasteringSession).where(
            MasteringSession.id == req.session_id,
            MasteringSession.user_id == current_user.user_id,
        )
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, detail={"code": "RAIN-E600", "message": "Session not found"})
    if session.status != "complete":
        raise HTTPException(400, detail={"code": "RAIN-E600", "message": "Session not complete"})

    # 2. Verify RAIN-CERT exists
    cert_result = await db.execute(
        select(RainCert).where(RainCert.session_id == req.session_id)
    )
    cert = cert_result.scalar_one_or_none()
    if not cert:
        raise HTTPException(400, detail={"code": "RAIN-E600", "message": "RAIN-CERT not issued — wait for certification to complete"})

    # 3. Generate ISRC + UPC
    isrc = generate_isrc()
    upc = generate_upc()

    # 4. Generate DDEX ERN 4.3 XML
    audio_file_path = session.output_file_key or ""
    duration_seconds = int((session.input_duration_ms or 0) / 1000)
    ddex_xml = generate_ddex_ern43(
        release_id=str(req.session_id),
        title=req.title,
        artist_name=req.artist_name,
        isrc=isrc,
        upc=upc,
        audio_file_path=audio_file_path,
        audio_sha256=session.output_file_hash or "",
        duration_seconds=duration_seconds,
        genre=req.genre,
        release_date=req.release_date,
        territory=req.territory,
        ai_generated=req.ai_generated,
        ai_source=req.ai_source,
        explicit=req.explicit,
        label_name=req.label_name,
    )

    # 5. Submit to LabelGrid
    release_data = {
        "title": req.title,
        "artist": req.artist_name,
        "isrc": isrc,
        "upc": upc,
        "genre": req.genre,
        "release_date": req.release_date,
        "territory": req.territory,
        "label": req.label_name,
        "rain_cert_id": str(cert.id),
        "rain_cert_signature": cert.signature,
    }
    labelgrid_resp: dict = {}
    try:
        labelgrid_resp = await labelgrid.submit_release(release_data, ddex_xml, audio_file_path)
    except RuntimeError as e:
        logger.error("labelgrid_submit_failed", error=str(e), error_code="RAIN-E600", user_id=str(current_user.user_id))
        # Non-blocking: create release record even if LabelGrid fails
        labelgrid_resp = {"status": "error", "error": str(e)}

    # 6. Create Release record
    release = Release(
        user_id=current_user.user_id,
        session_id=req.session_id,
        title=req.title,
        artist_name=req.artist_name,
        isrc=isrc,
        upc=upc,
        genre=req.genre,
        release_date=req.release_date,
        territory=req.territory,
        label_name=req.label_name,
        explicit=req.explicit,
        ai_generated=req.ai_generated,
        ai_source=req.ai_source,
        ddex_xml=ddex_xml,
        labelgrid_release_id=labelgrid_resp.get("id") or labelgrid_resp.get("release_id"),
        labelgrid_status=labelgrid_resp.get("status", "submitted"),
        status="submitted" if labelgrid_resp.get("status") not in ("error", "skipped") else "pending",
        metadata_json=release_data,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(release)
    await db.commit()
    await db.refresh(release)

    logger.info(
        "release_created",
        release_id=str(release.id),
        isrc=isrc,
        upc=upc,
        labelgrid_status=release.labelgrid_status,
        stage="distribution",
        user_id=str(current_user.user_id),
    )
    return ReleaseResponse.model_validate(release)


@router.get("/{release_id}/status")
async def get_release_status(
    release_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Poll LabelGrid for current distribution status."""
    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(current_user.user_id)})

    result = await db.execute(
        select(Release).where(
            Release.id == release_id,
            Release.user_id == current_user.user_id,
        )
    )
    release = result.scalar_one_or_none()
    if not release:
        raise HTTPException(404, detail={"code": "RAIN-E600", "message": "Release not found"})

    if release.labelgrid_release_id:
        try:
            status_data = await labelgrid.get_release_status(release.labelgrid_release_id)
            # Update cached status
            release.labelgrid_status = status_data.get("status", release.labelgrid_status)
            await db.commit()
            return {"release_id": str(release_id), "status": release.labelgrid_status, "labelgrid": status_data}
        except Exception as e:
            logger.warning("labelgrid_status_failed", error=str(e), error_code="RAIN-E600")

    return {"release_id": str(release_id), "status": release.labelgrid_status or "unknown"}
