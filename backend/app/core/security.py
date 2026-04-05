import jwt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from app.core.config import settings


def _load_private_key():
    path = Path(settings.JWT_PRIVATE_KEY_PATH)
    return serialization.load_pem_private_key(
        path.read_bytes(),
        password=None,
        backend=default_backend()
    )


def _load_public_key():
    path = Path(settings.JWT_PUBLIC_KEY_PATH)
    return serialization.load_pem_public_key(
        path.read_bytes(),
        backend=default_backend()
    )


def create_access_token(user_id: UUID, tier: str, expires_minutes: int = 60) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {
        "sub": str(user_id),
        "tier": tier,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": "rain.arcovel.com",
    }
    private_key = _load_private_key()
    return jwt.encode(payload, private_key, algorithm="RS256")


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
    private_key = _load_private_key()
    token = jwt.encode(payload, private_key, algorithm="RS256")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, family_id, token_hash


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError on invalid token. Caller handles RAIN-E100."""
    public_key = _load_public_key()
    return jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
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
