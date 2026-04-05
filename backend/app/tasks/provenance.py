"""Celery task: stamp RAIN output with AudioSeal + C2PA + Chromaprint.

Runs on the `certification` queue (sister task to RAIN-CERT). Executes the
provenance pipeline on a completed session's output audio:

  1. AudioSeal neural watermark  (soft-fail: warn + continue on RAIN-E742)
  2. C2PA v2.2 manifest embed    (HARD-fail: RAIN-E740 on any failure)
  3. Chromaprint fingerprint     (soft-fail: warn + continue on RAIN-E743)

Idempotency: gated on session.provenance_stamped_at. The output is written
back to S3 at `users/{user_id}/{session_id}/output_stamped.wav`.
"""
from __future__ import annotations
import asyncio
import hashlib
import io
from uuid import UUID

import structlog
from celery import shared_task

logger = structlog.get_logger()


@shared_task(
    name="app.tasks.provenance.stamp_output",
    bind=True,
    max_retries=2,
    queue="certification",
)
def stamp_output(self, session_id: str, user_id: str) -> None:
    """Stamp the session's output audio with watermark + manifest + fingerprint."""
    asyncio.run(_stamp_output_async(session_id, user_id))


async def _stamp_output_async(session_id: str, user_id: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.session import Session as MasteringSession
    from sqlalchemy import select, update
    from app.services.provenance.c2pa_manifest import (
        build_c2pa_manifest,
        embed_c2pa_into_wav,
    )
    from app.services.provenance.fingerprint import compute_sha256

    async with AsyncSessionLocal() as db:
        await db.execute(f"SELECT set_app_user_id('{user_id}'::uuid)")

        sess_result = await db.execute(
            select(MasteringSession).where(MasteringSession.id == UUID(session_id))
        )
        session = sess_result.scalar_one_or_none()
        if not session:
            logger.error(
                "provenance_session_not_found",
                session_id=session_id,
                error_code="RAIN-E740",
                stage="provenance",
            )
            return

        # Idempotency gate (field may not exist yet — see report)
        already_stamped = getattr(session, "provenance_stamped_at", None)
        if already_stamped:
            logger.info(
                "provenance_skip_idempotent",
                session_id=session_id,
                stage="provenance",
            )
            return

        if not session.output_file_key:
            logger.error(
                "provenance_no_output",
                session_id=session_id,
                error_code="RAIN-E740",
                stage="provenance",
            )
            return

        # Load output audio from S3
        try:
            audio_bytes = await _load_from_s3(session.output_file_key)
        except Exception as e:
            logger.error(
                "provenance_s3_load_failed",
                session_id=session_id,
                error=str(e),
                error_code="RAIN-E740",
                stage="provenance",
            )
            raise self.retry(exc=e)

        original_len = len(audio_bytes)
        stamped_bytes = audio_bytes

        # --- Stage 1: AudioSeal watermark (soft-fail) ---
        try:
            import numpy as np
            from app.services.provenance.audioseal import embed_watermark

            samples, sr = _wav_bytes_to_samples(stamped_bytes)
            session_hash_src = f"{session_id}:{session.input_file_hash or ''}"
            session_hash = hashlib.sha256(session_hash_src.encode()).hexdigest()
            wm_samples = embed_watermark(
                samples,
                sample_rate=sr,
                session_hash=session_hash,
            )
            stamped_bytes = _samples_to_wav_bytes(wm_samples, sr, template=stamped_bytes)
            logger.info(
                "provenance_audioseal_ok",
                session_id=session_id,
                stage="provenance",
            )
        except Exception as e:
            logger.warning(
                "provenance_audioseal_skipped",
                session_id=session_id,
                error=str(e),
                error_code="RAIN-E742",
                stage="provenance",
            )

        # --- Stage 2: C2PA manifest embed (HARD fail) ---
        try:
            from app.core.config import settings
            rain_version = getattr(settings, "RAIN_VERSION", "6.0.0")
            manifest = build_c2pa_manifest(
                {
                    "session_id": session_id,
                    "rain_version": rain_version,
                    "input_file_hash": session.input_file_hash,
                    "output_file_hash": session.output_file_hash,
                    "wasm_binary_hash": session.wasm_binary_hash,
                    "rainnet_model_version": session.rainnet_model_version,
                    "processing_params": session.processing_params,
                    "ai_generated": session.ai_generated,
                    "user_id_hash": hashlib.sha256(user_id.encode()).hexdigest(),
                }
            )
            pre_c2pa = stamped_bytes
            stamped_bytes = embed_c2pa_into_wav(stamped_bytes, manifest)
            if stamped_bytes == pre_c2pa:
                # embed_c2pa_into_wav returns original on failure — HARD fail
                raise RuntimeError(
                    "C2PA embed returned unmodified bytes (embed failed silently)"
                )
            logger.info(
                "provenance_c2pa_ok",
                session_id=session_id,
                bytes_added=len(stamped_bytes) - len(pre_c2pa),
                stage="provenance",
            )
        except Exception as e:
            logger.error(
                "provenance_c2pa_failed",
                session_id=session_id,
                error=str(e),
                error_code="RAIN-E740",
                stage="provenance",
            )
            raise

        # --- Stage 3: Chromaprint fingerprint (soft-fail) ---
        fingerprint_str = ""
        try:
            from app.services.provenance.fingerprint import compute_chromaprint
            import numpy as np

            fp_samples, fp_sr = _wav_bytes_to_samples(stamped_bytes)
            fingerprint_str = compute_chromaprint(fp_samples, fp_sr)
            logger.info(
                "provenance_fingerprint_ok",
                session_id=session_id,
                fp_len=len(fingerprint_str),
                stage="provenance",
            )
        except Exception as e:
            logger.warning(
                "provenance_fingerprint_skipped",
                session_id=session_id,
                error=str(e),
                error_code="RAIN-E743",
                stage="provenance",
            )

        # Write stamped output back to S3
        stamped_key = f"users/{user_id}/{session_id}/output_stamped.wav"
        try:
            await _write_to_s3(stamped_key, stamped_bytes)
        except Exception as e:
            logger.error(
                "provenance_s3_write_failed",
                session_id=session_id,
                error=str(e),
                error_code="RAIN-E740",
                stage="provenance",
            )
            raise self.retry(exc=e)

        stamped_hash = compute_sha256(stamped_bytes)

        # Update session row (provenance_stamped_at / stamped_output_key may not exist — see report)
        from datetime import datetime, timezone
        update_values: dict = {}
        if hasattr(MasteringSession, "provenance_stamped_at"):
            update_values["provenance_stamped_at"] = datetime.now(timezone.utc)
        if hasattr(MasteringSession, "stamped_output_key"):
            update_values["stamped_output_key"] = stamped_key
        if hasattr(MasteringSession, "chromaprint_fingerprint"):
            update_values["chromaprint_fingerprint"] = fingerprint_str
        if hasattr(MasteringSession, "stamped_output_hash"):
            update_values["stamped_output_hash"] = stamped_hash

        if update_values:
            await db.execute(
                update(MasteringSession)
                .where(MasteringSession.id == UUID(session_id))
                .values(**update_values)
            )
            await db.commit()

        logger.info(
            "provenance_stamped",
            session_id=session_id,
            user_id=user_id,
            stamped_key=stamped_key,
            bytes_original=original_len,
            bytes_stamped=len(stamped_bytes),
            stage="provenance",
        )


async def _load_from_s3(key: str) -> bytes:
    """Load object bytes from the RAIN S3 bucket."""
    from app.core.config import settings
    import aioboto3  # type: ignore

    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=getattr(settings, "S3_ENDPOINT_URL", None),
        aws_access_key_id=getattr(settings, "S3_ACCESS_KEY", None),
        aws_secret_access_key=getattr(settings, "S3_SECRET_KEY", None),
    ) as s3:
        resp = await s3.get_object(
            Bucket=getattr(settings, "S3_BUCKET", "rain-audio"), Key=key
        )
        return await resp["Body"].read()


