"""Valkey/Redis-backed session store with TTL. Replaces in-memory sessions
so API servers can scale horizontally behind Traefik/Coolify.

Key format: rain:session:{session_token} -> JSON { user_id, tier, created_at, ... }
Default TTL: 60 minutes, refreshed on every touch.
"""
from __future__ import annotations
import json
from typing import Optional
from uuid import UUID
import redis.asyncio as aioredis
import structlog

from app.core.config import settings

logger = structlog.get_logger()

_SESSION_PREFIX = "rain:session:"
_DEFAULT_TTL_SECONDS = 60 * 60  # 1 hour

_redis: Optional[aioredis.Redis] = None


def _client() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.VALKEY_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _redis


async def put_session(
    session_token: str,
    user_id: UUID,
    tier: str,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    **extra: object,
) -> None:
    key = _SESSION_PREFIX + session_token
    payload = {
        "user_id": str(user_id),
        "tier": tier,
        **extra,
    }
    await _client().setex(key, ttl_seconds, json.dumps(payload))


async def get_session(session_token: str, refresh_ttl: bool = True) -> Optional[dict]:
    key = _SESSION_PREFIX + session_token
    client = _client()
    raw = await client.get(key)
    if raw is None:
        return None
    if refresh_ttl:
        await client.expire(key, _DEFAULT_TTL_SECONDS)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("session_store_corrupt", session_token_prefix=session_token[:8])
        return None


async def delete_session(session_token: str) -> None:
    await _client().delete(_SESSION_PREFIX + session_token)


async def delete_all_user_sessions(user_id: UUID) -> int:
    """Revoke all sessions for a user (logout everywhere). Returns count deleted."""
    client = _client()
    deleted = 0
    async for key in client.scan_iter(match=f"{_SESSION_PREFIX}*", count=200):
        raw = await client.get(key)
        if raw:
            try:
                if json.loads(raw).get("user_id") == str(user_id):
                    await client.delete(key)
                    deleted += 1
            except json.JSONDecodeError:
                continue
    return deleted
