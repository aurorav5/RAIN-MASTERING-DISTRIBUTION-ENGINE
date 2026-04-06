"""Three-layer content verification scan: Chromaprint/AcoustID → AudD → ACRCloud."""
from celery import shared_task
import asyncio
import httpx
import hashlib
import subprocess
import json
import structlog
import base64
import time
from typing import Optional

logger = structlog.get_logger()

RETRY_DELAYS = [1, 2, 4]  # Exponential backoff seconds


@shared_task(name="app.tasks.content_scan.scan_content", bind=True, max_retries=2)
def scan_content(self, session_id: str, user_id: str) -> None:
    asyncio.run(_scan_async(session_id, user_id))


async def _scan_async(session_id: str, user_id: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.session import Session as MasteringSession
    from app.models.content_scan import ContentScan
    from app.services.storage import download_from_s3
    from app.core.config import settings
    from sqlalchemy import select, text
    from uuid import UUID, uuid4

    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(user_id)})
        result = await db.execute(
            select(MasteringSession).where(MasteringSession.id == UUID(session_id))
        )
        session = result.scalar_one_or_none()
        if not session or not session.input_file_key:
            logger.info("content_scan_skip", session_id=session_id, reason="no_input_file")
            return

        try:
            audio_data = await download_from_s3(session.input_file_key)
        except Exception as e:
            logger.error("content_scan_s3_fail", session_id=session_id, error=str(e), error_code="RAIN-E800")
            return

        # Run all three layers with failure isolation
        chromaprint_result = await _scan_chromaprint_safe(audio_data, session_id)
        audd_result = await _scan_audd_safe(audio_data, getattr(settings, "AUDD_API_TOKEN", ""), session_id)
        acrcloud_result = await _scan_acrcloud_safe(
            audio_data,
            getattr(settings, "ACRCLOUD_HOST", ""),
            getattr(settings, "ACRCLOUD_ACCESS_KEY", ""),
            getattr(settings, "ACRCLOUD_ACCESS_SECRET", ""),
            session_id,
        )

        # Determine status
        match_found = (
            (audd_result.get("status") == "success" and audd_result.get("result")) or
            (isinstance(acrcloud_result.get("status"), dict) and
             acrcloud_result["status"].get("code") == 0 and
             acrcloud_result.get("metadata", {}).get("music"))
        )
        layers_complete = sum([
            bool(chromaprint_result.get("fingerprint")),
            audd_result.get("status") not in ("error", "skipped"),
            isinstance(acrcloud_result.get("status"), dict) and acrcloud_result["status"].get("code") != -999,
        ])
        if match_found:
            overall_status = "match_found"
        elif layers_complete == 0:
            overall_status = "incomplete"
        else:
            overall_status = "clear"

        scan = ContentScan(
            session_id=UUID(session_id),
            user_id=UUID(user_id),
            chromaprint_fingerprint=chromaprint_result.get("fingerprint"),
            acoustid_result=chromaprint_result,
            audd_result=audd_result,
            acrcloud_result=acrcloud_result,
            overall_status=overall_status,
        )
        db.add(scan)
        await db.commit()
        logger.info("content_scan_complete", session_id=session_id, status=overall_status, stage="content_scan", user_id=user_id)


async def _scan_chromaprint_safe(audio_data: bytes, session_id: str) -> dict:
    """Chromaprint/AcoustID scan with failure isolation."""
    import tempfile, os
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            tmp_path = f.name
        try:
            result = subprocess.run(
                ["fpcalc", "-json", tmp_path],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return {"fingerprint": data.get("fingerprint"), "duration": data.get("duration")}
            logger.warning("chromaprint_nonzero", session_id=session_id, returncode=result.returncode, error_code="RAIN-E800")
        finally:
            os.unlink(tmp_path)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("chromaprint_failed", session_id=session_id, error=str(e), error_code="RAIN-E800")
    except Exception as e:
        logger.error("chromaprint_error", session_id=session_id, error=str(e), error_code="RAIN-E800")
    return {}


async def _scan_audd_safe(audio_data: bytes, api_token: str, session_id: str) -> dict:
    """AudD scan with retries and failure isolation."""
    if not api_token:
        return {"status": "skipped", "reason": "no_api_token"}
    for attempt, delay in enumerate(RETRY_DELAYS):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.audd.io/",
                    data={"api_token": api_token, "return": "spotify,apple_music"},
                    files={"file": ("audio.wav", audio_data, "audio/wav")},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning("audd_retry", session_id=session_id, attempt=attempt+1, error=str(e), error_code="RAIN-E800")
            if attempt < len(RETRY_DELAYS) - 1:
                await asyncio.sleep(delay)
    return {"status": "error", "reason": "max_retries_exceeded"}


async def _scan_acrcloud_safe(
    audio_data: bytes,
    host: str,
    access_key: str,
    access_secret: str,
    session_id: str,
) -> dict:
    """ACRCloud scan with retries and failure isolation."""
    if not access_key or not access_secret:
        return {"status": {"code": -1, "msg": "skipped"}}
    import hmac as hmac_lib
    for attempt, delay in enumerate(RETRY_DELAYS):
        try:
            timestamp = str(int(time.time()))
            string_to_sign = "\n".join(["POST", "/v1/identify", access_key, "audio", "1", timestamp])
            signature = base64.b64encode(
                hmac_lib.new(access_secret.encode(), string_to_sign.encode(), hashlib.sha1).digest()
            ).decode()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"https://{host}/v1/identify",
                    data={
                        "access_key": access_key,
                        "sample_bytes": str(len(audio_data)),
                        "timestamp": timestamp,
                        "signature": signature,
                        "data_type": "audio",
                        "signature_version": "1",
                    },
                    files={"sample": ("audio.wav", audio_data[:10 * 44100 * 2 * 2], "audio/wav")},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning("acrcloud_retry", session_id=session_id, attempt=attempt+1, error=str(e), error_code="RAIN-E800")
            if attempt < len(RETRY_DELAYS) - 1:
                await asyncio.sleep(delay)
    return {"status": {"code": -999, "msg": "max_retries_exceeded"}}
