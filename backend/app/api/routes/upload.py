from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import hashlib
import structlog
from app.core.database import get_db
from app.core.rate_limit import limiter, dynamic_limit
from app.api.dependencies import get_current_user, CurrentUser
from app.services.storage import upload_to_s3
from app.services.quota import check_and_increment_renders
from app.models.session import Session as MasteringSession
from app.schemas.session import SessionCreateRequest, SessionResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/sessions", tags=["sessions"])

ACCEPTED_FORMATS = {".wav", ".flac", ".aiff", ".aif", ".mp3", ".m4a"}
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB


@router.post("/", response_model=SessionResponse, status_code=201)
@limiter.limit(dynamic_limit)
async def create_session(
    request: Request,
    params: SessionCreateRequest = Depends(),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    ext = ("." + file.filename.rsplit(".", 1)[-1].lower()) if file.filename and "." in file.filename else ""
    if ext not in ACCEPTED_FORMATS:
        raise HTTPException(422, detail={"code": "RAIN-E200", "message": f"Format '{ext}' not accepted"})

    data = await file.read()
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(413, detail={"code": "RAIN-E201", "message": "File exceeds 500 MB limit"})

    file_hash = hashlib.sha256(data).hexdigest()
    session_id = uuid.uuid4()

    if current_user.tier == "free":
        s3_key_val = None
    else:
        try:
            s3_key_val, _ = await upload_to_s3(
                data, str(current_user.user_id), str(session_id),
                file.filename or "upload.wav"
            )
        except Exception:
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
        wasm_binary_hash="pending",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    from app.tasks.analysis import analyze_session
    analyze_session.delay(str(session_id), str(current_user.user_id))

    logger.info("session_created", session_id=str(session_id), tier=current_user.tier,
                stage="upload", user_id=str(current_user.user_id))
    return SessionResponse.model_validate(session)
