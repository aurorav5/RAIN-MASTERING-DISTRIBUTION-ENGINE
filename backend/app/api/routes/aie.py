"""AIE (Artist Identity Engine) API routes."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from uuid import UUID
from app.core.database import get_db
from app.api.dependencies import get_current_user, CurrentUser, require_tier
from app.models.aie import AIEProfile, validate_voice_vector
import structlog
import json
import hashlib
import base64

logger = structlog.get_logger()
router = APIRouter(prefix="/aie", tags=["aie"])


@router.get("/profile")
async def get_aie_profile(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return current user's AIE profile (session_count, cold_start status)."""
    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(current_user.user_id)})
    result = await db.execute(
        select(AIEProfile).where(AIEProfile.user_id == current_user.user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return {
            "session_count": 0,
            "cold_start": True,
            "cold_start_sessions_remaining": 5,
            "genre_distribution": {},
        }
    return {
        "session_count": profile.session_count,
        "cold_start": profile.session_count < 5,
        "cold_start_sessions_remaining": max(0, 5 - profile.session_count),
        "genre_distribution": profile.genre_distribution or {},
    }


@router.get("/profile/export")
async def export_aie_profile(
    current_user: CurrentUser = Depends(require_tier("artist", "studio_pro", "enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Export AIE profile as a signed portable file.
    Signed with SHA-256 HMAC using RAIN_WATERMARK_KEY.
    Tier gate: artist+
    """
    from app.core.config import settings
    import hmac

    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(current_user.user_id)})
    result = await db.execute(
        select(AIEProfile).where(AIEProfile.user_id == current_user.user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, detail={"code": "RAIN-E400", "message": "No AIE profile found"})

    payload = {
        "user_id_hash": hashlib.sha256(str(current_user.user_id).encode()).hexdigest(),
        "voice_vector": profile.voice_vector,
        "session_count": profile.session_count,
        "genre_distribution": profile.genre_distribution,
        "rain_version": settings.RAIN_VERSION,
        "export_format": "rain-aie-v1",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    # HMAC-SHA256 signature with watermark key
    wm_key_path = getattr(settings, "RAIN_WATERMARK_KEY_PATH", None)
    if wm_key_path:
        try:
            from pathlib import Path
            wm_key = Path(wm_key_path).read_bytes()
        except FileNotFoundError:
            wm_key = b"rain-dev-watermark-key"
    else:
        wm_key = b"rain-dev-watermark-key"

    sig = hmac.new(wm_key, canonical.encode(), hashlib.sha256).digest()
    signature_b64 = base64.b64encode(sig).decode()

    return {
        "payload": payload,
        "signature": signature_b64,
        "signature_algorithm": "HMAC-SHA256",
    }


@router.post("/reference-match")
async def reference_match(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_tier("artist", "studio_pro", "enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Compute reference artist embedding from uploaded audio.
    Returns interpolated target vector between user's voice and reference.
    Tier gate: artist+
    """
    from app.services.audio_analysis import extract_mel_spectrogram
    from app.models.aie import AIEProfile
    import numpy as np

    data = await file.read()
    mel, duration, sr = extract_mel_spectrogram(data)

    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(current_user.user_id)})
    result = await db.execute(
        select(AIEProfile).where(AIEProfile.user_id == current_user.user_id)
    )
    profile = result.scalar_one_or_none()

    # Compute reference embedding using same projection as training
    from app.tasks.aie import _compute_session_embedding
    ref_embedding = _compute_session_embedding(mel, {})
    ref_norm = np.linalg.norm(ref_embedding)
    if ref_norm > 1e-8:
        ref_embedding = ref_embedding / ref_norm

    if profile and profile.voice_vector and profile.session_count >= 5:
        user_vec = np.array(profile.voice_vector, dtype=np.float64)
        # Interpolate 50% toward reference
        interpolated = 0.5 * user_vec + 0.5 * ref_embedding
        interp_norm = np.linalg.norm(interpolated)
        if interp_norm > 1e-8:
            interpolated = interpolated / interp_norm
        target_vector = interpolated.tolist()
    else:
        target_vector = ref_embedding.tolist()

    return {
        "reference_embedding_norm": float(ref_norm),
        "target_vector": target_vector,
        "interpolation": "50% user + 50% reference" if profile and profile.session_count >= 5 else "reference only (cold start)",
    }
