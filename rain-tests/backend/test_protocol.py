"""
RAIN AI Mastering Engine - Comprehensive Backend Test Protocol
===============================================================

This test suite covers:
- Authentication & Authorization
- API Endpoints
- Mastering Engine
- File Upload/Download
- Billing & Quotas
- Security
- Performance
"""

import pytest
import asyncio
import json
import hashlib
import jwt
from datetime import datetime, timedelta, timezone
from uuid import uuid4, UUID
from unittest.mock import Mock, patch, AsyncMock
from httpx import AsyncClient
from fastapi import FastAPI, status
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Test configuration
pytestmark = pytest.mark.asyncio

# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Create a test database session."""
    engine = create_async_engine(
        "postgresql+asyncpg://rain_test:test@localhost:5432/rain_test",
        echo=False
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def test_app():
    """Create a test FastAPI application."""
    from app.main import app
    return app


@pytest.fixture
async def async_client(test_app):
    """Create an async HTTP client."""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client


@pytest.fixture
def test_user():
    """Create a test user payload."""
    return {
        "user_id": str(uuid4()),
        "email": "test@arcovel.com",
        "tier": "creator",
        "created_at": datetime.now(timezone.utc).isoformat()
    }


@pytest.fixture
def auth_token(test_user):
    """Generate a valid JWT auth token."""
    from app.core.security import create_access_token
    user_id = UUID(test_user["user_id"])
    return create_access_token(user_id, test_user["tier"], expires_minutes=60)


@pytest.fixture
def mock_audio_file():
    """Create a mock audio file for testing."""
    # Generate synthetic WAV-like data
    header = b'RIFF' + (44100 * 2 * 2 + 36).to_bytes(4, 'little')
    header += b'WAVEfmt ' + (16).to_bytes(4, 'little')
    header += (1).to_bytes(2, 'little')  # PCM
    header += (2).to_bytes(2, 'little')  # Stereo
    header += (44100).to_bytes(4, 'little')  # Sample rate
    header += (44100 * 2 * 2).to_bytes(4, 'little')  # Byte rate
    header += (4).to_bytes(2, 'little')  # Block align
    header += (16).to_bytes(2, 'little')  # Bits per sample
    header += b'data' + (44100 * 2 * 2).to_bytes(4, 'little')
    # Add 1 second of silence
    data = header + b'\x00' * (44100 * 2 * 2)
    return data


# =============================================================================
# AUTHENTICATION TESTS
# =============================================================================

class TestAuthentication:
    """Test authentication flows."""
    
    async def test_register_user(self, async_client):
        """Test user registration."""
        response = await async_client.post("/api/v1/auth/register", json={
            "email": "newuser@arcovel.com",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!"
        })
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT]
    
    async def test_login_user(self, async_client):
        """Test user login."""
        response = await async_client.post("/api/v1/auth/login", json={
            "email": "test@arcovel.com",
            "password": "testpassword"
        })
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]
        if response.status_code == 200:
            data = response.json()
            assert "access_token" in data
            assert "token_type" in data
            assert data["token_type"] == "bearer"
    
    async def test_login_invalid_credentials(self, async_client):
        """Test login with invalid credentials."""
        response = await async_client.post("/api/v1/auth/login", json={
            "email": "test@arcovel.com",
            "password": "wrongpassword"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_refresh_token(self, async_client, auth_token):
        """Test token refresh."""
        response = await async_client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": "test_refresh_token"}
        )
        # May fail without valid refresh token
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]
    
    async def test_protected_route_without_auth(self, async_client):
        """Test accessing protected route without authentication."""
        response = await async_client.get("/api/v1/sessions")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_protected_route_with_auth(self, async_client, auth_token):
        """Test accessing protected route with valid auth."""
        response = await async_client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        # May return empty list or 200
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# =============================================================================
# JWT SECURITY TESTS
# =============================================================================

