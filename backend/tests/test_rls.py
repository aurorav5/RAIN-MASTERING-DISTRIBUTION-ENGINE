"""
Critical RLS (Row-Level Security) cross-tenant isolation test.

Requires a real PostgreSQL database.  When DATABASE_URL is not set to a real
Postgres instance (detected by absence of "postgresql" in the URL or by an
explicit TEST_SKIP_RLS=1 env flag), all tests in this module are skipped.

Run against real DB:
    DATABASE_URL=postgresql+asyncpg://rain:rain@localhost:5432/rain_test \
        pytest backend/tests/test_rls.py -v
"""
import os
import sys
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

# ---------------------------------------------------------------------------
# Skip guard — must be declared before any app imports that need real DB
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "")
_HAS_REAL_PG = (
    "postgresql" in DATABASE_URL
    and os.environ.get("TEST_SKIP_RLS", "0") != "1"
)

pytestmark = pytest.mark.skipif(
    not _HAS_REAL_PG,
    reason="RLS tests require a real PostgreSQL database (set DATABASE_URL to postgresql+asyncpg://...)"
)

os.environ.setdefault("RAIN_ENV", "test")
os.environ.setdefault("RAIN_VERSION", "6.0.0")
os.environ.setdefault("RAIN_LOG_LEVEL", "error")
os.environ.setdefault("VALKEY_URL", "redis://localhost:6379/1")
os.environ.setdefault("S3_BUCKET", "rain-test")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "minioadmin")
os.environ.setdefault("S3_SECRET_KEY", "minioadmin")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_placeholder")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")


# ---------------------------------------------------------------------------
# JWT key pair — generated in-memory for test isolation
# ---------------------------------------------------------------------------
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


@pytest.fixture(scope="module", autouse=True)
def jwt_keys(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("jwt_keys_rls")
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    priv_path = tmp / "jwt.key"
    pub_path = tmp / "jwt.pub"
    priv_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    pub_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    os.environ["JWT_PRIVATE_KEY_PATH"] = str(priv_path)
    os.environ["JWT_PUBLIC_KEY_PATH"] = str(pub_path)
    return {"private": str(priv_path), "public": str(pub_path)}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="module")
async def app_client(jwt_keys):
    """Single AsyncClient shared across the RLS test module."""
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="module")
async def user_a_token(app_client) -> str:
    resp = await app_client.post("/api/v1/auth/register", json={
        "email": f"user_a_{uuid4().hex[:6]}@rls.test",
        "password": "UserAPassword1!"
    })
    assert resp.status_code == 201, f"user_a register failed: {resp.text}"
    return resp.json()["access_token"]


@pytest_asyncio.fixture(scope="module")
async def user_b_token(app_client) -> str:
    resp = await app_client.post("/api/v1/auth/register", json={
        "email": f"user_b_{uuid4().hex[:6]}@rls.test",
        "password": "UserBPassword1!"
    })
    assert resp.status_code == 201, f"user_b register failed: {resp.text}"
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Helper: create a session for a user via a mocked upload
# (real DB but mocked worker + S3 to avoid needing full infrastructure)
# ---------------------------------------------------------------------------

import io
from unittest.mock import patch

TINY_WAV = (
    b"RIFF" + (36).to_bytes(4, "little") +
    b"WAVEfmt " + (16).to_bytes(4, "little") +
    (1).to_bytes(2, "little") +
    (2).to_bytes(2, "little") +
    (44100).to_bytes(4, "little") +
    (176400).to_bytes(4, "little") +
    (4).to_bytes(2, "little") +
    (16).to_bytes(2, "little") +
    b"data" + (0).to_bytes(4, "little")
)


# ---------------------------------------------------------------------------
# RLS Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rls_cross_tenant_returns_404(app_client, user_a_token, user_b_token):
    """
    1. user_A creates a session.
    2. user_B tries to GET that session → must receive 404 (not 403).
    3. user_A can GET their own session → 200.
    """
    # Step 1: user_A creates a session (worker task is stubbed)
    with patch("app.api.routes.upload.analyze_session") as mock_task:
        mock_task.delay = MagicMock()
        create_resp = await app_client.post(
            "/api/v1/sessions/",
            files={"file": ("track.wav", io.BytesIO(TINY_WAV), "audio/wav")},
            data={"target_platform": "spotify", "simple_mode": "true"},
            headers={"Authorization": f"Bearer {user_a_token}"},
        )

    assert create_resp.status_code == 201, f"Session create failed: {create_resp.text}"
    session_id = create_resp.json()["id"]

    # Step 2: user_B tries to access user_A's session
    b_resp = await app_client.get(
        f"/api/v1/sessions/{session_id}",
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    # CRITICAL: must be 404, not 403, to prevent tenant enumeration
    assert b_resp.status_code == 404, (
        f"Expected 404 for cross-tenant access, got {b_resp.status_code}: {b_resp.text}"
    )

    # Step 3: user_A can access their own session
    a_resp = await app_client.get(
        f"/api/v1/sessions/{session_id}",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert a_resp.status_code == 200, (
        f"Expected 200 for owner access, got {a_resp.status_code}: {a_resp.text}"
    )
    assert a_resp.json()["id"] == session_id
