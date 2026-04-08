"""Distribution pipeline routes."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
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
from app.services.identifiers import allocate_isrc, allocate_upc, generate_isrc
from app.services.ddex import generate_ddex_ern43, AIDisclosure
from app.services import labelgrid
from app.api.routes.master import _sessions as mastering_sessions
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

    # 3. Allocate sequential ISRC + UPC from DB counters (ISO 3901 / GS1 compliance)
    #    If the caller supplied a pre-assigned ISRC, use it; otherwise auto-generate.
    if req.isrc:
        from app.services.identifiers import validate_isrc
        if not validate_isrc(req.isrc):
            raise HTTPException(400, detail={"code": "RAIN-E710", "message": "Invalid ISRC format"})
        isrc = req.isrc
    else:
        isrc = await allocate_isrc(db)
    upc = await allocate_upc(db)

    # 4. Generate DDEX ERN 4.3 XML
    audio_file_path = session.output_file_key or ""
    duration_seconds = int((session.input_duration_ms or 0) / 1000)
    # Sept 2025 DDEX AI Disclosure — derived from session state (RainNet usage,
    # neural restoration, etc.). If the caller flagged the input as AI-generated
    # via req.ai_generated, we also mark vocals+instrumentation+composition as AI.
    ai_disclosure = AIDisclosure.from_session(session)
    if req.ai_generated:
        ai_disclosure.vocals_ai = True
        ai_disclosure.instrumentation_ai = True
        ai_disclosure.composition_ai = True
        if req.ai_source:
            ai_disclosure.vocals_tool = req.ai_source
            ai_disclosure.instrumentation_tool = req.ai_source
            ai_disclosure.composition_tool = req.ai_source
        # Recompute overall involvement now that additional flags are set
        flags = [
            ai_disclosure.vocals_ai,
            ai_disclosure.instrumentation_ai,
            ai_disclosure.composition_ai,
            ai_disclosure.post_production_ai,
            ai_disclosure.mixing_mastering_ai,
        ]
        count = sum(1 for f in flags if f)
        if count == 0:
            ai_disclosure.overall_ai_involvement = "none"
        elif count <= 2:
            ai_disclosure.overall_ai_involvement = "partial"
        elif count == 3:
            ai_disclosure.overall_ai_involvement = "substantial"
        else:
            ai_disclosure.overall_ai_involvement = "full"
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
        ai_disclosure=ai_disclosure if ai_disclosure.overall_ai_involvement != "none" else None,
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


@router.get("/{release_id}/ddex")
async def get_ddex_xml(
    release_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Generate DDEX ERN 4.3.2 XML for a release.

    If the release exists in the database, its stored DDEX XML is returned.
    Otherwise, if release_id matches a mastering session, a mock DDEX XML
    is generated from the session's analysis and metadata.
    """
    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(current_user.user_id)})

    # Try DB first
    try:
        release_uuid = UUID(release_id)
        result = await db.execute(
            select(Release).where(
                Release.id == release_uuid,
                Release.user_id == current_user.user_id,
            )
        )
        release = result.scalar_one_or_none()
        if release and release.ddex_xml:
            return Response(
                content=release.ddex_xml,
                media_type="application/xml",
                headers={"Content-Disposition": f'attachment; filename="ddex_{release_id}.xml"'},
            )
    except (ValueError, AttributeError):
        # release_id is not a valid UUID — fall through to session lookup
        pass

    # Fall back to in-memory mastering session for mock generation
    session = mastering_sessions.get(release_id)
    if not session:
        raise HTTPException(404, detail={"code": "RAIN-E600", "message": "Release or session not found"})

    analysis = session.get("analysis")
    metadata = session.get("metadata", {})
    master_result = session.get("result")

    title = metadata.get("title") or session.get("filename", "Untitled")
    artist_name = metadata.get("artist") or "Unknown Artist"
    genre = metadata.get("genre") or "Other"
    duration_seconds = int(getattr(analysis, "duration", 0)) if analysis else 0

    # Generate a session-derived ISRC for the mock
    isrc = generate_isrc()

    ai_disclosure = AIDisclosure(
        mixing_mastering_ai=True,
        mixing_mastering_tool="RAIN",
        overall_ai_involvement="partial",
    )

    ddex_xml = generate_ddex_ern43(
        release_id=release_id,
        title=title,
        artist_name=artist_name,
        isrc=isrc,
        upc="0000000000000",
        audio_file_path=session.get("input_path", ""),
        audio_sha256="",
        duration_seconds=duration_seconds,
        genre=genre,
        release_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        territory="Worldwide",
        ai_disclosure=ai_disclosure,
        label_name=metadata.get("label", "ARCOVEL RAIN Distribution"),
    )

    return Response(
        content=ddex_xml,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="ddex_{release_id}.xml"'},
    )
