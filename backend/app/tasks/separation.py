"""BS-RoFormer cascaded 12-stem separation task.

Implements the RAIN blueprint's 4-pass separation cascade:

    Pass 1  BS-RoFormer SW                 -> vocals/drums/bass/guitar/piano/other
    Pass 2  MVSep Karaoke BS-RoFormer      -> lead/backing vocals (from pass-1 vocals)
    Pass 3  LarsNet / DrumSep              -> kick/snare/hats/percussion (from pass-1 drums)
    Pass 4  anvuew dereverb MelBand RoFormer -> room; residual -> fx_other (from pass-1 other)

Final 12-stem deliverable:
    lead_vocals, backing_vocals, kick, snare, hats, percussion,
    bass, guitar, piano, room, fx_other, other_residual

Idempotency: the task checks `session.status` and skips if already separated.
Deterministic S3 keys allow safe re-runs (overwrites are benign).

Error codes:
    RAIN-E620  model load failure
    RAIN-E621  inference failure
    RAIN-E622  S3 write failure
    RAIN-E623  stem row insert failure
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import time
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
import structlog
from celery import shared_task

logger = structlog.get_logger()


# Canonical ordered list of the 12 stems produced by the full cascade.
FINAL_STEM_NAMES: tuple[str, ...] = (
    "lead_vocals",
    "backing_vocals",
    "kick",
    "snare",
    "hats",
    "percussion",
    "bass",
    "guitar",
    "piano",
    "room",
    "fx_other",
    "other_residual",
)

# Sessions past this status are already separated; skip.
_SEPARATION_COMPLETE_STATUSES = {"separated", "rendering", "rendered", "completed", "failed"}

_TARGET_SR = 44100


class _SeparationTaskBase:
    """Shared state for the Celery separation task — models load once per worker."""

    _pass1_model: Optional[object] = None
    _pass2_model: Optional[object] = None
    _pass3_model: Optional[object] = None
    _pass4_model: Optional[object] = None


@shared_task(
    name="app.tasks.separation.separate_bsroformer",
    bind=True,
    max_retries=2,
)
def separate_bsroformer(self, session_id: str, user_id: str) -> None:
    """Entry point: run the 4-pass BS-RoFormer cascade on a session's input audio."""
    asyncio.run(_separate_async(self, session_id, user_id))


