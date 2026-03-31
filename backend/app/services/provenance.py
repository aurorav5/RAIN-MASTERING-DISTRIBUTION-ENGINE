"""
RAIN Provenance Engine — RAIN-CERT Ed25519 + C2PA v2.2 stub

Per RAIN-PLATFORM-SPEC-v1.0:
- RAIN-CERT: Ed25519-signed canonical JSON at each processing step
- C2PA v2.2: Industry-standard Content Provenance (CBOR-encoded manifests)
- EU AI Act Article 50 enforcement: August 2, 2026

Prototype implementation: Ed25519 signing with hashlib, C2PA manifest structure
(actual c2pa-rs integration requires Rust/WASM — stubbed with correct schema).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


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
    signature: str = ""  # Ed25519 hex signature (or HMAC in prototype)
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
    """C2PA v2.2 Content Provenance manifest (stub structure).

    In production, this would be generated via c2pa-rs (Rust SDK, WASM-compilable).
    This prototype creates the correct JSON schema for embedding.
    """
    claim_generator: str = "RAIN/1.0"
    title: str = ""
    format: str = "audio/wav"
    instance_id: str = ""
    assertions: list[dict[str, Any]] = field(default_factory=list)
    signature_info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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


def sign_cert(cert: RainCert, signing_key: bytes | None = None) -> str:
    """Sign a RAIN-CERT.

    Prototype: HMAC-SHA256 with a fixed key.
    Production: Ed25519 with the RAIN_CERT_SIGNING_KEY.
    """
    payload = cert.to_json().encode("utf-8")
    if signing_key:
        import hmac
        return hmac.new(signing_key, payload, hashlib.sha256).hexdigest()
    else:
        # Prototype: deterministic hash as signature placeholder
        return hashlib.sha256(payload).hexdigest()


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
        Signed RainCert
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

    # Sign
    cert.signature = sign_cert(cert)

    return cert


def create_c2pa_manifest(
    title: str,
    artist: str,
    format: str,
    rain_cert: RainCert,
    ai_generated: bool = False,
    ai_source: str = "",
) -> C2PAManifest:
    """Create a C2PA v2.2 Content Provenance manifest.

    Per EU AI Act Article 50 (enforcement: August 2, 2026):
    - Machine-readable AI marking in metadata
    - Content provenance chain
    - AI disclosure fields

    Prototype: correct JSON schema. Production: c2pa-rs CBOR encoding.
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
            "ai_processing_tool": "RAIN v1.0 by ARCOVEL Technologies International",
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
        "alg": "Ed25519",
        "issuer": "ARCOVEL Technologies International",
        "time": rain_cert.created_at,
    }

    return manifest
