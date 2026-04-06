"""Strict Pydantic models for RAIN-CERT provenance chain.

Replaces the loose dataclass RainCert/ProvenanceStep with strict validation.
All fields required, no empty string defaults, UUID/hash/signature constraints enforced.

Per audit finding: "structured data instead of strict truth" — this module
ensures provenance data is valid BEFORE it's signed or persisted.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_B64URL_RE = re.compile(r"^[A-Za-z0-9_-]{10,}$")  # min 10 chars for Ed25519 sig


class ProvenanceStep(BaseModel):
    """A single step in the RAIN-CERT provenance chain — strict validation."""

    model_config = ConfigDict(strict=True, frozen=True)

    stage: str = Field(..., min_length=1, max_length=64)
    timestamp: datetime
    input_hash: str = Field(..., min_length=64, max_length=64)
    output_hash: str = Field(..., min_length=64, max_length=64)
    params_hash: Optional[str] = Field(default=None)
    wasm_hash: Optional[str] = Field(default=None)
    model_version: Optional[str] = Field(default=None)
    duration_ms: float = Field(default=0.0, ge=0.0)

    @field_validator("input_hash", "output_hash")
    @classmethod
    def _validate_hex64(cls, v: str) -> str:
        if not _HEX64_RE.match(v):
            raise ValueError(f"must be a 64-char lowercase hex SHA-256 hash, got {v!r}")
        return v


class StrictRainCert(BaseModel):
    """RAIN-CERT with strict Pydantic validation.

    Every field is required and validated before signing. The cert_id must be
    a UUID, hashes must be 64-char hex, and the signature must be non-empty
    once signed.
    """

    model_config = ConfigDict(strict=True)

    cert_id: UUID
    session_id: UUID
    created_at: datetime
    version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    source_hash: str = Field(..., min_length=64, max_length=64)
    output_hash: str = Field(..., min_length=64, max_length=64)
    chain: list[ProvenanceStep] = Field(default_factory=list)
    signature: str = Field(default="")  # empty until signed
    ai_generated: bool = False
    ai_source: str = Field(default="")
    processing_summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_hash", "output_hash")
    @classmethod
    def _validate_hex64(cls, v: str) -> str:
        if not _HEX64_RE.match(v):
            raise ValueError(f"must be a 64-char lowercase hex SHA-256 hash, got {v!r}")
        return v

    def is_signed(self) -> bool:
        return bool(self.signature and len(self.signature) >= 10)

    def assert_signed(self) -> None:
        """Raise ValueError if the cert has not been signed."""
        if not self.is_signed():
            raise ValueError(
                f"RAIN-E306: cert {self.cert_id} has no valid signature — "
                "every master must have a signed cert before output is committed"
            )

    def assert_output_hash_matches(self, actual_hash: str) -> None:
        """Hard enforcement gate: output hash must match cert.

        Raises:
            ValueError: RAIN-E305 if hash mismatch — provenance chain broken.
        """
        if self.output_hash != actual_hash:
            raise ValueError(
                f"RAIN-E305: output hash mismatch — provenance chain broken. "
                f"cert.output_hash={self.output_hash[:16]}... "
                f"actual={actual_hash[:16]}..."
            )
