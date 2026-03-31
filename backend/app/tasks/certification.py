"""RAIN-CERT: Ed25519 signed provenance certificate for each completed session."""
from celery import shared_task
import asyncio
import json
import hashlib
import structlog
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from pathlib import Path

logger = structlog.get_logger()


def _load_cert_key() -> Ed25519PrivateKey:
    """Load Ed25519 signing key from env-configured path."""
    from app.core.config import settings
    key_path = getattr(settings, "RAIN_CERT_SIGNING_KEY_PATH", None)
    if not key_path or not Path(key_path).exists():
        # Dev fallback: generate ephemeral key (not for production)
        logger.warning("cert_key_not_found", path=key_path, note="using ephemeral dev key")
        return Ed25519PrivateKey.generate()
    return serialization.load_pem_private_key(
        Path(key_path).read_bytes(),
        password=None,
    )  # type: ignore[return-value]


@shared_task(name="app.tasks.certification.sign_rain_cert", bind=True, max_retries=3)
def sign_rain_cert(self, session_id: str, user_id: str) -> None:
    asyncio.run(_sign_cert_async(session_id, user_id))


async def _sign_cert_async(session_id: str, user_id: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.session import Session as MasteringSession
    from app.models.cert import RainCert
    from app.models.content_scan import ContentScan
    from sqlalchemy import select, update, text
    from uuid import UUID, uuid4
    from datetime import datetime, timezone

    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(user_id)})

        sess_result = await db.execute(
            select(MasteringSession).where(MasteringSession.id == UUID(session_id))
        )
        session = sess_result.scalar_one_or_none()
        if not session:
            logger.error("cert_session_not_found", session_id=session_id)
            return

        # Idempotency: skip if cert already exists
        existing_cert = await db.execute(
            select(RainCert).where(RainCert.session_id == UUID(session_id))
        )
        if existing_cert.scalar_one_or_none():
            logger.info("cert_skip_idempotent", session_id=session_id)
            return

        scan_result = await db.execute(
            select(ContentScan).where(ContentScan.session_id == UUID(session_id))
        )
        scan = scan_result.scalar_one_or_none()

        params_hash = (
            hashlib.sha256(
                json.dumps(session.processing_params, sort_keys=True).encode()
            ).hexdigest()
            if session.processing_params
            else "none"
        )

        cert_payload = {
            "session_id": session_id,
            "user_id_hash": hashlib.sha256(user_id.encode()).hexdigest(),
            "input_hash": session.input_file_hash or "",
            "output_hash": session.output_file_hash or "",
            "wasm_hash": session.wasm_binary_hash or "pending",
            "model_version": session.rainnet_model_version or "heuristic",
            "processing_params_hash": params_hash,
            "content_scan_status": scan.overall_status if scan else "not_run",
            "ai_generated": False,
            "issued_at": datetime.now(timezone.utc).isoformat(),
        }

        canonical_json = json.dumps(cert_payload, sort_keys=True, separators=(",", ":"))
        private_key = _load_cert_key()
        signature_bytes = private_key.sign(canonical_json.encode())
        signature_b64 = base64.b64encode(signature_bytes).decode()

        cert = RainCert(
            id=uuid4(),
            session_id=UUID(session_id),
            user_id=UUID(user_id),
            input_hash=session.input_file_hash or "",
            output_hash=session.output_file_hash or "",
            wasm_hash=session.wasm_binary_hash or "pending",
            model_version=session.rainnet_model_version or "heuristic",
            processing_params_hash=params_hash,
            content_scan_passed=(scan.overall_status == "clear" if scan else None),
            signature=signature_b64,
        )
        db.add(cert)

        await db.execute(
            update(MasteringSession)
            .where(MasteringSession.id == UUID(session_id))
            .values(rain_cert_id=cert.id)
        )
        await db.commit()
        logger.info("rain_cert_signed", session_id=session_id, cert_id=str(cert.id), stage="certification", user_id=user_id)
