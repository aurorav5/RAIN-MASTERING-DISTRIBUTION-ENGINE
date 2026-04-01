"""
Unit tests for quota enforcement logic in app.services.quota.

These tests exercise the service functions directly (no HTTP layer) using
an in-memory mocked AsyncSession — no database connection required.
"""
import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

os.environ.setdefault("RAIN_ENV", "test")
os.environ.setdefault("RAIN_VERSION", "6.0.0")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://rain:rain@localhost:5432/rain_test")
os.environ.setdefault("VALKEY_URL", "redis://localhost:6379/1")
os.environ.setdefault("S3_BUCKET", "rain-test")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "minioadmin")
os.environ.setdefault("S3_SECRET_KEY", "minioadmin")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_placeholder")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")


def _make_mock_db():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.refresh = AsyncMock()
    return mock_db


def _scalar_result(value):
    m = MagicMock()
    m.scalar_one_or_none.return_value = value
    return m


# ---------------------------------------------------------------------------
# Test 1: Free tier download → 403 RAIN-E101
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_free_tier_download_blocked():
    from fastapi import HTTPException
    from app.services.quota import check_and_increment_downloads

    mock_db = _make_mock_db()
    user_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        await check_and_increment_downloads(user_id, "free", mock_db)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "RAIN-E101"


# ---------------------------------------------------------------------------
# Test 2: spark tier with renders_used == 50 → 429 RAIN-E701
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_spark_render_quota_exhausted():
    from fastapi import HTTPException
    from app.models.quota import UsageQuota
    from app.services.quota import check_and_increment_renders

    user_id = uuid4()

    # Build a quota record that is already at the spark render limit (50)
    quota = MagicMock(spec=UsageQuota)
    quota.renders_used = 50
    quota.downloads_used = 0
    quota.period_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    mock_db = _make_mock_db()
    mock_db.execute.return_value = _scalar_result(quota)

    with pytest.raises(HTTPException) as exc_info:
        await check_and_increment_renders(user_id, "spark", mock_db)

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["code"] == "RAIN-E701"