async def _separate_async(task, session_id: str, user_id: str) -> None:
    from uuid import UUID

    from sqlalchemy import select, update

    from app.core.config import settings
    from app.core.database import AsyncSessionLocal
    from app.models.session import Session as MasteringSession
    from app.models.stem import Stem
    from app.services.storage import get_s3_client

    t_start = time.monotonic()

    async with AsyncSessionLocal() as db:
        # RLS: set per-request user id before any user-scoped query.
        await db.execute(f"SELECT set_app_user_id('{user_id}'::uuid)")

        result = await db.execute(
            select(MasteringSession).where(
                MasteringSession.id == UUID(session_id),
                MasteringSession.user_id == UUID(user_id),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            logger.error(
                "separation_session_not_found",
                session_id=session_id,
                user_id=user_id,
                stage="separation",
                error_code="RAIN-E301",
            )
            return

        # Idempotency gate: skip if a previous run already separated this session.
        if session.status in _SEPARATION_COMPLETE_STATUSES:
            logger.info(
                "separation_skip_idempotent",
                session_id=session_id,
                user_id=user_id,
                stage="separation",
                status=session.status,
            )
            return

        if not session.input_file_key:
            logger.warning(
                "separation_no_input_file_key",
                session_id=session_id,
                user_id=user_id,
                stage="separation",
                note="free tier / input not persisted — separation skipped",
            )
            return

        # --- Feature gate: SEPARATION_ENABLED + checkpoint must exist on disk ---
        model_path = settings.BSROFORMER_MODEL_PATH
        model_available = (
            settings.SEPARATION_ENABLED and bool(model_path) and Path(model_path).exists()
        )
        if not model_available:
            logger.info(
                "separation_stub",
                session_id=session_id,
                user_id=user_id,
                stage="separation",
                pass_name="all",
                separation_enabled=settings.SEPARATION_ENABLED,
                model_path=model_path,
                model_exists=bool(model_path) and Path(model_path).exists(),
                note=(
                    "SEPARATION_ENABLED=False or BS-RoFormer checkpoint missing — "
                    "no stems produced (No Fake Data rule)"
                ),
            )
            return

        # --- Download source audio from S3 ---
        try:
            s3 = get_s3_client()
            obj = s3.get_object(Bucket=settings.S3_BUCKET, Key=session.input_file_key)
            audio_bytes: bytes = obj["Body"].read()
        except Exception as exc:
            logger.error(
                "separation_s3_read_failed",
                session_id=session_id,
                user_id=user_id,
                stage="separation",
                error=str(exc),
                error_code="RAIN-E622",
            )
            return

        try:
            audio, sr = await _read_audio_stereo_44k(audio_bytes)
        except Exception as exc:
            logger.error(
                "separation_audio_decode_failed",
                session_id=session_id,
                user_id=user_id,
                stage="separation",
                error=str(exc),
                error_code="RAIN-E621",
            )
            return

        # --- Load models (once per worker) ---
        try:
            _ensure_models_loaded(settings.BSROFORMER_MODEL_PATH, settings.BSROFORMER_DEVICE)
        except NotImplementedError as exc:
            # Expected until checkpoints are provisioned — stubbed per "No Fake Data".
            logger.info(
                "separation_stub",
                session_id=session_id,
                user_id=user_id,
                stage="separation",
                pass_name="model_load",
                note=str(exc),
            )
            return
        except Exception as exc:
            logger.error(
                "separation_model_load_failed",
                session_id=session_id,
                user_id=user_id,
                stage="separation",
                error=str(exc),
                error_code="RAIN-E620",
            )
            return

        # --- Run the 4-pass cascade ---
        try:
            final_stems = await _run_cascade(audio, sr, session_id=session_id, user_id=user_id)
        except NotImplementedError as exc:
            logger.info(
                "separation_stub",
                session_id=session_id,
                user_id=user_id,
                stage="separation",
                pass_name="inference",
                note=str(exc),
            )
            return
        except Exception as exc:
            logger.error(
                "separation_inference_failed",
                session_id=session_id,
                user_id=user_id,
                stage="separation",
                error=str(exc),
                error_code="RAIN-E621",
            )
            return

        # --- Write each stem to S3 + upsert into stems table ---
        duration_ms = session.input_duration_ms
        written = 0
        for stem_name, stem_audio in final_stems.items():
            # Deterministic S3 key under the canonical prefix:
            #   users/{user_id}/{session_id}/stems/{stem_name}.wav
            stem_key = f"users/{user_id}/{session_id}/stems/{stem_name}.wav"
            try:
                wav_bytes, stem_hash = _encode_wav_24bit(stem_audio, sr)
                s3.put_object(
                    Bucket=settings.S3_BUCKET,
                    Key=stem_key,
                    Body=wav_bytes,
                    ContentType="audio/wav",
                    Metadata={
                        "sha256": stem_hash,
                        "user_id": user_id,
                        "session_id": session_id,
                        "stem_role": stem_name,
                    },
                )
            except Exception as exc:
                logger.error(
                    "separation_s3_write_failed",
                    session_id=session_id,
                    user_id=user_id,
                    stage="separation",
                    stem_role=stem_name,
                    key=stem_key,
                    error=str(exc),
                    error_code="RAIN-E622",
                )
                continue

            try:
                # Upsert: delete any prior row for this (session, stem_role), then insert.
                await db.execute(
                    _delete_existing_stem_stmt(UUID(session_id), stem_name)
                )
                stem_row = Stem(
                    session_id=UUID(session_id),
                    user_id=UUID(user_id),
                    stem_role=stem_name,
                    file_key=stem_key,
                    file_hash=stem_hash,
                    duration_ms=duration_ms,
                    source="bs_roformer_cascade",
                )
                db.add(stem_row)
                written += 1
            except Exception as exc:
                logger.error(
                    "separation_stem_insert_failed",
                    session_id=session_id,
                    user_id=user_id,
                    stage="separation",
                    stem_role=stem_name,
                    error=str(exc),
                    error_code="RAIN-E623",
                )
                continue

        try:
            await db.execute(
                update(MasteringSession)
                .where(MasteringSession.id == UUID(session_id))
                .values(status="separated")
            )
            await db.commit()
        except Exception as exc:
            logger.error(
                "separation_commit_failed",
                session_id=session_id,
                user_id=user_id,
                stage="separation",
                error=str(exc),
                error_code="RAIN-E623",
            )
            await db.rollback()
            return

        logger.info(
            "separation_complete",
            session_id=session_id,
            user_id=user_id,
            stage="separation",
            stems_written=written,
            duration_ms=int((time.monotonic() - t_start) * 1000),
        )


# ---------------------------------------------------------------------------
# Cascade orchestration
# ---------------------------------------------------------------------------


async def _run_cascade(
    audio: np.ndarray, sr: int, *, session_id: str, user_id: str
) -> dict[str, np.ndarray]:
    """Run all four passes and return the final 12-stem dict."""
    from app.services import separation_engine

    # Pass 1: 6-stem
    t0 = time.monotonic()
    pass1 = separation_engine.run_pass_1_6stem(_SeparationTaskBase._pass1_model, audio, sr)
    logger.info(
        "separation_pass_complete",
        session_id=session_id,
        user_id=user_id,
        stage="separation",
        pass_name="pass_1_6stem",
        duration_ms=int((time.monotonic() - t0) * 1000),
    )

    # Pass 2: karaoke (lead/backing) from pass-1 vocals
    t0 = time.monotonic()
    lead, backing = separation_engine.run_pass_2_karaoke(
        _SeparationTaskBase._pass2_model, pass1["vocals"], sr
    )
    logger.info(
        "separation_pass_complete",
        session_id=session_id,
        user_id=user_id,
        stage="separation",
        pass_name="pass_2_karaoke",
        duration_ms=int((time.monotonic() - t0) * 1000),
    )

    # Pass 3: drum breakdown from pass-1 drums
    t0 = time.monotonic()
    drum_pieces = separation_engine.run_pass_3_drums(
        _SeparationTaskBase._pass3_model, pass1["drums"], sr
    )
    logger.info(
        "separation_pass_complete",
        session_id=session_id,
        user_id=user_id,
        stage="separation",
        pass_name="pass_3_drums",
        duration_ms=int((time.monotonic() - t0) * 1000),
    )

    # Pass 4: dereverb room + fx_other from pass-1 other
    t0 = time.monotonic()
    room, fx_other = separation_engine.run_pass_4_dereverb(
        _SeparationTaskBase._pass4_model, pass1["other"], sr
    )
    logger.info(
        "separation_pass_complete",
        session_id=session_id,
        user_id=user_id,
        stage="separation",
        pass_name="pass_4_dereverb",
        duration_ms=int((time.monotonic() - t0) * 1000),
    )

    return {
        "lead_vocals": lead,
        "backing_vocals": backing,
        "kick": drum_pieces["kick"],
        "snare": drum_pieces["snare"],
        "hats": drum_pieces["hats"],
        "percussion": drum_pieces["percussion"],
        "bass": pass1["bass"],
        "guitar": pass1["guitar"],
        "piano": pass1["piano"],
        "room": room,
        "fx_other": fx_other,
        # Preserve the original pass-1 "other" bus for engineers who want the
        # pre-dereverb residual. Named _residual to disambiguate from fx_other.
        "other_residual": pass1["other"],
    }


def _ensure_models_loaded(checkpoint_path: str, device: str) -> None:
    """Load all four cascade models once per worker process."""
    from app.services import separation_engine

    if _SeparationTaskBase._pass1_model is None:
        _SeparationTaskBase._pass1_model = separation_engine.load_bsroformer_model(
            checkpoint_path, device
        )
    if _SeparationTaskBase._pass2_model is None:
        _SeparationTaskBase._pass2_model = separation_engine.load_bsroformer_model(
            checkpoint_path, device
        )
    if _SeparationTaskBase._pass3_model is None:
        _SeparationTaskBase._pass3_model = separation_engine.load_bsroformer_model(
            checkpoint_path, device
        )
    if _SeparationTaskBase._pass4_model is None:
        _SeparationTaskBase._pass4_model = separation_engine.load_bsroformer_model(
            checkpoint_path, device
        )


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------


async def _read_audio_stereo_44k(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    """Decode an audio bytestream to a (2, samples) float32 array at 44.1 kHz."""
    from app.core.audio_io import read_audio

    data, sr = await read_audio(audio_bytes, dtype="float32", always_2d=True)
    # data shape from soundfile: (samples, channels) with always_2d=True
    if data.ndim == 2:
        data = data.T  # -> (channels, samples)
    if data.shape[0] == 1:
        data = np.concatenate([data, data], axis=0)
    elif data.shape[0] > 2:
        data = data[:2, :]

    if sr != _TARGET_SR:
        # Resample to 44.1 kHz. The separation models are trained on 44.1k.
        # Kept async-friendly via to_thread.
        import librosa

        resampled_channels = await asyncio.to_thread(
            lambda: np.stack(
                [
                    librosa.resample(data[0], orig_sr=sr, target_sr=_TARGET_SR),
                    librosa.resample(data[1], orig_sr=sr, target_sr=_TARGET_SR),
                ]
            )
        )
        data = resampled_channels.astype(np.float32)
        sr = _TARGET_SR

    return data, sr


def _encode_wav_24bit(audio: np.ndarray, sr: int) -> tuple[bytes, str]:
    """Encode (channels, samples) float32 audio to 24-bit PCM WAV. Returns (bytes, sha256)."""
    if audio.ndim == 2:
        # soundfile expects (samples, channels) when writing
        out = audio.T
    else:
        out = audio
    buf = io.BytesIO()
    sf.write(buf, out, sr, subtype="PCM_24", format="WAV")
    raw = buf.getvalue()
    return raw, hashlib.sha256(raw).hexdigest()


def _delete_existing_stem_stmt(session_uuid, stem_role: str):
    """SQLAlchemy delete stmt for a prior stem row (idempotent upsert)."""
    from sqlalchemy import delete

    from app.models.stem import Stem

    return delete(Stem).where(
        Stem.session_id == session_uuid,
        Stem.stem_role == stem_role,
    )
