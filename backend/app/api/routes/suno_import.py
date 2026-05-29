"""Suno Import Mode — dedicated upload for Suno AI-generated stems."""
from __future__ import annotations
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import hashlib
import json
import uuid
import structlog

from app.core.database import get_db
from app.api.dependencies import get_current_user, CurrentUser
from app.models.session import Session as MasteringSession
from app.schemas.session import SessionResponse
from app.services.storage import upload_to_s3

logger = structlog.get_logger()
router = APIRouter(prefix="/suno-import", tags=["suno"])

# Suno v5 12-stem filename labels → OSMEF roles
SUNO_STEM_MAP: dict[str, str] = {
    "vocals_bg": "vocals",
    "vocals": "vocals",
    "drums": "drums",
    "bass": "bass",
    "guitar": "instruments",
    "piano": "instruments",
    "synth": "instruments",
    "strings": "instruments",
    "brass": "instruments",
    "fx": "fx",
    "accompaniment": "accompaniment",
    "other": "other",
}


def _detect_stem_role(filename: str) -> str:
    """Auto-detect OSMEF stem role from Suno export filename."""
    name = filename.lower()
    for label, role in SUNO_STEM_MAP.items():
        if label in name:
            return role
    return "other"


@router.post("/", status_code=201)
async def suno_import(
    stems: List[UploadFile] = File(...),
    metadata: str = Form(...),
    target_platform: str = Form("spotify"),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Suno Import Mode: upload up to 12 Suno-exported stems.
    - Auto-detects stem roles from filenames
    - Sets ai_generated=True, ai_source='suno' automatically
    - No BS-RoFormer needed — stems already separated
    - Free tier: no S3 storage, session held in memory
    """
    try:
        meta: dict = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(422, detail={"code": "RAIN-E200", "message": "Invalid metadata JSON"})

    session_id = uuid.uuid4()
    uploaded_stems: list[dict] = []
    mix_data: bytes | None = None

    for stem_file in stems:
        filename = stem_file.filename or "unknown.wav"
        data = await stem_file.read()
        file_hash = hashlib.sha256(data).hexdigest()
        role = _detect_stem_role(filename)

        if current_user.tier == "free":
            s3_key: str | None = None
        else:
            try:
                s3_key, _ = await upload_to_s3(
                    data, str(current_user.user_id), str(session_id), filename
                )
            except Exception:
                raise HTTPException(503, detail={"code": "RAIN-E203", "message": "Storage write failed"})

        uploaded_stems.append({
            "role": role,
            "file_key": s3_key,
            "file_hash": file_hash,
            "filename": filename,
        })
        # Treat "accompaniment" or last uploaded as the reference mix
        if role in ("mix", "accompaniment") or mix_data is None:
            mix_data = data

    # Derive input_file_key from mix stem (or None for free tier)
    mix_stem = next(
        (s for s in uploaded_stems if s["role"] in ("mix", "accompaniment")),
        uploaded_stems[0] if uploaded_stems else None,
    )
    input_file_key = mix_stem["file_key"] if mix_stem else None
    input_file_hash = mix_stem["file_hash"] if mix_stem else ""

    session = MasteringSession(
        id=session_id,
        user_id=current_user.user_id,
        status="analyzing",
        tier_at_creation=current_user.tier,
        input_file_key=input_file_key,
        input_file_hash=input_file_hash,
        target_platform=target_platform,
        simple_mode=False,
        genre=meta.get("genre", "default"),
        wasm_binary_hash="pending",
        ai_generated=True,
        ai_source="suno",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    logger.info(
        "suno_import_created",
        session_id=str(session_id),
        stem_count=len(stems),
        tier=current_user.tier,
        platform=target_platform,
        stage="upload",
        user_id=str(current_user.user_id),
    )

    # Dispatch analysis — Suno stems skip BS-RoFormer (already separated)
    if input_file_key:
        from app.tasks.analysis import analyze_session
        analyze_session.delay(str(session_id), str(current_user.user_id))

    return {
        "session_id": str(session_id),
        "status": session.status,
        "stems_uploaded": len(uploaded_stems),
        "stem_roles": [s["role"] for s in uploaded_stems],
        "ai_generated": True,
        "ai_source": "suno",
        "tier": current_user.tier,
    }