async def _write_to_s3(key: str, data: bytes) -> None:
    """Write bytes to the RAIN S3 bucket."""
    from app.core.config import settings
    import aioboto3  # type: ignore

    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=getattr(settings, "S3_ENDPOINT_URL", None),
        aws_access_key_id=getattr(settings, "S3_ACCESS_KEY", None),
        aws_secret_access_key=getattr(settings, "S3_SECRET_KEY", None),
    ) as s3:
        await s3.put_object(
            Bucket=getattr(settings, "S3_BUCKET", "rain-audio"),
            Key=key,
            Body=data,
            ContentType="audio/wav",
        )


def _wav_bytes_to_samples(wav_bytes: bytes):
    """Decode WAV bytes to float32 numpy samples + sample rate."""
    import numpy as np
    import wave

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        sr = wf.getframerate()
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sampwidth == 2:
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        arr = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif sampwidth == 3:
        # 24-bit little-endian
        a = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        i32 = (a[:, 0].astype(np.int32)
               | (a[:, 1].astype(np.int32) << 8)
               | (a[:, 2].astype(np.int32) << 16))
        i32 = np.where(i32 & 0x800000, i32 | ~0xFFFFFF, i32)
        arr = i32.astype(np.float32) / 8388608.0
    else:
        raise ValueError(f"unsupported WAV sampwidth: {sampwidth}")

    if n_channels > 1:
        arr = arr.reshape(-1, n_channels).T  # (channels, n_samples)
    return arr, sr


def _samples_to_wav_bytes(samples, sample_rate: int, template: bytes) -> bytes:
    """Encode float32 samples back to 16-bit PCM WAV bytes."""
    import numpy as np
    import wave

    if samples.ndim == 1:
        data = samples
        n_channels = 1
    else:
        # (channels, n_samples) -> interleave
        n_channels = samples.shape[0]
        data = samples.T.reshape(-1)

    clipped = np.clip(data, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)

    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return out.getvalue()
