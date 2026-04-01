import jwt
import hashlib
import structlog
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
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


def create_refresh_token(user_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=30)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _JWT_SIGN_KEY, algorithm=_JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError on invalid token. Caller handles RAIN-E100."""
    return jwt.decode(
        token,
        _JWT_VERIFY_KEY,
        algorithms=[_JWT_ALGORITHM],
        options={"require": ["exp", "iat", "sub"]}
    )


def hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(password.encode(), hashed.encode())


def hash_file(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
