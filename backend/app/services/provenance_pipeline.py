"""Provenance pipeline — create, sign, verify, and enforce RAIN-CERT.

Wired into the render pipeline SYNCHRONOUSLY before session is marked "complete".
Every master that exits the pipeline must have a signed cert. No exceptions.
"""
from __future__ import annotations

import json
import time as _time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog

from app.services.provenance import (
    compute_bytes_hash,
    compute_params_hash,
    sign_cert as _legacy_sign,
    verify_cert as _legacy_verify,
    get_public_key_pem,
    RainCert as LegacyRainCert,
    ProvenanceStep as LegacyProvenanceStep,
)
from app.services.provenance_models import StrictRainCert, ProvenanceStep

logger = structlog.get_logger()


def create_rain_cert(
    session_id: str,
    input_hash: str,
    output_hash: str,
    output_audio: bytes,
    processing_params: dict[str, Any],
    wasm_binary_hash: str = "",
    model_version: str = "heuristic",
    ai_generated: bool = False,
    ai_source: str = "",
    duration_ms: float = 0.0,
) -> StrictRainCert:
    """Create a RAIN-CERT for a completed mastering session.

    Validates all inputs strictly (Pydantic). Computes output hash from the
    actual audio bytes and verifies it matches the declared output_hash.
    Raises ValueError (RAIN-E305) on hash mismatch.

    Returns an UNSIGNED cert — call sign_and_verify() next.
    """
    now = datetime.now(timezone.utc)

    # Recompute output hash from actual bytes — enforcement gate
    actual_hash = compute_bytes_hash(output_audio)
    if actual_hash != output_hash:
        logger.error(
            "provenance_hash_mismatch",
            session_id=session_id,
            declared=output_hash[:16],
            actual=actual_hash[:16],
            error_code="RAIN-E305",
        )
        raise ValueError(
            f"RAIN-E305: output hash mismatch — provenance chain broken. "
            f"Declared {output_hash[:16]}... != actual {actual_hash[:16]}..."
        )

    params_hash = compute_params_hash(processing_params)

    step = ProvenanceStep(
        stage="mastering",
        timestamp=now,
        input_hash=input_hash,
        output_hash=output_hash,
        params_hash=params_hash,
        wasm_hash=wasm_binary_hash or None,
        model_version=model_version or None,
        duration_ms=duration_ms,
    )

    cert = StrictRainCert(
        cert_id=uuid4(),
        session_id=UUID(session_id),
        created_at=now,
        source_hash=input_hash,
        output_hash=output_hash,
        chain=[step],
        ai_generated=ai_generated,
        ai_source=ai_source or "",
        processing_summary={
            "target_lufs": processing_params.get("target_lufs"),
            "platform": processing_params.get("target_platform", "unknown"),
            "model_version": model_version,
        },
    )

    logger.info(
        "rain_cert_created",
        cert_id=str(cert.cert_id),
        session_id=session_id,
        output_hash=output_hash[:16],
    )
    return cert


def sign_and_verify(cert: StrictRainCert, user_id: str = "") -> StrictRainCert:
    """Sign a RAIN-CERT with Ed25519 and verify the signature immediately.

    Mutates cert.signature. Raises if verification fails.
    """
    t0 = _time.monotonic()
    # Convert to legacy format for signing (reuses provenance.py's Ed25519 logic)
    legacy = LegacyRainCert(
        cert_id=str(cert.cert_id),
        session_id=str(cert.session_id),
        created_at=cert.created_at.isoformat(),
        version=cert.version,
        source_hash=cert.source_hash,
        output_hash=cert.output_hash,
        chain=[
            LegacyProvenanceStep(
                stage=s.stage,
                timestamp=s.timestamp.isoformat(),
                input_hash=s.input_hash,
                output_hash=s.output_hash,
                params_hash=s.params_hash,
                wasm_hash=s.wasm_hash,
                model_version=s.model_version,
                duration_ms=s.duration_ms,
            )
            for s in cert.chain
        ],
        ai_generated=cert.ai_generated,
        ai_source=cert.ai_source,
        processing_summary=cert.processing_summary,
    )

    signature = _legacy_sign(legacy)
    cert.signature = signature

    # Immediate verify — catch signing failures before they persist
    legacy.signature = signature
    if not _legacy_verify(legacy):
        logger.error(
            "rain_cert_verify_failed_after_sign",
            cert_id=str(cert.cert_id),
            error_code="RAIN-E306",
        )
        raise ValueError(
            f"RAIN-E306: cert {cert.cert_id} signature verification failed immediately after signing"
        )

    cert.assert_signed()
    duration_ms = int((_time.monotonic() - t0) * 1000)
    logger.info(
        "rain_cert_signed_verified",
        cert_id=str(cert.cert_id),
        session_id=str(cert.session_id),
        user_id=user_id,
        stage="provenance",
        duration_ms=duration_ms,
    )
    return cert


def cert_to_json(cert: StrictRainCert) -> str:
    """Serialize cert to JSON for storage in PostgreSQL JSONB."""
    return cert.model_dump_json()


def cert_to_dict(cert: StrictRainCert) -> dict:
    """Serialize cert to dict for storage in PostgreSQL JSONB."""
    d = cert.model_dump(mode="json")
    # Convert UUIDs to strings for JSON
    d["cert_id"] = str(cert.cert_id)
    d["session_id"] = str(cert.session_id)
    return d
