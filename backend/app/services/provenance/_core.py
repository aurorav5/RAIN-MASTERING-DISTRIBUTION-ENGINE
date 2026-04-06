"""
RAIN Provenance Engine — RAIN-CERT Ed25519 + C2PA v2.2

Per RAIN-PLATFORM-SPEC-v1.0:
- RAIN-CERT: Ed25519-signed canonical JSON at each processing step
- C2PA v2.2: Industry-standard Content Provenance (CBOR-encoded manifests)
- EU AI Act Article 50 enforcement: August 2, 2026
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

import structlog

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    PublicFormat,
    NoEncryption,
    load_pem_private_key,
)

logger = structlog.get_logger()

SIGNING_ALG = "Ed25519"

# Module-level cached signing key (loaded once per process)
_signing_key_cache: Ed25519PrivateKey | None = None


def _load_or_generate_signing_key() -> Ed25519PrivateKey:
    """
    Load Ed25519 private key from RAIN_CERT_SIGNING_KEY env var or file path.

    Priority order:
    1. RAIN_CERT_SIGNING_KEY env var — raw PEM string or hex seed
    2. RAIN_CERT_SIGNING_KEY_PATH setting — path to PEM file
    3. Deterministic dev key derived from JWT_SECRET_KEY (development only)

    The deterministic dev key MUST:
    - Use SHA-256 of JWT_SECRET_KEY as the 32-byte Ed25519 seed
    - Log a WARNING that dev key is in use (not for production)
    - Never be used when RAIN_ENV == "production"
    """
    global _signing_key_cache
    if _signing_key_cache is not None:
        return _signing_key_cache

    rain_env = os.environ.get("RAIN_ENV", "development")

    # Priority 1: RAIN_CERT_SIGNING_KEY env var
    env_key = os.environ.get("RAIN_CERT_SIGNING_KEY")
    if env_key:
        env_key_stripped = env_key.strip()
        if env_key_stripped.startswith("-----BEGIN"):
            # PEM string
            private_key = load_pem_private_key(env_key_stripped.encode(), password=None)
            if not isinstance(private_key, Ed25519PrivateKey):
                raise ValueError("RAIN_CERT_SIGNING_KEY PEM is not an Ed25519 key")
            _signing_key_cache = private_key
            logger.info("rain_cert.signing_key_loaded", source="env_var_pem")
            return _signing_key_cache
        else:
            # Treat as hex seed (32 bytes = 64 hex chars)
            seed = bytes.fromhex(env_key_stripped)
            if len(seed) != 32:
                raise ValueError("RAIN_CERT_SIGNING_KEY hex seed must be 32 bytes (64 hex chars)")
            _signing_key_cache = Ed25519PrivateKey.from_private_bytes(seed)
            logger.info("rain_cert.signing_key_loaded", source="env_var_hex_seed")
            return _signing_key_cache

    # Priority 2: RAIN_CERT_SIGNING_KEY_PATH setting
    key_path = os.environ.get("RAIN_CERT_SIGNING_KEY_PATH")
    if not key_path:
        # Also check pydantic settings if available
        try:
            from app.core.config import settings
            key_path = getattr(settings, "RAIN_CERT_SIGNING_KEY_PATH", None)
        except Exception:
            pass

    if key_path and os.path.exists(key_path):
        with open(key_path, "rb") as f:
            pem_data = f.read()
        private_key = load_pem_private_key(pem_data, password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            raise ValueError("Key at RAIN_CERT_SIGNING_KEY_PATH is not an Ed25519 key")
        _signing_key_cache = private_key
        logger.info("rain_cert.signing_key_loaded", source="file", path=key_path)
        return _signing_key_cache

    # Priority 3: Deterministic dev key — NEVER in production
    if rain_env == "production":
        raise RuntimeError(
            "RAIN_CERT_SIGNING_KEY or RAIN_CERT_SIGNING_KEY_PATH must be set in production. "
            "Dev key fallback is not permitted when RAIN_ENV=production."
        )

    logger.warning(
        "rain_cert.dev_key_in_use",
        message="Ed25519 signing key derived from JWT_SECRET_KEY. NOT FOR PRODUCTION USE.",
        rain_env=rain_env,
    )

    jwt_secret = os.environ.get(
        "JWT_SECRET_KEY", "dev-secret-key-do-not-use-in-production"
    )
    seed = hashlib.sha256(jwt_secret.encode("utf-8")).digest()  # 32 bytes
    _signing_key_cache = Ed25519PrivateKey.from_private_bytes(seed)
    logger.info("rain_cert.signing_key_loaded", source="dev_deterministic")
    return _signing_key_cache


def get_public_key_pem() -> str:
    """Return the PEM-encoded Ed25519 public key for the current signing key.
    Used by the RAIN-CERT verification API.
    """
    private_key = _load_or_generate_signing_key()
    public_key: Ed25519PublicKey = private_key.public_key()
    pem_bytes = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    return pem_bytes.decode("utf-8")


@dataclass
class ProvenanceStep:
    """A single step in the RAIN-CERT provenance chain."""
    stage: str
    timestamp: str
    input_hash: str
    output_hash: str
    params_hash: str | None = None
    wasm_hash: str | None = None
    model_version: str | None = None
    duration_ms: float = 0.0


@dataclass
class RainCert:
    """RAIN-CERT: Cryptographic audit trail from upload through delivery."""
    cert_id: str = ""
    session_id: str = ""
    created_at: str = ""
    version: str = "1.0"
    source_hash: str = ""
    output_hash: str = ""
    chain: list[ProvenanceStep] = field(default_factory=list)
    signature: str = ""  # Ed25519 base64url signature
    ai_generated: bool = False
    ai_source: str = ""
    processing_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        """Canonical JSON for signing (sorted keys, no whitespace)."""
        d = self.to_dict()
        d.pop("signature", None)  # Exclude signature from signed payload
        return json.dumps(d, sort_keys=True, separators=(",", ":"))


@dataclass
class C2PAManifest:
    """C2PA v2.2 Content Provenance manifest.

    In production, this would be generated via c2pa-rs (Rust SDK, WASM-compilable).
    This prototype creates the correct JSON schema for embedding.
    CBOR encoding per C2PA v2.2 spec (RFC 7049) is supported via to_cbor().
    """
    claim_generator: str = "RAIN/1.0"
    title: str = ""
    format: str = "audio/wav"
    instance_id: str = ""
    assertions: list[dict[str, Any]] = field(default_factory=list)
    signature_info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json_str(self) -> str:
        """Return JSON string representation of the manifest."""
        return json.dumps(asdict(self), indent=2)

    def to_cbor(self) -> bytes:
        """CBOR-encode the C2PA manifest for embedding in audio files.
        Per C2PA v2.2 spec: manifests are CBOR-encoded (RFC 7049).
        """
        try:
            import cbor2
        except ImportError as exc:
            raise ImportError(
                "cbor2 is required for C2PA CBOR encoding. "
                "Install it with: pip install cbor2>=5.6.0"
            ) from exc
        return cbor2.dumps(asdict(self))


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_bytes_hash(data: bytes) -> str:
    """Compute SHA-256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()


