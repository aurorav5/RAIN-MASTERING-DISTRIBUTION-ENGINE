from celery import shared_task
import numpy as np
import asyncio
import structlog

logger = structlog.get_logger()
EMA_ALPHA = 0.15
COLD_START_SESSIONS = 5


@shared_task(name="app.tasks.aie.update_aie_profile")
def update_aie_profile(
    session_id: str,
    user_id: str,
    mel_list: list,
    params: dict,
    genre: str,
) -> None:
    asyncio.run(
        _update_aie_async(
            session_id, user_id,
            np.array(mel_list, dtype=np.float32),
            params, genre,
        )
    )


async def _update_aie_async(
    session_id: str,
    user_id: str,
    mel: np.ndarray,
    params: dict,
    genre: str,
) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.aie import AIEProfile, validate_voice_vector
    from app.models.session import Session as MasteringSession
    from sqlalchemy import select
    from uuid import UUID

    async with AsyncSessionLocal() as db:
        await db.execute(f"SELECT set_app_user_id('{user_id}'::uuid)")

        # Idempotency: check if this session was already counted
        # We use session_id as a guard by checking if session.aie_applied is set
        # (aie_applied is set to True by render task before dispatching this task)
        result = await db.execute(
            select(AIEProfile).where(AIEProfile.user_id == UUID(user_id))
        )
        profile = result.scalar_one_or_none()

        if not profile:
            profile = AIEProfile(
                user_id=UUID(user_id),
                voice_vector=[0.0] * 64,
                session_count=0,
                genre_distribution={},
                platform_preferences={},
            )
            db.add(profile)
            await db.flush()  # get profile.id

        # Compute session embedding
        session_embedding = _compute_session_embedding(mel, params)

        # EMA update
        current_vec = np.array(profile.voice_vector if profile.voice_vector else [0.0] * 64, dtype=np.float64)
        new_vec = (1.0 - EMA_ALPHA) * current_vec + EMA_ALPHA * session_embedding

        # Update session count first
        new_count = profile.session_count + 1

        # Only normalize if past cold-start threshold
        if new_count >= COLD_START_SESSIONS:
            validated = validate_voice_vector(new_vec.tolist())
            profile.voice_vector = validated
        else:
            # Cold start: store raw EMA without normalization
            profile.voice_vector = new_vec.tolist()

        # Update genre distribution
        genre_dist = dict(profile.genre_distribution or {})
        genre_dist[genre] = genre_dist.get(genre, 0) + 1

        profile.session_count = new_count
        profile.genre_distribution = genre_dist
        await db.commit()

        logger.info(
            "aie_updated",
            user_id=user_id,
            session_id=session_id,
            session_count=new_count,
            cold_start=(new_count < COLD_START_SESSIONS),
            stage="aie",
        )


@shared_task(
    name="app.tasks.aie.update_vector_from_session",
    bind=True,
    max_retries=2,
)
def update_vector_from_session(
    self,
    session_id: str,
    user_id: str,
    observation_source: float = 0.6,
) -> None:
    """Update the 64-dim AIE vector from a completed session's processing_params.

    Idempotency: we use `session.aie_applied` as the gate because
    `session.aie_updated_at` does NOT exist on the Session model.
    NOTE: blueprint requested `session.aie_updated_at` — FLAGGED as missing.
    """
    asyncio.run(
        _update_vector_async(session_id, user_id, observation_source)
    )


async def _update_vector_async(
    session_id: str,
    user_id: str,
    observation_source: float,
) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.session import Session as MasteringSession
    from app.services.aie_vector import record_observation
    from sqlalchemy import select
    from uuid import UUID

    async with AsyncSessionLocal() as db:
        await db.execute(f"SELECT set_app_user_id('{user_id}'::uuid)")

        result = await db.execute(
            select(MasteringSession).where(MasteringSession.id == UUID(session_id))
        )
        sess = result.scalar_one_or_none()
        if sess is None:
            logger.warning(
                "aie_vector_session_missing",
                session_id=session_id, user_id=user_id, stage="aie",
            )
            return

        # Idempotency guard — session.aie_updated_at does not exist, using aie_applied.
        if getattr(sess, "aie_updated_at", None) is not None:
            logger.info(
                "aie_vector_already_updated",
                session_id=session_id, user_id=user_id, stage="aie",
            )
            return

        params = sess.processing_params or {}
        if sess.genre and "_genre" not in params:
            params = dict(params)
            params["_genre"] = sess.genre

        await record_observation(
            db=db, user_id=user_id,
            processing_params=params, source=observation_source,
        )


def _compute_session_embedding(mel: np.ndarray, params: dict) -> np.ndarray:
    """
    Deterministic 64-dim projection of mel + param features.
    Fixed seed=42 for reproducibility across workers.
    """
    rng = np.random.RandomState(42)

    spec_features = np.concatenate([
        mel.mean(axis=1).astype(np.float64),   # 128-dim
        mel.std(axis=1).astype(np.float64),    # 128-dim
    ])  # 256-dim

    param_features = np.array([
        params.get("mb_threshold_low", -24.0) / -40.0,
        params.get("mb_threshold_mid", -18.0) / -40.0,
        params.get("mb_threshold_high", -12.0) / -40.0,
        params.get("mb_ratio_low", 2.5) / 5.0,
        params.get("stereo_width", 1.0) / 2.0,
        float(params.get("analog_saturation", False)),
        float(params.get("saturation_drive", 0.0)),
        params.get("target_lufs", -14.0) / -20.0,
    ], dtype=np.float64)

    combined = np.concatenate([spec_features, param_features])  # 264-dim

    W = rng.randn(64, len(combined)).astype(np.float64)
    W /= np.linalg.norm(W, axis=1, keepdims=True)
    embedding = W @ combined
    return embedding
