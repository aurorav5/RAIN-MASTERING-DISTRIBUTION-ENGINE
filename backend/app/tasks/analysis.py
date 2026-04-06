from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import io

logger = structlog.get_logger()

@shared_task(name="app.tasks.analysis.analyze_session", bind=True, max_retries=3)
def analyze_session(self, session_id: str, user_id: str) -> None:
    import asyncio
    asyncio.run(_analyze_session_async(session_id, user_id))

async def _analyze_session_async(session_id: str, user_id: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.session import Session as MasteringSession
    from app.services.storage import download_from_s3
    from app.services.audio_analysis import extract_mel_spectrogram, measure_lufs_true_peak
    from sqlalchemy import select, update, text
    from uuid import UUID

    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(user_id)})

        result = await db.execute(
            select(MasteringSession).where(
                MasteringSession.id == UUID(session_id),
                MasteringSession.user_id == UUID(user_id),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            logger.error("analysis_session_not_found", session_id=session_id)
            return

        # Idempotency: skip if already past analysis stage
        if session.status not in ("analyzing", "uploaded"):
            logger.info("analysis_skip_idempotent", session_id=session_id, status=session.status)
            return

        try:
            if session.input_file_key:
                audio_data = await download_from_s3(session.input_file_key)
            else:
                # Free tier: audio not persisted
                await db.execute(
                    update(MasteringSession)
                    .where(MasteringSession.id == UUID(session_id))
                    .values(status="failed", error_code="RAIN-E200",
                            error_detail="Free tier audio not persisted for server-side analysis")
                )
                await db.commit()
                return

            import time as _time
            t0 = _time.monotonic()
            lufs, tp = await measure_lufs_true_peak(audio_data)
            lufs_ms = int((_time.monotonic() - t0) * 1000)
            logger.info("analysis_lufs_measured", session_id=session_id, user_id=user_id, stage="analysis", duration_ms=lufs_ms, lufs=round(lufs, 2), true_peak=round(tp, 2))

            t0 = _time.monotonic()
            mel, duration, _ = extract_mel_spectrogram(audio_data)
            mel_ms = int((_time.monotonic() - t0) * 1000)
            logger.info("analysis_mel_extracted", session_id=session_id, user_id=user_id, stage="analysis", duration_ms=mel_ms)

            genre = _classify_genre(mel) or session.genre

            await db.execute(
                update(MasteringSession)
                .where(MasteringSession.id == UUID(session_id))
                .values(
                    status="processing",
                    input_duration_ms=int(duration * 1000),
                    input_lufs=round(lufs, 2),
                    input_true_peak=round(tp, 2),
                    genre=genre,
                )
            )
            await db.commit()

            from app.tasks.render import render_session
            render_session.delay(session_id, user_id, mel.tolist(), genre)

        except Exception as e:
            logger.error("analysis_failed", session_id=session_id, error=str(e), stage="analysis", user_id=user_id)
            await db.execute(
                update(MasteringSession)
                .where(MasteringSession.id == UUID(session_id))
                .values(status="failed", error_code="RAIN-E301", error_detail=str(e))
            )
            await db.commit()

_GENRE_LABELS: tuple[str, ...] = (
    "afropop_house", "hiphop", "electronic", "pop", "rock",
    "rnb_soul", "jazz", "classical", "latin", "gospel", "podcast",
)

_genre_ort_session = None


def _classify_genre(mel) -> str:
    """Genre classification: ONNX inference if enabled, else fallback to 'default'.

    Gate: GENRE_CLASSIFIER_ENABLED must be true and the ONNX checkpoint must
    exist at ml/checkpoints/genre_classifier.onnx.
    """
    import structlog
    _logger = structlog.get_logger()

    from app.core.config import settings
    if not getattr(settings, "GENRE_CLASSIFIER_ENABLED", False):
        _logger.info(
            "genre_classifier_disabled",
            stage="analysis",
            note="GENRE_CLASSIFIER_ENABLED=false — using 'default'",
        )
        return "default"

    global _genre_ort_session
    if _genre_ort_session is None:
        from pathlib import Path
        ckpt = Path("ml/checkpoints/genre_classifier.onnx")
        if not ckpt.exists():
            _logger.warning(
                "genre_classifier_checkpoint_missing",
                error_code="RAIN-E401",
                stage="analysis",
                path=str(ckpt),
            )
            return "default"
        try:
            import onnxruntime as ort
            _genre_ort_session = ort.InferenceSession(
                str(ckpt), providers=["CPUExecutionProvider"]
            )
        except Exception as e:
            _logger.error(
                "genre_classifier_load_failed",
                error_code="RAIN-E401",
                stage="analysis",
                error=str(e),
            )
            return "default"

    try:
        import numpy as np
        # Prepare input: model expects [B, 1, 128, 128]
        if mel is None:
            return "default"
        mel_input = np.array(mel, dtype=np.float32)
        if mel_input.ndim == 2:
            mel_input = mel_input[np.newaxis, np.newaxis, :128, :128]
        elif mel_input.ndim == 3:
            mel_input = mel_input[np.newaxis, :, :128, :128]

        # Pad if smaller than 128x128
        if mel_input.shape[2] < 128 or mel_input.shape[3] < 128:
            padded = np.zeros((1, 1, 128, 128), dtype=np.float32)
            h, w = min(128, mel_input.shape[2]), min(128, mel_input.shape[3])
            padded[0, 0, :h, :w] = mel_input[0, 0, :h, :w]
            mel_input = padded

        input_name = _genre_ort_session.get_inputs()[0].name
        output = _genre_ort_session.run(None, {input_name: mel_input})
        probs = output[0][0]

        # Map to 11 RAIN genres (model has 87 classes, we pick top match from our 11)
        top_idx = int(np.argmax(probs[:len(_GENRE_LABELS)]))
        genre = _GENRE_LABELS[top_idx] if top_idx < len(_GENRE_LABELS) else "default"

        _logger.info(
            "genre_classified",
            stage="analysis",
            genre=genre,
            confidence=float(probs[top_idx]),
        )
        return genre

    except Exception as e:
        _logger.error(
            "genre_classifier_inference_failed",
            error_code="RAIN-E401",
            stage="analysis",
            error=str(e),
        )
        return "default"
