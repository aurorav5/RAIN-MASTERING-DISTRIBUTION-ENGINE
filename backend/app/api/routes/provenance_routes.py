"""Provenance public API routes.

GET /api/v1/provenance/public-key — returns the Ed25519 public key PEM
for independent RAIN-CERT signature verification.
"""
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.services.provenance import get_public_key_pem

router = APIRouter(prefix="/provenance", tags=["provenance"])


@router.get(
    "/public-key",
    response_class=PlainTextResponse,
    summary="RAIN-CERT Ed25519 public key",
    description=(
        "Returns the PEM-encoded Ed25519 public key used to sign RAIN-CERT "
        "provenance certificates. Use this to independently verify any cert's "
        "signature: decode the base64url signature, then verify against the "
        "canonical JSON payload using Ed25519."
    ),
)
async def get_provenance_public_key() -> str:
    return get_public_key_pem()