def compute_params_hash(params: dict[str, Any]) -> str:
    """Compute SHA-256 of canonical JSON params."""
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sign_cert(cert: RainCert) -> str:
    """Sign a RAIN-CERT with Ed25519.

    Serializes the canonical JSON of the cert (excluding the signature field),
    signs it with the Ed25519 private key, and returns a base64url-encoded
    signature string.

    Returns:
        base64url-encoded Ed25519 signature (no padding).
    """
    private_key = _load_or_generate_signing_key()
    payload = cert.to_json().encode("utf-8")
    raw_sig: bytes = private_key.sign(payload)
    sig_b64url = base64.urlsafe_b64encode(raw_sig).rstrip(b"=").decode("ascii")
    logger.debug("rain_cert.signed", cert_id=cert.cert_id, alg=SIGNING_ALG)
    return sig_b64url


def verify_cert(cert: RainCert) -> bool:
    """Verify a RAIN-CERT Ed25519 signature.

    Derives the public key from the current signing key, decodes the base64url
    signature stored in cert.signature, and verifies the Ed25519 signature over
    cert.to_json().

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not cert.signature:
        logger.warning("rain_cert.verify_failed", cert_id=cert.cert_id, reason="empty_signature")
        return False

    try:
        private_key = _load_or_generate_signing_key()
        public_key: Ed25519PublicKey = private_key.public_key()

        # Restore padding for urlsafe_b64decode
        padded = cert.signature + "=" * (4 - len(cert.signature) % 4)
        raw_sig = base64.urlsafe_b64decode(padded)

        payload = cert.to_json().encode("utf-8")
        public_key.verify(raw_sig, payload)
        logger.info("rain_cert.verify_ok", cert_id=cert.cert_id, alg=SIGNING_ALG)
        return True
    except Exception as exc:
        logger.warning(
            "rain_cert.verify_failed",
            cert_id=cert.cert_id,
            reason=str(exc),
            alg=SIGNING_ALG,
        )
        return False


def create_rain_cert(
    session_id: str,
    source_file_path: str,
    output_file_path: str,
    processing_params: dict[str, Any] | None = None,
    chain_steps: list[dict[str, Any]] | None = None,
    ai_generated: bool = False,
    ai_source: str = "",
    output_lufs: float | None = None,
    output_true_peak: float | None = None,
) -> RainCert:
    """Create a complete RAIN-CERT for a mastering session.

    Args:
        session_id: UUID of the mastering session
        source_file_path: Path to the original uploaded file
        output_file_path: Path to the mastered output file
        processing_params: ProcessingParams dict used for mastering
        chain_steps: Optional pre-built provenance chain
        ai_generated: Whether the source was AI-generated
        ai_source: AI generation source (e.g., "suno", "udio")
        output_lufs: Measured output LUFS
        output_true_peak: Measured output true peak

    Returns:
        Signed RainCert with Ed25519 base64url signature
    """
    now = datetime.now(timezone.utc).isoformat()

    source_hash = compute_file_hash(source_file_path)
    output_hash = compute_file_hash(output_file_path)
    params_hash = compute_params_hash(processing_params) if processing_params else ""

    cert = RainCert(
        cert_id=str(uuid.uuid4()),
        session_id=session_id,
        created_at=now,
        source_hash=source_hash,
        output_hash=output_hash,
        ai_generated=ai_generated,
        ai_source=ai_source,
        processing_summary={
            "params_hash": params_hash,
            "output_lufs": output_lufs,
            "output_true_peak": output_true_peak,
        },
    )

    # Build chain if not provided
    if chain_steps:
        cert.chain = [ProvenanceStep(**s) for s in chain_steps]
    else:
        cert.chain = [
            ProvenanceStep(
                stage="upload",
                timestamp=now,
                input_hash=source_hash,
                output_hash=source_hash,
            ),
            ProvenanceStep(
                stage="mastering",
                timestamp=now,
                input_hash=source_hash,
                output_hash=output_hash,
                params_hash=params_hash,
            ),
        ]

    # Sign with Ed25519
    cert.signature = sign_cert(cert)

    return cert


def create_c2pa_manifest(
    title: str,
    artist: str,
    format: str,
    rain_cert: RainCert,
    ai_generated: bool = False,
    ai_source: str = "",
    encode_cbor: bool = False,
) -> C2PAManifest | bytes:
    """Create a C2PA v2.2 Content Provenance manifest.

    Per EU AI Act Article 50 (enforcement: August 2, 2026):
    - Machine-readable AI marking in metadata
    - Content provenance chain
    - AI disclosure fields

    Args:
        title: Track title
        artist: Artist name
        format: Audio format string (e.g. "wav", "mp3")
        rain_cert: Signed RainCert to cross-reference
        ai_generated: Whether the source was AI-generated
        ai_source: AI generation source identifier
        encode_cbor: If True, return CBOR-encoded bytes instead of C2PAManifest.
                     Per C2PA v2.2 spec, manifests are CBOR-encoded (RFC 7049).

    Returns:
        C2PAManifest dataclass, or CBOR bytes if encode_cbor=True.
    """
    manifest = C2PAManifest(
        title=title,
        format=f"audio/{format}",
        instance_id=f"urn:uuid:{rain_cert.cert_id}",
    )

    # Creative work assertion
    manifest.assertions.append({
        "label": "stds.schema-org.CreativeWork",
        "data": {
            "@type": "CreativeWork",
            "name": title,
            "author": [{"@type": "Person", "name": artist}],
        },
    })

    # AI training/generation assertion (EU AI Act Art. 50)
    manifest.assertions.append({
        "label": "c2pa.ai_generative_info",
        "data": {
            "ai_generated": ai_generated,
            "ai_tool": ai_source if ai_source else None,
            "ai_processing": True,  # RAIN always AI-processes
            "ai_processing_tool": "RAIN v6.0.0 by ARCOVEL Technologies International",
            "description": "Audio mastered by RAIN AI mastering engine",
        },
    })

    # RAIN-CERT cross-reference
    manifest.assertions.append({
        "label": "rain.cert",
        "data": {
            "cert_id": rain_cert.cert_id,
            "session_id": rain_cert.session_id,
            "source_hash": rain_cert.source_hash,
            "output_hash": rain_cert.output_hash,
            "signature": rain_cert.signature,
        },
    })

    # Signature info
    manifest.signature_info = {
        "alg": SIGNING_ALG,
        "issuer": "ARCOVEL Technologies International",
        "time": rain_cert.created_at,
    }

    if encode_cbor:
        try:
            import cbor2
        except ImportError as exc:
            raise ImportError(
                "cbor2 is required for C2PA CBOR encoding. "
                "Install it with: pip install cbor2>=5.6.0"
            ) from exc
        return cbor2.dumps(asdict(manifest))

    return manifest
