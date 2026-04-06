import jwt
import hashlib
import secrets
import structlog
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4
from app.core.config import settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# JWT key resolution: RS256 (production) with HS256 dev-mode fallback
# ---------------------------------------------------------------------------

_USE_HMAC = False  # Set True if RSA keys are unavailable


def _resolve_jwt_mode() -> tuple[str, object, object]:
    """Resolve JWT algorithm and keys. Returns (algorithm, signing_key, verify_key).

    In production (RS256): loads RSA private/public keys from disk.
    In dev mode (HS256): falls back to JWT_SECRET_KEY when key files are missing.
    """
    global _USE_HMAC

    priv_path = Path(getattr(settings, "JWT_PRIVATE_KEY_PATH", "/etc/rain/jwt.key"))
    pub_path = Path(getattr(settings, "JWT_PUBLIC_KEY_PATH", "/etc/rain/jwt.pub"))

    if priv_path.exists() and pub_path.exists():
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend
            priv_key = serialization.load_pem_private_key(
                priv_path.read_bytes(), password=None, backend=default_backend()
            )
            pub_key = serialization.load_pem_public_key(
                pub_path.read_bytes(), backend=default_backend()
            )
            _USE_HMAC = False
            return "RS256", priv_key, pub_key
        except Exception as e:
            logger.warning("jwt_rsa_key_load_failed", error=str(e))

    # Dev-mode fallback: HS256 with JWT_SECRET_KEY
    if settings.RAIN_ENV == "production":
        raise RuntimeError(
            "RS256 key files not found and RAIN_ENV=production. "
            "JWT_PRIVATE_KEY_PATH and JWT_PUBLIC_KEY_PATH must point to valid RSA keys."
        )

    _USE_HMAC = True
    secret = settings.JWT_SECRET_KEY
    logger.warning("jwt_using_hmac_fallback", note="HS256 dev-mode — not for production")
    return "HS256", secret, secret


_JWT_ALGORITHM, _JWT_SIGN_KEY, _JWT_VERIFY_KEY = _resolve_jwt_mode()


def create_access_token(user_id: UUID, tier: str, expires_minutes: int = 60) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {
        "sub": str(user_id),
        "tier": tier,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": "rain.arcovel.com",
    }
    return jwt.encode(payload, _JWT_SIGN_KEY, algorithm=_JWT_ALGORITHM)


def create_refresh_token(user_id: UUID, family_id: Optional[UUID] = None) -> tuple[str, UUID, str]:
    """
    Issue a refresh token. Returns (token, family_id, token_hash).
    family_id links a rotation chain — reuse of a rotated token revokes the entire family
    (theft detection). Caller must persist (family_id, token_hash) in refresh_token_families.
    """
    if family_id is None:
        family_id = uuid4()
    jti = secrets.token_urlsafe(32)
    expire = datetime.now(timezone.utc) + timedelta(days=30)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "fam": str(family_id),
        "jti": jti,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, _JWT_SIGN_KEY, algorithm=_JWT_ALGORITHM)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, family_id, token_hash


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError on invalid token. Caller handles RAIN-E100."""
    return jwt.decode(
        token,
        _JWT_VERIFY_KEY,
        algorithms=[_JWT_ALGORITHM],
        options={"require": ["exp", "iat", "sub"]}
    )


def decode_refresh_token(token: str) -> dict:
    """Decode refresh token and verify type claim."""
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("not a refresh token")
    if "fam" not in payload or "jti" not in payload:
        raise jwt.InvalidTokenError("missing family or jti claim")
    return payload


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(password.encode(), hashed.encode())


def hash_file(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
