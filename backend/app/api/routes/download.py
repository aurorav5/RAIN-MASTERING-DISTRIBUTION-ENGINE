from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from uuid import UUID
import asyncio
import subprocess
import tempfile
from pathlib import Path
import structlog
from app.core.database import get_db
from app.api.dependencies import get_current_user, CurrentUser
from app.models.session import Session as MasteringSession
from app.services.storage import generate_presigned_url, download_from_s3, upload_to_s3, head_object
from app.services.quota import check_and_increment_downloads

logger = structlog.get_logger()
router = APIRouter(prefix="/sessions", tags=["download"])


async def _key_exists(key: str) -> bool:
    """Check if an S3 key exists (True/False, swallows 404)."""
    try:
        await head_object(key)
        return True
    except Exception:
        return False


async def _upload_bytes(key: str, data: bytes) -> None:
    """Upload raw bytes to S3 under the given key."""
    from app.services.storage import _s3_client
    from app.core.config import settings

    async with _s3_client() as client:
        await client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=data,
        )


@router.get("/{session_id}/download")
async def download_master(
    session_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(current_user.user_id)})

    result = await db.execute(
        select(MasteringSession).where(
            MasteringSession.id == session_id,
            MasteringSession.user_id == current_user.user_id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(404, detail={"code": "RAIN-E200", "message": "Session not found"})
    if session.status != "complete":
        raise HTTPException(400, detail={"code": "RAIN-E200", "message": "Session not complete"})
    if not session.output_file_key:
        raise HTTPException(400, detail={"code": "RAIN-E200", "message": "No output file"})

    # Quota check enforces free tier block (raises 402 for free tier)
    await check_and_increment_downloads(current_user.user_id, current_user.tier, db)

    url = await generate_presigned_url(session.output_file_key, expires_seconds=300)
    logger.info(
        "download_presigned_url_generated",
        session_id=str(session_id),
        user_id=str(current_user.user_id),
        stage="download",
    )
    return RedirectResponse(url=url, status_code=302)


# ── Multi-format transcode (MP3 320 / FLAC / AAC / OGG) ────────────────────

_TRANSCODE_FORMATS = {"mp3", "flac", "aac", "ogg"}

_FFMPEG_ARGS: dict[str, list[str]] = {
    "mp3":  ["-codec:a", "libmp3lame", "-b:a", "320k"],
    "flac": ["-codec:a", "flac"],
    "aac":  ["-codec:a", "aac", "-b:a", "256k"],
    "ogg":  ["-codec:a", "libvorbis", "-q:a", "8"],
}

_FORMAT_EXT: dict[str, str] = {
    "mp3": "mp3",
    "flac": "flac",
    "aac": "m4a",
    "ogg": "ogg",
}


async def _transcode(wav_bytes: bytes, fmt: str) -> bytes:
    """Transcode WAV bytes to target format via ffmpeg subprocess."""
    args = _FFMPEG_ARGS[fmt]
    ext = _FORMAT_EXT[fmt]

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.wav"
        output_path = Path(tmpdir) / f"output.{ext}"
        input_path.write_bytes(wav_bytes)

        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            *args,
            str(output_path),
        ]
        proc = await asyncio.to_thread(
            subprocess.run, cmd,
            capture_output=True, timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"RAIN-E703: ffmpeg transcode to {fmt} failed: {proc.stderr.decode(errors='replace')[:500]}"
            )
        return output_path.read_bytes()


@router.get("/{session_id}/download/{fmt}")
async def download_master_format(
    session_id: UUID,
    fmt: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if fmt not in _TRANSCODE_FORMATS:
        raise HTTPException(422, detail={
            "code": "RAIN-E703",
            "message": f"Unknown format '{fmt}'. Supported: {', '.join(sorted(_TRANSCODE_FORMATS))}",
        })

    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(current_user.user_id)})

    result = await db.execute(
        select(MasteringSession).where(
            MasteringSession.id == session_id,
            MasteringSession.user_id == current_user.user_id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(404, detail={"code": "RAIN-E200", "message": "Session not found"})
    if session.status != "complete":
        raise HTTPException(400, detail={"code": "RAIN-E200", "message": "Session not complete"})
    if not session.output_file_key:
        raise HTTPException(400, detail={"code": "RAIN-E200", "message": "No output file"})

    await check_and_increment_downloads(current_user.user_id, current_user.tier, db)

    # Deterministic S3 key for transcoded output
    ext = _FORMAT_EXT[fmt]
    base_key = session.output_file_key.rsplit(".", 1)[0]
    transcode_key = f"{base_key}.{ext}"

    # Check cache: skip transcode if already exists in S3
    if not await _key_exists(transcode_key):
        wav_bytes = await download_from_s3(session.output_file_key)
        transcoded = await _transcode(wav_bytes, fmt)
        await _upload_bytes(transcode_key, transcoded)
        logger.info(
            "transcode_complete",
            session_id=str(session_id),
            user_id=str(current_user.user_id),
            format=fmt,
            size_bytes=len(transcoded),
            stage="download",
        )

    url = await generate_presigned_url(transcode_key, expires_seconds=300)
    return RedirectResponse(url=url, status_code=302)


# ── DDP 2.0 export ──────────────────────────────────────────────────────────

@router.get("/{session_id}/ddp")
async def download_ddp(
    session_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Generate and download a DDP 2.0 image as a ZIP archive.

    DDP image contains: DDPID, DDPMS, PQSHEET, and 16-bit 44.1kHz PCM audio.
    Studio Pro+ only (feature gate enforced by route middleware).
    """
    await db.execute(text("SELECT set_app_user_id(:uid::uuid)"), {"uid": str(current_user.user_id)})

    result = await db.execute(
        select(MasteringSession).where(
            MasteringSession.id == session_id,
            MasteringSession.user_id == current_user.user_id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(404, detail={"code": "RAIN-E200", "message": "Session not found"})
    if session.status != "complete":
        raise HTTPException(400, detail={"code": "RAIN-E200", "message": "Session not complete"})
    if not session.output_file_key:
        raise HTTPException(400, detail={"code": "RAIN-E200", "message": "No output file"})

    await check_and_increment_downloads(current_user.user_id, current_user.tier, db)

    ddp_key = session.output_file_key.rsplit(".", 1)[0] + ".ddp.zip"

    if not await _key_exists(ddp_key):
        wav_bytes = await download_from_s3(session.output_file_key)
        ddp_zip = await asyncio.to_thread(_build_ddp_image, wav_bytes, session)
        await _upload_bytes(ddp_key, ddp_zip)
        logger.info(
            "ddp_export_complete",
            session_id=str(session_id),
            user_id=str(current_user.user_id),
            size_bytes=len(ddp_zip),
            stage="download",
        )

    url = await generate_presigned_url(ddp_key, expires_seconds=300)
    return RedirectResponse(url=url, status_code=302)


def _build_ddp_image(wav_bytes: bytes, session: MasteringSession) -> bytes:
    """Build a DDP 2.0 image ZIP from WAV audio data."""
    import io
    import struct
    import zipfile
    import soundfile as sf
    import numpy as np

    # Read and convert to 16-bit 44.1kHz PCM
    audio, sr = sf.read(io.BytesIO(wav_bytes), dtype="float64", always_2d=True)

    if sr != 44100:
        import resampy
        audio = resampy.resample(audio, sr, 44100, axis=0, filter="kaiser_best")
        sr = 44100

    # Convert to 16-bit int
    audio_16 = np.clip(audio, -1.0, 1.0 - 1.0 / (2 ** 15))
    pcm_data = (audio_16 * (2 ** 15)).astype(np.int16).tobytes()

    duration_sec = len(audio) / sr
    isrc = getattr(session, "isrc", "") or ""
    title = getattr(session, "title", "Untitled") or "Untitled"

    # DDPID — descriptor identifier
    ddpid = f"DDP_ID\r\nIdentifier: RAIN-{session.id}\r\nFormat: DDP 2.00\r\n"

    # DDPMS — master descriptor
    ddpms = (
        f"DDP_MS\r\n"
        f"Title: {title}\r\n"
        f"SampleRate: {sr}\r\n"
        f"BitDepth: 16\r\n"
        f"Channels: {audio_16.shape[1]}\r\n"
        f"Duration: {duration_sec:.3f}\r\n"
    )

    # PQSHEET — track descriptor
    minutes = int(duration_sec // 60)
    seconds = int(duration_sec % 60)
    frames = int((duration_sec % 1) * 75)
    pqsheet = (
        f"PQ_DESCRIPTOR\r\n"
        f"TrackCount: 1\r\n"
        f"Track 01:\r\n"
        f"  Start: 00:00:00.00\r\n"
        f"  End: {minutes:02d}:{seconds:02d}:{frames:02d}.00\r\n"
        f"  ISRC: {isrc}\r\n"
        f"  PreGap: 02:00\r\n"
    )

    # Package as ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("DDPID", ddpid)
        zf.writestr("DDPMS", ddpms)
        zf.writestr("PQSHEET", pqsheet)
        zf.writestr("AUDIO.PCM", pcm_data)
    return buf.getvalue()
