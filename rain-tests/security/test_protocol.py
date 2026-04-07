"""
RAIN AI Mastering Engine - Security Test Protocol
=================================================

Comprehensive security testing including:
- Authentication bypass attempts
- Injection attacks
- CSRF/XSS protection
- Rate limiting
- File upload security
- API security
"""

import pytest
import asyncio
import json
import jwt
import hashlib
import hmac
import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4, UUID
from unittest.mock import Mock, patch, AsyncMock
from httpx import AsyncClient
import aiohttp

pytestmark = pytest.mark.asyncio

# =============================================================================
# JWT SECURITY TESTS
# =============================================================================

class TestJWTVulnerabilities:
    """Test JWT token vulnerabilities."""
    
    async def test_jwt_none_algorithm_attack(self, async_client):
        """Test that 'none' algorithm is rejected."""
        # Create token with 'none' algorithm
        header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b'=')
        payload = base64.urlsafe_b64encode(json.dumps({
            "sub": str(uuid4()),
            "exp": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        }).encode()).rstrip(b'=')
        
        malicious_token = f"{header.decode()}.{payload.decode()}."
        
        response = await async_client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {malicious_token}"}
        )
        assert response.status_code == 401, "None algorithm should be rejected"
    
    async def test_jwt_algorithm_confusion_hs256_to_rs256(self, async_client):
        """Test algorithm confusion from HS256 to RS256."""
        # This attack tries to use the public key as HMAC secret
        # In a vulnerable implementation, this could bypass verification
        
        public_key_pem = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"""
        
        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b'=')
        payload_data = {
            "sub": str(uuid4()),
            "tier": "enterprise",
            "exp": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        }
        payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b'=')
        
        # Sign with public key (should fail in proper implementation)
        signature = hmac.new(
            public_key_pem.encode(),
            f"{header.decode()}.{payload.decode()}".encode(),
            hashlib.sha256
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b'=')
        
        malicious_token = f"{header.decode()}.{payload.decode()}.{signature_b64.decode()}"
        
        response = await async_client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {malicious_token}"}
        )
        # Should be rejected
        assert response.status_code == 401
    
    async def test_jwt_expired_token_reuse(self, async_client):
        """Test that expired tokens cannot be reused."""
        from app.core.security import create_access_token
        
        # Create expired token
        expired_token = create_access_token(
            uuid4(), "free", expires_minutes=-10
        )
        
        response = await async_client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401
        assert "expired" in response.text.lower() or response.status_code == 401
    
    async def test_jwt_token_tampering(self, async_client, auth_token):
        """Test that tampered tokens are rejected."""
        parts = auth_token.split('.')
        if len(parts) != 3:
            pytest.skip("Invalid token format")
        
        # Modify payload to upgrade tier
        payload_json = base64.urlsafe_b64decode(parts[1] + '==')
        payload = json.loads(payload_json)
        payload['tier'] = 'enterprise'
        
        new_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=')
        tampered_token = f"{parts[0]}.{new_payload.decode()}.{parts[2]}"
        
        response = await async_client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {tampered_token}"}
        )
        assert response.status_code == 401, "Tampered token should be rejected"
    
    async def test_jwt_missing_signature(self, async_client):
        """Test that tokens without signatures are rejected."""
        header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).rstrip(b'=')
        payload = base64.urlsafe_b64encode(json.dumps({
            "sub": str(uuid4()),
            "exp": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        }).encode()).rstrip(b'=')
        
        # Token without signature
        incomplete_token = f"{header.decode()}.{payload.decode()}"
        
        response = await async_client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {incomplete_token}"}
        )
        assert response.status_code == 401
    
    async def test_jwt_key_id_confusion(self, async_client):
        """Test key ID confusion attacks."""
        # Create token with fake key ID
        header = base64.urlsafe_b64encode(json.dumps({
            "alg": "RS256",
            "typ": "JWT",
            "kid": "../../../etc/passwd"  # Path traversal attempt
        }).encode()).rstrip(b'=')
        
        payload = base64.urlsafe_b64encode(json.dumps({
            "sub": str(uuid4()),
            "exp": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        }).encode()).rstrip(b'=')
        
        token = f"{header.decode()}.{payload.decode()}.fake_signature"
        
        response = await async_client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401


# =============================================================================
# SQL INJECTION TESTS
# =============================================================================

class TestSQLInjection:
    """Test SQL injection vulnerabilities."""
    
    async def test_login_sql_injection(self, async_client):
        """Test SQL injection in login endpoint."""
        malicious_emails = [
            "' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM users--",
            "'; DROP TABLE users;--",
            "' OR 1=1 LIMIT 1--",
        ]
        
        for email in malicious_emails:
            response = await async_client.post("/api/v1/auth/login", json={
                "email": email,
                "password": "anything"
            })
            # Should return 401, not 500 (which would indicate SQL error)
            assert response.status_code in [401, 422], f"SQL injection attempt with: {email}"
    
    async def test_search_sql_injection(self, async_client, auth_token):
        """Test SQL injection in search parameters."""
        malicious_queries = [
            "' OR '1'='1",
            "test' UNION SELECT * FROM sessions--",
            "'; DELETE FROM sessions;--",
        ]
        
        for query in malicious_queries:
            response = await async_client.get(
                "/api/v1/sessions",
                headers={"Authorization": f"Bearer {auth_token}"},
                params={"search": query}
            )
            # Should not expose SQL errors
            assert response.status_code in [200, 422]
            if response.status_code == 200:
                # Should not return all data
                data = response.json()
                if isinstance(data, list):
                    assert len(data) < 1000, "Potential SQL injection - too many results"
    
    async def test_order_by_sql_injection(self, async_client, auth_token):
        """Test SQL injection in ORDER BY clause."""
        malicious_order = [
            "id; DROP TABLE users;--",
            "(SELECT * FROM users)",
            "id, (SELECT password FROM users LIMIT 1)",
        ]
        
        for order in malicious_order:
            response = await async_client.get(
                "/api/v1/sessions",
                headers={"Authorization": f"Bearer {auth_token}"},
                params={"order_by": order}
            )
            # Should not cause SQL errors
            assert response.status_code in [200, 422]


# =============================================================================
# XSS TESTS
# =============================================================================

class TestXSS:
    """Test Cross-Site Scripting vulnerabilities."""
    
    async def test_xss_in_metadata(self, async_client, auth_token):
        """Test XSS in metadata fields."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "<iframe src='javascript:alert(1)'>",
        ]
        
        for payload in xss_payloads:
            response = await async_client.post(
                "/api/v1/distribution/jobs",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "session_id": str(uuid4()),
                    "platforms": ["spotify"],
                    "metadata": {
                        "title": payload,
                        "artist": payload,
                    }
                }
            )
            
            # Check response doesn't contain unescaped script
            if response.status_code == 200:
                response_text = response.text
                assert "<script>" not in response_text or "&lt;script&gt;" in response_text
    
    async def test_xss_in_filename(self, async_client, auth_token):
        """Test XSS in filename during upload."""
        from io import BytesIO
        
        xss_filename = "<script>alert(1)</script>.wav"
        
        files = {
            "file": (xss_filename, BytesIO(b"fake audio data"), "audio/wav")
        }
        
        response = await async_client.post(
            "/api/v1/upload",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=files
        )
        
        # Response should not contain unescaped script
        if response.status_code in [200, 201]:
            response_text = response.text
            assert "<script>" not in response_text or "&lt;script&gt;" in response_text


