"""
Upload endpoint tests.

S3 is monkeypatched — no real S3/MinIO needed.
A real or mocked PostgreSQL session is used via dependency_overrides.
"""
import os
import io
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch, AsyncMock
from uuid import uuid4

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


# ---------------------------------------------------------------------------
# JWT key pair — reuse pattern from test_auth.py
# ---------------------------------------------------------------------------
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


@pytest.fixture(scope="session", autouse=True)
def jwt_keys(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("jwt_keys_upload")
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
# Helper fixtures
# ---------------------------------------------------------------------------

def _make_mock_db():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.refresh = AsyncMock()
    return mock_db


def _make_free_token() -> str:
    from app.core.security import create_access_token
    return create_access_token(uuid4(), "free")


def _make_paid_token(tier: str = "spark") -> str:
    from app.core.security import create_access_token
    return create_access_token(uuid4(), tier)


@pytest_asyncio.fixture
async def client(jwt_keys):
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Minimal WAV bytes (44-byte PCM header, no audio data — valid enough for format check)
# ---------------------------------------------------------------------------
TINY_WAV = (
    b"RIFF" + (36).to_bytes(4, "little") +
    b"WAVEfmt " + (16).to_bytes(4, "little") +
    (1).to_bytes(2, "little") +   # PCM
    (2).to_bytes(2, "little") +   # channels
    (44100).to_bytes(4, "little") +  # sample rate
    (176400).to_bytes(4, "little") + # byte rate
    (4).to_bytes(2, "little") +   # block align
    (16).to_bytes(2, "little") +  # bits per sample
    b"data" + (0).to_bytes(4, "little")
)


# ---------------------------------------------------------------------------
# Test 1: Free tier upload WAV → 201, input_file_key is None, status == "analyzing"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_free_tier_upload_wav(client, jwt_keys):
    from app.main import app
    from app.core.database import get_db
    from app.models.session import Session as MasteringSession

    free_token = _make_free_token()

    # Build a mock session that db.refresh populates
    mock_session = MagicMock(spec=MasteringSession)
    mock_session.id = uuid4()
    mock_session.status = "analyzing"
    mock_session.tier_at_creation = "free"
    mock_session.input_file_key = None
    mock_session.input_file_hash = "abc123"
    mock_session.input_duration_ms = None
    mock_session.input_lufs = None
    mock_session.input_true_peak = None
    mock_session.output_lufs = None
    mock_session.output_true_peak = None
    mock_session.target_platform = "spotify"
    mock_session.rain_score = None
    mock_session.rain_cert_id = None
    mock_session.error_code = None
    mock_session.created_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    mock_session.completed_at = None

    mock_db = _make_mock_db()

    async def fake_refresh(obj):
        # Copy mock_session attributes onto obj
        for attr in vars(mock_session):
            if not attr.startswith("_"):
                try:
                    setattr(obj, attr, getattr(mock_session, attr))
                except Exception:
                    pass

    mock_db.refresh.side_effect = fake_refresh

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db

    with patch("app.tasks.analysis.analyze_session") as mock_task:
        mock_task.delay = MagicMock()
        resp = await client.post(
            "/api/v1/sessions/",
            files={"file": ("track.wav", io.BytesIO(TINY_WAV), "audio/wav")},
            data={"target_platform": "spotify", "simple_mode": "true"},
            headers={"Authorization": f"Bearer {free_token}"},
        )

    app.dependency_overrides.clear()

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "analyzing"
    # Free tier S3 isolation: verify no S3 upload was attempted
    # (input_file_key is not exposed in SessionResponse — verified via mock_db)
    assert mock_db.add.called
    added_session = mock_db.add.call_args[0][0]
    assert added_session.input_file_key is None, "Free tier must not write to S3"


# ---------------------------------------------------------------------------
# Test 2: Upload unsupported format .xyz → 422 RAIN-E200
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_unsupported_format(client, jwt_keys):
    from app.main import app
    from app.core.database import get_db

    token = _make_free_token()
    mock_db = _make_mock_db()

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    resp = await client.post(
        "/api/v1/sessions/",
        files={"file": ("track.xyz", io.BytesIO(b"garbage"), "application/octet-stream")},
        data={"target_platform": "spotify"},
        headers={"Authorization": f"Bearer {token}"},
    )
    app.dependency_overrides.clear()

    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "RAIN-E200"


# ---------------------------------------------------------------------------
# Test 3: Upload oversized file (>500 MB) → 413 RAIN-E201
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_oversized_file(client, jwt_keys):
    from app.main import app
    from app.core.database import get_db

    token = _make_free_token()
    mock_db = _make_mock_db()

    # 501 MB of zeros
    oversized = b"\x00" * (501 * 1024 * 1024)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    resp = await client.post(
        "/api/v1/sessions/",
        files={"file": ("huge.wav", io.BytesIO(oversized), "audio/wav")},
        data={"target_platform": "spotify"},
        headers={"Authorization": f"Bearer {token}"},
    )
    app.dependency_overrides.clear()

    assert resp.status_code == 413
    assert resp.json()["detail"]["code"] == "RAIN-E201"
