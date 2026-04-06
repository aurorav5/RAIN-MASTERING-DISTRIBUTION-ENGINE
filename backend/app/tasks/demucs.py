"""DEPRECATED: Demucs stem-separation task.

RAIN v6.0 replaces Demucs htdemucs_6s with a 4-pass BS-RoFormer cascade that
produces 12 stems (see app.tasks.separation.separate_bsroformer).

This module is retained only for backward compatibility with callers that still
dispatch `app.tasks.demucs.separate_stems`. The task signature is unchanged:
    separate_stems(session_id: str, user_id: str) -> None

New code should call `app.tasks.separation.separate_bsroformer` directly.
"""
from __future__ import annotations

import structlog
from celery import shared_task

logger = structlog.get_logger()


@shared_task(name="app.tasks.demucs.separate_stems", bind=True, max_retries=2)
def separate_stems(self, session_id: str, user_id: str) -> None:
    """Back-compat shim — delegates to the BS-RoFormer cascade task.

    Routed to the same gpu_priority_medium queue as separate_bsroformer.
    """
    logger.warning(
        "demucs_separate_stems_deprecated",
        session_id=session_id,
        user_id=user_id,
        stage="separation",
        note=(
            "app.tasks.demucs.separate_stems is deprecated — delegating to "
            "app.tasks.separation.separate_bsroformer (BS-RoFormer 12-stem cascade)"
        ),
    )
    # Late import to avoid circular import at Celery worker boot.
    from app.tasks.separation import separate_bsroformer

    # Run inline (same worker process, same queue) to preserve the original
    # call semantics: callers expect this function to complete the separation
    # work, not just enqueue it.
    separate_bsroformer.run(session_id, user_id)
