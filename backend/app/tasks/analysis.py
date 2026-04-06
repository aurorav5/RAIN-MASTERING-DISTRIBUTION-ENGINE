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

def _classify_genre(mel) -> str:
    """Genre classification fallback.

    Returns 'default' until GenreClassifier ONNX is trained and deployed.
    Logs RAIN-E401 so the failure is observable in monitoring — not silent.
    """
    # TODO(RAIN-ML): Wire ml/genre_classifier/model.py ONNX checkpoint here.
    # Once available: load checkpoint, run inference on mel, return top-1 genre label.
    import structlog
    _logger = structlog.get_logger()
    _logger.info(
        "genre_classifier_fallback",
        error_code="RAIN-E401",
        stage="analysis",
        note="GenreClassifier not deployed — returning 'default'. Train and export ONNX to enable.",
    )
    return "default"
