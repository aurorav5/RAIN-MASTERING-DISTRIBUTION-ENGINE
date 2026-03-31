from celery import shared_task
import structlog
import asyncio
import numpy as np

logger = structlog.get_logger()

@shared_task(name="app.tasks.render.render_session", bind=True, max_retries=2)
def render_session(self, session_id: str, user_id: str, mel_list: list, genre: str) -> None:
    asyncio.run(_render_session_async(session_id, user_id, np.array(mel_list, dtype=np.float32), genre))

async def _render_session_async(
    session_id: str,
    user_id: str,
    mel: np.ndarray,
    genre: str,
) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.session import Session as MasteringSession
    from app.models.aie import AIEProfile
    from app.services.inference import InferenceService
    from app.services.storage import download_from_s3, upload_to_s3
    from app.services.wasm_bridge import RainDSPBridge
    from app.services.rain_score import compute_rain_score
    from app.core.config import settings
    from sqlalchemy import select, update, text
    from uuid import UUID
    import time

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
            return

        # Idempotency: skip if already completed
        if session.status == "complete":
            logger.info("render_skip_idempotent", session_id=session_id)
            return

        try:
            aie_result = await db.execute(
                select(AIEProfile).where(AIEProfile.user_id == UUID(user_id))
            )
            aie_profile = aie_result.scalar_one_or_none()
            artist_vec = np.array(
                aie_profile.voice_vector if aie_profile and aie_profile.voice_vector else [0.0] * 64,
                dtype=np.float32,
            )

            inference_svc = InferenceService.get()
            params, source = inference_svc.get_params(
                mel_spectrogram=mel,
                artist_vector=artist_vec,
                genre=genre,
                platform=session.target_platform or "spotify",
                simple_mode=session.simple_mode,
            )
            logger.info("params_source", session_id=session_id, source=source, stage="render", user_id=user_id)

            audio_data = await download_from_s3(session.input_file_key)

            t0 = time.monotonic()
            bridge = RainDSPBridge()
            output_audio, result_obj = bridge.process(audio_data, params)
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.info("render_complete", session_id=session_id, duration_ms=duration_ms,
                        lufs=result_obj.integrated_lufs, stage="render", user_id=user_id)

            target_lufs = params.get("target_lufs", -14.0)
            drift = abs(result_obj.integrated_lufs - target_lufs)
            if drift > 0.5:
                logger.warning("lufs_drift", target=target_lufs, actual=result_obj.integrated_lufs,
                               drift=drift, session_id=session_id)

            output_key, output_hash = await upload_to_s3(
                output_audio, user_id, session_id,
                f"master_{session.target_platform or 'spotify'}.wav"
            )

            rain_score = await compute_rain_score(output_audio, session.target_platform or "spotify", mel)

            await db.execute(
                update(MasteringSession)
                .where(MasteringSession.id == UUID(session_id))
                .values(
                    status="complete",
                    output_file_key=output_key,
                    output_file_hash=output_hash,
                    output_lufs=round(result_obj.integrated_lufs, 2),
                    output_true_peak=round(result_obj.true_peak_dbtp, 2),
                    rain_score=rain_score,
                    processing_params=params,
                    rainnet_model_version=settings.RAIN_VERSION if source == "rainnet" else "heuristic",
                    aie_applied=(source == "rainnet"),
                )
            )
            await db.commit()

            from app.tasks.certification import sign_rain_cert
            from app.tasks.aie import update_aie_profile
            from app.tasks.content_scan import scan_content
            sign_rain_cert.delay(session_id, user_id)
            update_aie_profile.delay(session_id, user_id, mel.tolist(), params, genre)
            scan_content.delay(session_id, user_id)

        except Exception as e:
            logger.error("render_failed", session_id=session_id, error=str(e), stage="render", user_id=user_id)
            await db.execute(
                update(MasteringSession)
                .where(MasteringSession.id == UUID(session_id))
                .values(status="failed", error_code="RAIN-E300", error_detail=str(e))
            )
            await db.commit()