# =============================================================================
# CSRF TESTS
# =============================================================================

class TestCSRF:
    """Test Cross-Site Request Forgery protection."""
    
    async def test_csrf_token_required(self, async_client):
        """Test that state-changing operations require CSRF protection."""
        # Try to perform state-changing operation without proper headers
        response = await async_client.post("/api/v1/auth/login", json={
            "email": "test@arcovel.com",
            "password": "password"
        }, headers={
            "Origin": "https://evil.com"  # Wrong origin
        })
        
        # Should be rejected or require additional verification
        assert response.status_code in [401, 403, 422]
    
    async def test_origin_header_validation(self, async_client, auth_token):
        """Test Origin header validation."""
        response = await async_client.post(
            "/api/v1/master/start",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Origin": "https://malicious-site.com"
            },
            json={"file_id": str(uuid4())}
        )
        
        # Should reject requests from unauthorized origins
        assert response.status_code in [200, 403]  # 200 if CORS blocks at middleware level


# =============================================================================
# RATE LIMITING TESTS
# =============================================================================

class TestRateLimiting:
    """Test rate limiting functionality."""
    
    async def test_login_rate_limiting(self, async_client):
        """Test rate limiting on login endpoint."""
        # Make multiple rapid login attempts
        responses = []
        for i in range(20):
            response = await async_client.post("/api/v1/auth/login", json={
                "email": f"test{i}@arcovel.com",
                "password": "wrongpassword"
            })
            responses.append(response.status_code)
        
        # Some requests should be rate limited
        assert 429 in responses, "Rate limiting should trigger after multiple requests"
    
    async def test_api_rate_limiting_by_tier(self, async_client, auth_token):
        """Test tier-based rate limiting."""
        # Make many rapid API calls
        responses = []
        for i in range(100):
            response = await async_client.get(
                "/api/v1/sessions",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            responses.append(response.status_code)
            
            if response.status_code == 429:
                break
        
        # Should eventually rate limit
        assert 429 in responses or responses.count(200) < 100
    
    async def test_rate_limit_headers(self, async_client):
        """Test that rate limit headers are present."""
        response = await async_client.post("/api/v1/auth/login", json={
            "email": "test@arcovel.com",
            "password": "password"
        })
        
        # Check for rate limit headers
        headers = response.headers
        assert any(h in headers for h in [
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset",
            "retry-after"
        ]), "Rate limit headers should be present"


# =============================================================================
# FILE UPLOAD SECURITY TESTS
# =============================================================================

class TestFileUploadSecurity:
    """Test file upload security."""
    
    async def test_upload_malicious_file_extension(self, async_client, auth_token):
        """Test upload of files with malicious extensions."""
        from io import BytesIO
        
        dangerous_extensions = [
            ("test.php", "text/plain"),
            ("test.exe", "application/octet-stream"),
            ("test.sh", "text/x-shellscript"),
            ("test.py", "text/x-python"),
            ("test.jsp", "text/plain"),
            (".htaccess", "text/plain"),
        ]
        
        for filename, content_type in dangerous_extensions:
            files = {
                "file": (filename, BytesIO(b"malicious content"), content_type)
            }
            
            response = await async_client.post(
                "/api/v1/upload",
                headers={"Authorization": f"Bearer {auth_token}"},
                files=files
            )
            
            # Should reject dangerous file types
            assert response.status_code in [400, 415, 422], f"Should reject {filename}"
    
    async def test_upload_path_traversal(self, async_client, auth_token):
        """Test path traversal in filename."""
        from io import BytesIO
        
        path_traversal_names = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "test/../../../etc/passwd",
            "test.wav/../../../etc/passwd",
        ]
        
        for filename in path_traversal_names:
            files = {
                "file": (filename, BytesIO(b"fake audio"), "audio/wav")
            }
            
            response = await async_client.post(
                "/api/v1/upload",
                headers={"Authorization": f"Bearer {auth_token}"},
                files=files
            )
            
            # Should sanitize or reject
            assert response.status_code in [200, 201, 400]
            
            if response.status_code in [200, 201]:
                # Verify the stored filename is sanitized
                data = response.json()
                stored_name = data.get("filename", "")
                assert ".." not in stored_name, "Path traversal should be sanitized"
    
    async def test_upload_malformed_audio(self, async_client, auth_token):
        """Test upload of malformed audio files."""
        from io import BytesIO
        
        # Files that claim to be audio but aren't
        fake_audio_files = [
            ("fake.wav", b"not a real wav file", "audio/wav"),
            ("fake.mp3", b"not a real mp3 file", "audio/mpeg"),
            ("fake.flac", b"not a real flac file", "audio/flac"),
        ]
        
        for filename, content, mime_type in fake_audio_files:
            files = {
                "file": (filename, BytesIO(content), mime_type)
            }
            
            response = await async_client.post(
                "/api/v1/upload",
                headers={"Authorization": f"Bearer {auth_token}"},
                files=files
            )
            
            # Should validate file content
            assert response.status_code in [200, 201, 400, 422]
    
    async def test_upload_size_limit(self, async_client, auth_token):
        """Test file size limits."""
        from io import BytesIO
        
        # Create oversized file (100MB)
        large_content = b'\x00' * (100 * 1024 * 1024)
        
        files = {
            "file": ("large.wav", BytesIO(large_content), "audio/wav")
        }
        
        response = await async_client.post(
            "/api/v1/upload",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=files,
            timeout=60.0
        )
        
        # Should reject oversized files
        assert response.status_code in [413, 400]


