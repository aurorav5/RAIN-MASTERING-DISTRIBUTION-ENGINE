from typing import Union

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import hashlib
import structlog
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter, dynamic_limit
from app.api.dependencies import get_current_user, CurrentUser
from app.services.storage import upload_to_s3
from app.services.quota import check_and_increment_renders
from app.models.session import Session as MasteringSession
from app.schemas.session import SessionCreateRequest, SessionResponse, FreeSessionResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/sessions", tags=["sessions"])

ACCEPTED_FORMATS = {".wav", ".flac", ".aiff", ".aif", ".mp3", ".m4a"}
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB


@router.post("/", response_model=Union[SessionResponse, FreeSessionResponse], status_code=201)
@limiter.limit(dynamic_limit)
async def create_session(
    request: Request,
    params: SessionCreateRequest = Depends(),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse | FreeSessionResponse:
    ext = ("." + file.filename.rsplit(".", 1)[-1].lower()) if file.filename and "." in file.filename else ""
    if ext not in ACCEPTED_FORMATS:
        raise HTTPException(422, detail={"code": "RAIN-E200", "message": f"Format '{ext}' not accepted"})

    data = await file.read()
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(413, detail={"code": "RAIN-E201", "message": "File exceeds 500 MB limit"})

    file_hash = hashlib.sha256(data).hexdigest()

    # ── Free-tier gate: no S3, no DB persistence, no Celery tasks ──
    # Free tier renders entirely in WASM on the client. Audio never
    # leaves the device. No session is persisted server-side.
    if current_user.tier == "free":
        logger.info(
            "free_tier_local_only",
            user_id=str(current_user.user_id),
            stage="upload",
            tier="free",
            file_hash=file_hash,
            code="RAIN-B001",
            message="Free-tier upload handled locally — no S3, no Celery dispatch",
        )
        return FreeSessionResponse(
            file_hash=file_hash,
            target_platform=params.target_platform,
            genre=params.genre,
            simple_mode=params.simple_mode,
        )

    # ── Paid-tier flow: S3 upload → DB session → Celery analysis ──
    session_id = uuid.uuid4()

    try:
        s3_key_val, _ = await upload_to_s3(
            data, str(current_user.user_id), str(session_id),
            file.filename or "upload.wav"
        )
    except Exception:
        logger.error(
            "s3_upload_failed",
            user_id=str(current_user.user_id),
            session_id=str(session_id),
            stage="upload",
            error_code="RAIN-E203",
        )
        raise HTTPException(503, detail={"code": "RAIN-E203", "message": "Storage write failed"})

    session = MasteringSession(
        id=session_id,
        user_id=current_user.user_id,
        status="analyzing",
        tier_at_creation=current_user.tier,
        input_file_key=s3_key_val,
        input_file_hash=file_hash,
        target_platform=params.target_platform,
        simple_mode=params.simple_mode,
        genre=params.genre,
        wasm_binary_hash=params.wasm_binary_hash or "pending",
    )
    # R6 WASM binary integrity — verify hash if gate is set
    if settings.RAIN_EXPECTED_WASM_HASH and session.wasm_binary_hash not in ("pending", settings.RAIN_EXPECTED_WASM_HASH):
        raise HTTPException(
            status_code=403,
            detail={"code": "RAIN-E304", "message": "WASM binary hash mismatch — render blocked"}
        )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    from app.tasks.analysis import analyze_session
    analyze_session.delay(str(session_id), str(current_user.user_id))

    logger.info(
        "session_created",
        session_id=str(session_id),
        tier=current_user.tier,
        stage="upload",
        user_id=str(current_user.user_id),
    )
    return SessionResponse.model_validate(session)