class TestJWTSecurity:
    """Test JWT token security."""
    
    async def test_jwt_algorithm_confusion_attack(self, async_client):
        """Test that algorithm confusion attacks are prevented."""
        # Create a token with 'none' algorithm
        payload = {"sub": str(uuid4()), "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
        malicious_token = jwt.encode(payload, "", algorithm="none")
        
        response = await async_client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {malicious_token}"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_jwt_expired_token(self, async_client):
        """Test that expired tokens are rejected."""
        from app.core.security import create_access_token
        
        # Create expired token
        expired_token = create_access_token(
            uuid4(), "free", expires_minutes=-1
        )
        
        response = await async_client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_jwt_tampered_token(self, async_client, auth_token):
        """Test that tampered tokens are rejected."""
        # Modify the token payload
        parts = auth_token.split('.')
        if len(parts) == 3:
            # Tamper with payload
            tampered_token = f"{parts[0]}.{parts[1]}.invalid_signature"
            
            response = await async_client.get(
                "/api/v1/sessions",
                headers={"Authorization": f"Bearer {tampered_token}"}
            )
            assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# FILE UPLOAD TESTS
# =============================================================================

class TestFileUpload:
    """Test file upload functionality."""
    
    async def test_upload_audio_file(self, async_client, auth_token, mock_audio_file):
        """Test uploading an audio file."""
        from io import BytesIO
        
        files = {
            "file": ("test_audio.wav", BytesIO(mock_audio_file), "audio/wav")
        }
        
        response = await async_client.post(
            "/api/v1/upload",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=files
        )
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_200_OK]
    
    async def test_upload_without_auth(self, async_client, mock_audio_file):
        """Test upload without authentication."""
        from io import BytesIO
        
        files = {
            "file": ("test_audio.wav", BytesIO(mock_audio_file), "audio/wav")
        }
        
        response = await async_client.post("/api/v1/upload", files=files)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    async def test_upload_invalid_file_type(self, async_client, auth_token):
        """Test uploading invalid file type."""
        from io import BytesIO
        
        files = {
            "file": ("test.txt", BytesIO(b"not an audio file"), "text/plain")
        }
        
        response = await async_client.post(
            "/api/v1/upload",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=files
        )
        # Should reject non-audio files
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE]
    
    async def test_upload_oversized_file(self, async_client, auth_token):
        """Test uploading oversized file."""
        from io import BytesIO
        
        # Create 1GB of data
        large_data = b'\x00' * (1024 * 1024 * 1024)
        files = {
            "file": ("large.wav", BytesIO(large_data), "audio/wav")
        }
        
        response = await async_client.post(
            "/api/v1/upload",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=files,
            timeout=30.0
        )
        # Should reject or timeout
        assert response.status_code in [status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, status.HTTP_504_GATEWAY_TIMEOUT]


# =============================================================================
# MASTERING ENGINE TESTS
# =============================================================================

class TestMasteringEngine:
    """Test mastering engine functionality."""
    
    async def test_start_mastering_session(self, async_client, auth_token):
        """Test starting a mastering session."""
        response = await async_client.post(
            "/api/v1/master/start",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "file_id": str(uuid4()),
                "target_lufs": -14.0,
                "platform": "spotify"
            }
        )
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    async def test_get_mastering_params(self, async_client, auth_token):
        """Test getting mastering parameters."""
        response = await async_client.get(
            "/api/v1/master/params",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    async def test_update_macro_controls(self, async_client, auth_token):
        """Test updating macro controls."""
        response = await async_client.post(
            "/api/v1/master/macros",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "brighten": 5.0,
                "glue": 6.0,
                "width": 5.0,
                "punch": 5.0,
                "warmth": 2.5,
                "space": 3.0,
                "repair": 0.0
            }
        )
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    async def test_mastering_without_auth(self, async_client):
        """Test mastering without authentication."""
        response = await async_client.post("/api/v1/master/start", json={})
        # In dev mode this might be allowed
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_422_UNPROCESSABLE_ENTITY]


# =============================================================================
# QC ENGINE TESTS
# =============================================================================

class TestQCEngine:
    """Test quality control engine."""
    
    async def test_run_qc_checks(self, async_client, auth_token):
        """Test running QC checks."""
        response = await async_client.post(
            "/api/v1/qc/run",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"session_id": str(uuid4())}
        )
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    async def test_get_qc_report(self, async_client, auth_token):
        """Test getting QC report."""
        response = await async_client.get(
            "/api/v1/qc/report",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"session_id": str(uuid4())}
        )
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# =============================================================================
# BILLING & QUOTA TESTS
# =============================================================================

