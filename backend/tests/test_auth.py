"""
Integration tests for /api/v1/auth/* endpoints.

Requires a real or test PostgreSQL database reachable via DATABASE_URL env var.
Falls back to a lightweight in-process test setup that stubs the DB session when
DATABASE_URL is not pointing at a real Postgres instance — those cases are marked
with pytest.mark.skipif where a real DB is strictly required.
"""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# App import — defer so that missing env vars don't kill collection
# ---------------------------------------------------------------------------
os.environ.setdefault("RAIN_ENV", "test")
os.environ.setdefault("RAIN_VERSION", "6.0.0")
os.environ.setdefault("RAIN_LOG_LEVEL", "error")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://rain:rain@localhost:5432/rain_test")
os.environ.setdefault("VALKEY_URL", "redis://localhost:6379/1")
os.environ.setdefault("S3_BUCKET", "rain-test")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "minioadmin")
os.environ.setdefault("S3_SECRET_KEY", "minioadmin")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_placeholder")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

_REAL_PG = "localhost" in os.environ.get("DATABASE_URL", "")

# ---------------------------------------------------------------------------
# JWT key pair — generated in-memory for test isolation
# ---------------------------------------------------------------------------
import tempfile
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


@pytest.fixture(scope="session", autouse=True)
def jwt_keys(tmp_path_factory):
    """Generate a temporary RS256 key pair and point settings at it."""
    tmp = tmp_path_factory.mktemp("jwt_keys")
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
# Shared mock DB session
# ---------------------------------------------------------------------------

def _make_mock_db():
    """Return an AsyncSession mock with configurable scalar_one_or_none."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.refresh = AsyncMock()
    return mock_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(jwt_keys):
    """Async HTTP client wrapping the FastAPI app."""
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helper — build a fake scalar result
# ---------------------------------------------------------------------------

def _scalar_result(value):
    m = MagicMock()
    m.scalar_one_or_none.return_value = value
    return m


# ---------------------------------------------------------------------------
# Test 1: Register → 201, tokens present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_success(client, jwt_keys):
    mock_db = _make_mock_db()
    # First execute: check existing user → None
    mock_db.execute.return_value = _scalar_result(None)

    with patch("app.api.routes.auth.get_db", return_value=mock_db):
        # Also patch async generator
        async def override_db():
            yield mock_db

        from app.main import app
        from app.core.database import get_db
        app.dependency_overrides[get_db] = override_db

        resp = await client.post("/api/v1/auth/register", json={
            "email": "alice@example.com",
            "password": "StrongPass1!"
        })

        app.dependency_overrides.clear()

    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["tier"] == "free"
    assert "user_id" in body


# ---------------------------------------------------------------------------
# Test 2: Duplicate email → 409 RAIN-E100
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_duplicate_email(client, jwt_keys):
    from app.models.user import User
    from app.main import app
    from app.core.database import get_db

    existing_user = MagicMock(spec=User)
    existing_user.email = "alice@example.com"

    mock_db = _make_mock_db()
    mock_db.execute.return_value = _scalar_result(existing_user)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    resp = await client.post("/api/v1/auth/register", json={
        "email": "alice@example.com",
        "password": "StrongPass1!"
    })
    app.dependency_overrides.clear()

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "RAIN-E100"


# ---------------------------------------------------------------------------
# Test 3: Login correct credentials → 200, valid JWT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_success(client, jwt_keys):
    from app.models.user import User
    from app.models.subscription import Subscription
    from app.core.security import hash_password
    from app.main import app
    from app.core.database import get_db

    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "bob@example.com"
    user.password_hash = hash_password("MyPassword9!")
    user.is_active = True
    user.last_login_at = None

    sub = MagicMock(spec=Subscription)
    sub.tier = "spark"

    mock_db = _make_mock_db()
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _scalar_result(user)
        return _scalar_result(sub)

    mock_db.execute.side_effect = side_effect

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    resp = await client.post("/api/v1/auth/login", json={
        "email": "bob@example.com",
        "password": "MyPassword9!"
    })
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["tier"] == "spark"


# ---------------------------------------------------------------------------
# Test 4: Login wrong password → 401 RAIN-E100
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_wrong_password(client, jwt_keys):
    from app.models.user import User
    from app.core.security import hash_password
    from app.main import app
    from app.core.database import get_db

    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "carol@example.com"
    user.password_hash = hash_password("CorrectHorseBattery1!")
    user.is_active = True

    mock_db = _make_mock_db()
    mock_db.execute.return_value = _scalar_result(user)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    resp = await client.post("/api/v1/auth/login", json={
        "email": "carol@example.com",
        "password": "WrongPassword!"
    })
    app.dependency_overrides.clear()

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "RAIN-E100"


# ---------------------------------------------------------------------------
# Test 5: GET /health is publicly accessible (no auth needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_endpoint_unprotected(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Test 6: Protected route without token → 401/403
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_protected_route_without_token(client):
    import uuid
    session_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/sessions/{session_id}")
    # HTTPBearer returns 403 when no Authorization header is present
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Test 7: Free user hits creator-only endpoint → 403 RAIN-E101
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_free_user_tier_gated_endpoint(client, jwt_keys):
    """
    Register a free user, obtain their token, then call an endpoint guarded
    by require_tier("creator") — expect 403 RAIN-E101.

    We add a minimal test-only route to the app for this purpose so the test
    doesn't depend on PART-6+ routes existing yet.
    """
    from fastapi import APIRouter, Depends
    from app.api.dependencies import require_tier, CurrentUser
    from app.main import app
    from app.core.database import get_db

    # Register a free user (mock DB)
    mock_db = _make_mock_db()
    mock_db.execute.return_value = _scalar_result(None)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    reg_resp = await client.post("/api/v1/auth/register", json={
        "email": "freeguy@example.com",
        "password": "FreeUserPass1!"
    })
    app.dependency_overrides.clear()

    assert reg_resp.status_code == 201
    free_token = reg_resp.json()["access_token"]

    # Add a temporary creator-only route
    test_router = APIRouter()

    @test_router.get("/test-creator-only")
    async def creator_endpoint(
        cu: CurrentUser = Depends(require_tier("creator"))
    ) -> dict:
        return {"ok": True}

    app.include_router(test_router, prefix="/api/v1")

    resp = await client.get(
        "/api/v1/test-creator-only",
        headers={"Authorization": f"Bearer {free_token}"}
    )

    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "RAIN-E101"