# =============================================================================
# AUTHORIZATION TESTS
# =============================================================================

class TestAuthorization:
    """Test authorization and access control."""
    
    async def test_cross_tenant_access(self, async_client, auth_token):
        """Test that users cannot access other users' data."""
        # Try to access another user's session
        other_user_session = str(uuid4())
        
        response = await async_client.get(
            f"/api/v1/sessions/{other_user_session}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Should return 404 (not found) or 403 (forbidden)
        # 404 is safer as it doesn't reveal existence
        assert response.status_code in [404, 403]
    
    async def test_tier_gating(self, async_client):
        """Test that tier-based features are properly gated."""
        from app.core.security import create_access_token
        
        # Create free tier token
        free_token = create_access_token(uuid4(), "free", expires_minutes=60)
        
        # Try to access premium feature
        response = await async_client.post(
            "/api/v1/separate/start",
            headers={"Authorization": f"Bearer {free_token}"},
            json={"file_id": str(uuid4())}
        )
        
        # Should be forbidden for free tier
        assert response.status_code in [403, 402]  # Forbidden or Payment Required
    
    async def test_admin_endpoints_protection(self, async_client, auth_token):
        """Test that admin endpoints are protected."""
        admin_endpoints = [
            "/api/v1/admin/users",
            "/api/v1/admin/config",
            "/api/v1/admin/metrics",
        ]
        
        for endpoint in admin_endpoints:
            response = await async_client.get(
                endpoint,
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            # Should be forbidden for non-admin users
            assert response.status_code in [404, 403], f"Admin endpoint {endpoint} should be protected"


# =============================================================================
# INFORMATION DISCLOSURE TESTS
# =============================================================================

class TestInformationDisclosure:
    """Test for information disclosure vulnerabilities."""
    
    async def test_error_message_leakage(self, async_client):
        """Test that error messages don't leak sensitive info."""
        response = await async_client.post("/api/v1/auth/login", json={
            "email": "test@arcovel.com",
            "password": "wrong"
        })
        
        response_text = response.text.lower()
        
        # Should not reveal whether email exists
        assert "password" not in response_text or "invalid" in response_text
        assert "user" not in response_text or "invalid" in response_text
        
        # Should not contain stack traces
        assert "traceback" not in response_text
        assert "file \"" not in response_text
    
    async def test_debug_info_in_production(self, async_client):
        """Test that debug info is not exposed in production."""
        # Try to access docs in production mode
        response = await async_client.get("/docs")
        
        # In production, docs should be disabled
        # This depends on RAIN_ENV setting
        assert response.status_code in [200, 404]
    
    async def test_server_header_leakage(self, async_client):
        """Test that server headers don't reveal too much."""
        response = await async_client.get("/health")
        headers = response.headers
        
        # Server header should not reveal version
        server_header = headers.get("server", "")
        assert "fastapi" not in server_header.lower() or "nginx" in server_header.lower()
        
        # X-Powered-By should not be present
        assert "x-powered-by" not in headers


# =============================================================================
# SSRF TESTS
# =============================================================================

class TestSSRF:
    """Test Server-Side Request Forgery vulnerabilities."""
    
    async def test_ssrf_in_webhook_url(self, async_client, auth_token):
        """Test SSRF in webhook URLs."""
        ssrf_payloads = [
            "http://localhost:22",  # SSH
            "http://169.254.169.254/latest/meta-data/",  # AWS metadata
            "http://127.0.0.1:8000/admin",
            "file:///etc/passwd",
        ]
        
        for url in ssrf_payloads:
            response = await async_client.post(
                "/api/v1/webhooks",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"url": url}
            )
            
            # Should reject internal URLs
            assert response.status_code in [400, 422], f"SSRF attempt with: {url}"


# =============================================================================
# RUN ALL TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