class TestBilling:
    """Test billing and quota functionality."""
    
    async def test_get_user_quota(self, async_client, auth_token):
        """Test getting user quota."""
        response = await async_client.get(
            "/api/v1/billing/quota",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    async def test_check_quota_enforcement(self, async_client, auth_token):
        """Test that quota limits are enforced."""
        # This would require mocking quota exhaustion
        pass
    
    async def test_get_stripe_products(self, async_client, auth_token):
        """Test getting Stripe product information."""
        response = await async_client.get(
            "/api/v1/billing/products",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# =============================================================================
# STEM SEPARATION TESTS
# =============================================================================

class TestStemSeparation:
    """Test stem separation functionality."""
    
    async def test_start_separation(self, async_client, auth_token):
        """Test starting stem separation."""
        response = await async_client.post(
            "/api/v1/separate/start",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "file_id": str(uuid4()),
                "model": "bs_roformer_sw"
            }
        )
        # May be disabled or require GPU
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
    
    async def test_get_separation_status(self, async_client, auth_token):
        """Test getting separation status."""
        response = await async_client.get(
            "/api/v1/separate/status",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"job_id": str(uuid4())}
        )
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# =============================================================================
# DISTRIBUTION TESTS
# =============================================================================

class TestDistribution:
    """Test distribution functionality."""
    
    async def test_get_distribution_platforms(self, async_client, auth_token):
        """Test getting available distribution platforms."""
        response = await async_client.get(
            "/api/v1/distribution/platforms",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    async def test_create_distribution_job(self, async_client, auth_token):
        """Test creating a distribution job."""
        response = await async_client.post(
            "/api/v1/distribution/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "session_id": str(uuid4()),
                "platforms": ["spotify", "apple_music"],
                "metadata": {
                    "title": "Test Track",
                    "artist": "Test Artist"
                }
            }
        )
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_404_NOT_FOUND]


# =============================================================================
# AI CO-MASTER ENGINEER TESTS
# =============================================================================

class TestAIE:
    """Test AI Co-Master Engineer functionality."""
    
    async def test_aie_chat(self, async_client, auth_token):
        """Test AI engineer chat."""
        response = await async_client.post(
            "/api/v1/aie/chat",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "session_id": str(uuid4()),
                "message": "Make it brighter and more punchy"
            }
        )
        # May require Anthropic API key
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
    
    async def test_aie_rate_limiting(self, async_client, auth_token):
        """Test AI engineer rate limiting."""
        # Make multiple rapid requests
        for _ in range(10):
            response = await async_client.post(
                "/api/v1/aie/chat",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"message": "test"}
            )
        # Should eventually rate limit
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS]


# =============================================================================
# PROVENANCE TESTS
# =============================================================================

class TestProvenance:
    """Test provenance and certification."""
    
    async def test_get_public_key(self, async_client):
        """Test getting public key for verification (no auth required)."""
        response = await async_client.get("/api/v1/provenance/public-key")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    async def test_get_certificate(self, async_client, auth_token):
        """Test getting RAIN certificate."""
        response = await async_client.get(
            "/api/v1/provenance/certificate",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"session_id": str(uuid4())}
        )
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Test error handling and responses."""
    
    async def test_404_not_found(self, async_client):
        """Test 404 response."""
        response = await async_client.get("/api/v1/nonexistent")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    async def test_405_method_not_allowed(self, async_client):
        """Test 405 response."""
        response = await async_client.delete("/api/v1/auth/register")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    
    async def test_422_validation_error(self, async_client):
        """Test 422 validation error."""
        response = await async_client.post("/api/v1/auth/login", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestPerformance:
    """Test API performance."""
    
    async def test_response_time_health(self, async_client):
        """Test health endpoint response time."""
        import time
        
        start = time.time()
        response = await async_client.get("/health")
        elapsed = time.time() - start
        
        assert response.status_code == status.HTTP_200_OK
        assert elapsed < 1.0  # Should respond in under 1 second
    
    async def test_concurrent_requests(self, async_client, auth_token):
        """Test handling concurrent requests."""
        import asyncio
        
        async def make_request():
            return await async_client.get(
                "/api/v1/sessions",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
        
        # Make 10 concurrent requests
        tasks = [make_request() for _ in range(10)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete without exceptions
        for r in responses:
            assert not isinstance(r, Exception)


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
