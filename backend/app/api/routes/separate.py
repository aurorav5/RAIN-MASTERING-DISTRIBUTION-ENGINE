"""
Stem separation route.
POST /api/v1/separate/upload          — upload audio, queue separation
GET  /api/v1/separate/{job_id}/status — poll status
GET  /api/v1/separate/{job_id}/stems  — get stem download URLs
WS   /api/v1/separate/{job_id}/ws     — WebSocket progress stream

When BS-RoFormer is not available (SEPARATION_ENABLED != true),
returns a structured response explaining the fallback:
{
  "status": "unavailable",
  "reason": "separation_not_available",
  "message": "Stem separation requires server-side GPU processing. Available for Creator+ tiers.",
  "fallback": "Upload pre-separated stems via /api/v1/separate/upload-stems"
}
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = structlog.get_logger()

router = APIRouter(prefix="/separate", tags=["separation"])

# In-memory job store (no DB dependency) — same pattern as master.py's _sessions
_separation_jobs: dict[str, dict[str, Any]] = {}

ALLOWED_EXTENSIONS = {".wav", ".flac", ".aiff", ".aif", ".mp3"}
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB

STEM_NAMES = [
    "vocals", "drums", "bass", "guitar", "piano", "synth",
    "strings", "brass", "woodwinds", "percussion", "fx", "other",
]

UPLOAD_DIR = Path(tempfile.gettempdir()) / "rain_separate_uploads"
STEMS_DIR = Path(tempfile.gettempdir()) / "rain_separate_stems"
UPLOAD_DIR.mkdir(exist_ok=True)
STEMS_DIR.mkdir(exist_ok=True)

_UNAVAILABLE_RESPONSE: dict[str, str] = {
    "status": "unavailable",
    "reason": "separation_not_available",
    "message": "Stem separation requires server-side GPU processing (BS-RoFormer cascade). Available for Creator+ tiers.",
    "fallback": "Upload pre-separated stems via /api/v1/separate/upload-stems",
}


def _separation_available() -> bool:
    """Return True only when separation is enabled with GPU."""
    return getattr(settings, "SEPARATION_ENABLED", False) is True


@router.post("/upload")
async def upload_for_separation(file: UploadFile = File(...)) -> dict[str, Any]:
    """
    Upload an audio file and queue it for stem separation.
    Returns job_id for subsequent status polling and WebSocket progress.

    If BS-RoFormer is unavailable (no GPU), returns a structured unavailable response
    with instructions to use the manual upload-stems endpoint instead.
    """
    if not _separation_available():
        log = logger.bind(stage="upload", reason="separation_not_available")
        log.info("separation_unavailable", separation_enabled=getattr(settings, "SEPARATION_ENABLED", False))
        return _UNAVAILABLE_RESPONSE

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Accepted: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 200MB)")

    job_id = str(uuid.uuid4())
    input_path = str(UPLOAD_DIR / f"{job_id}{ext}")

    with open(input_path, "wb") as fh:
        fh.write(content)

    _separation_jobs[job_id] = {
        "job_id": job_id,
        "filename": file.filename,
        "file_size": len(content),
        "input_path": input_path,
        "status": "queued",
        "progress": 0,
        "stems": {name: {"status": "processing", "path": None} for name in STEM_NAMES},
        "error": None,
    }

    logger.info(
        "separation_job_created",
        job_id=job_id,
        filename=file.filename,
        file_size=len(content),
        stage="upload",
    )

    return {"job_id": job_id, "status": "queued", "filename": file.filename}


@router.get("/{job_id}/status")
async def get_separation_status(job_id: str) -> dict[str, Any]:
    """
    Poll the status of a stem separation job.
    Returns job status dict including progress (0-100) and per-stem status.
    """
    job = _separation_jobs.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"code": "RAIN-E700", "message": "Separation job not found"},
        )

    log = logger.bind(job_id=job_id, stage="status")
    log.debug("separation_status_polled", status=job["status"], progress=job["progress"])

    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "filename": job["filename"],
        "stems": {
            name: {"status": stem["status"]}
            for name, stem in job["stems"].items()
        },
        "error": job["error"],
    }


@router.get("/{job_id}/stems")
async def get_stem_download_urls(job_id: str) -> dict[str, Any]:
    """
    Get stem download URLs for a completed separation job.
    Returns 6 stem slots (vocals, drums, bass, guitar, piano, other).
    Until processing is complete, each stem shows status "pending".
    """
    job = _separation_jobs.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"code": "RAIN-E700", "message": "Separation job not found"},
        )

    log = logger.bind(job_id=job_id, stage="stems")

    if job["status"] != "complete":
        log.info("stems_not_ready", status=job["status"])
        stems_info = [
            {"name": name, "status": "pending", "download_url": None}
            for name in STEM_NAMES
        ]
        return {
            "job_id": job_id,
            "status": job["status"],
            "stems": stems_info,
        }

    stems_info = [
        {
            "name": name,
            "status": stem["status"],
            "download_url": f"/api/v1/separate/{job_id}/stems/{name}/download"
            if stem["status"] == "complete" else None,
        }
        for name, stem in job["stems"].items()
    ]

    log.info("stems_ready", count=len(stems_info))
    return {
        "job_id": job_id,
        "status": job["status"],
        "stems": stems_info,
    }


@router.post("/upload-stems")
async def upload_pre_separated_stems(
    vocals: UploadFile = File(default=None),
    drums: UploadFile = File(default=None),
    bass: UploadFile = File(default=None),
    guitar: UploadFile = File(default=None),
    piano: UploadFile = File(default=None),
    other: UploadFile = File(default=None),
) -> dict[str, Any]:
    """
    Accept up to 6 pre-separated stems as form files.
    Stores them and returns session info for manual stem upload workflow.
    This is the fallback path when BS-RoFormer GPU processing is unavailable.
    """
    stem_files: dict[str, UploadFile | None] = {
        "vocals": vocals,
        "drums": drums,
        "bass": bass,
        "guitar": guitar,
        "piano": piano,
        "other": other,
    }

    session_id = str(uuid.uuid4())
    session_stem_dir = STEMS_DIR / session_id
    session_stem_dir.mkdir(exist_ok=True)

    stored: list[dict[str, Any]] = []
    for name, stem_file in stem_files.items():
        if stem_file is None or not stem_file.filename:
            stored.append({"name": name, "status": "not_provided", "filename": None})
            continue

        ext = Path(stem_file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Stem '{name}': unsupported format '{ext}'",
            )

        content = await stem_file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Stem '{name}' too large (max 200MB)",
            )

        dest = session_stem_dir / f"{name}{ext}"
        with open(str(dest), "wb") as fh:
            fh.write(content)

        stored.append({
            "name": name,
            "status": "uploaded",
            "filename": stem_file.filename,
            "file_size": len(content),
        })

        logger.info(
            "stem_uploaded",
            session_id=session_id,
            stem=name,
            filename=stem_file.filename,
            file_size=len(content),
            stage="upload-stems",
        )

    provided_count = sum(1 for s in stored if s["status"] == "uploaded")

    _separation_jobs[session_id] = {
        "job_id": session_id,
        "filename": "manual-stems",
        "file_size": 0,
        "input_path": None,
        "status": "stems_uploaded",
        "progress": 100,
        "stems": {
            s["name"]: {"status": s["status"], "path": str(session_stem_dir / f"{s['name']}.wav")}
            for s in stored
        },
        "error": None,
    }

    logger.info(
        "stems_session_created",
        session_id=session_id,
        provided_count=provided_count,
        stage="upload-stems",
    )

    return {
        "session_id": session_id,
        "status": "stems_uploaded",
        "stems_provided": provided_count,
        "stems": stored,
    }


@router.websocket("/{job_id}/ws")
async def separation_progress_ws(websocket: WebSocket, job_id: str) -> None:
    """
    WebSocket progress stream for a stem separation job.
    Emits JSON progress events as the job advances through stages.
    Client receives: {"job_id": ..., "status": ..., "progress": ..., "stage": ...}
    """
    await websocket.accept()

    log = logger.bind(job_id=job_id, stage="ws")

    job = _separation_jobs.get(job_id)
    if not job:
        await websocket.send_json({
            "job_id": job_id,
            "status": "error",
            "progress": 0,
            "stage": "init",
            "error_code": "RAIN-E700",
            "message": "Separation job not found",
        })
        await websocket.close()
        return

    log.info("ws_client_connected")

    try:
        # Send current state immediately on connect
        await websocket.send_json({
            "job_id": job_id,
            "status": job["status"],
            "progress": job["progress"],
            "stage": job["status"],
        })

        # Keep connection open; client can disconnect anytime
        while True:
            try:
                data = await websocket.receive_text()
                # Respond to ping messages
                if data == "ping":
                    current = _separation_jobs.get(job_id, job)
                    await websocket.send_json({
                        "job_id": job_id,
                        "status": current["status"],
                        "progress": current["progress"],
                        "stage": current["status"],
                    })
            except WebSocketDisconnect:
                log.info("ws_client_disconnected")
                break

    except Exception as exc:  # noqa: BLE001
        log.error("ws_error", error=str(exc))
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass
