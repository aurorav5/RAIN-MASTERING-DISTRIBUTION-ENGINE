"""
RAIN Prototype Mastering API Routes

POST /api/v1/master/upload       — Upload audio file, get session_id
POST /api/v1/master/{id}/process — Trigger mastering with params + metadata
GET  /api/v1/master/{id}/download/{format} — Download mastered WAV or MP3
GET  /api/v1/master/{id}/analysis — Get analysis results as JSON
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.master_engine import (
    AnalysisResult,
    MasteringParams,
    MasterResult,
    analyze,
    load_audio,
    master_audio,
    normalize_input,
    INTERNAL_SR,
)
from app.services.metadata_engine import write_metadata
from app.services.feature_extraction import extract_features, FeatureVector
from app.services.qc_engine import run_qc, QCReport
from app.services.platform_targets import get_platform_target, list_platform_targets
from app.services.provenance import create_rain_cert, create_c2pa_manifest, RainCert

logger = structlog.get_logger()

router = APIRouter(prefix="/master", tags=["mastering"])

# In-memory session store for the prototype (no DB dependency)
_sessions: dict[str, dict[str, Any]] = {}

# Simple IP-based rate limiter for prototype (no auth = no user_id)
_upload_timestamps: dict[str, list[float]] = {}
_UPLOAD_RATE_LIMIT = 10
_UPLOAD_WINDOW_SECONDS = 60.0


def _check_upload_rate_limit(client_ip: str) -> None:
    """Raise 429 if client exceeds upload rate limit."""
    import time
    now = time.time()
    cutoff = now - _UPLOAD_WINDOW_SECONDS
    timestamps = _upload_timestamps.get(client_ip, [])
    timestamps = [t for t in timestamps if t > cutoff]
    if len(timestamps) >= _UPLOAD_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "RAIN-E102",
                "message": f"Upload rate limit exceeded ({_UPLOAD_RATE_LIMIT} per {int(_UPLOAD_WINDOW_SECONDS)}s)",
            },
        )
    timestamps.append(now)
    _upload_timestamps[client_ip] = timestamps


ALLOWED_EXTENSIONS = {".wav", ".flac", ".aiff", ".aif", ".mp3"}
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB

# Temp directory for uploads and outputs
UPLOAD_DIR = Path(tempfile.gettempdir()) / "rain_uploads"
OUTPUT_DIR = Path(tempfile.gettempdir()) / "rain_outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


class ProcessRequest(BaseModel):
    target_lufs: float = Field(default=-14.0, ge=-16.0, le=-9.0)
    brightness: float = Field(default=2.0, ge=0.0, le=4.0)
    tightness: float = Field(default=3.0, ge=1.0, le=5.0)
    width: float = Field(default=2.0, ge=-3.0, le=6.0)
    warmth: float = Field(default=0.0, ge=0.0, le=3.0)
    punch: float = Field(default=10.0, ge=1.0, le=30.0)
    air: float = Field(default=1.5, ge=0.0, le=3.0)
    # Metadata
    title: str = ""
    artist: str = ""
    album: str = ""
    genre: str = ""
    track_number: str = "1"
    year: str = ""


class UploadResponse(BaseModel):
    session_id: str
    filename: str
    format: str
    file_size: int
    duration: float | None = None


class AnalysisResponse(BaseModel):
    input_lufs: float
    input_true_peak: float
    spectral_centroid: float
    crest_factor: float
    stereo_width: float
    bass_energy_ratio: float
    dynamic_range: float
    sample_rate: int
    channels: int
    duration: float
    # Post-mastering (if processed)
    output_lufs: float | None = None
    output_true_peak: float | None = None
    output_dynamic_range: float | None = None
    output_stereo_width: float | None = None
    output_spectral_centroid: float | None = None


class ProcessResponse(BaseModel):
    session_id: str
    status: str
    output_lufs: float
    output_true_peak: float
    output_dynamic_range: float
    output_stereo_width: float
    output_spectral_centroid: float


@router.post("/upload", response_model=UploadResponse)
async def upload_audio(request: Request, file: UploadFile = File(...)) -> UploadResponse:
    """Upload an audio file for mastering. Returns session_id for subsequent operations."""
    client_ip = request.client.host if request.client else "unknown"
    _check_upload_rate_limit(client_ip)
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Accepted: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 200MB)")

    session_id = str(uuid.uuid4())
    input_path = str(UPLOAD_DIR / f"{session_id}{ext}")

    # Write to disk
    with open(input_path, "wb") as f:
        f.write(content)

    # Quick analysis for the upload response
    try:
        raw_audio, original_sr = load_audio(input_path)
        audio = normalize_input(raw_audio, original_sr)
        analysis = analyze(audio, INTERNAL_SR, original_sr)
        # 43-dim feature extraction per RAIN-PLATFORM-SPEC Stage 4
        features = extract_features(audio, INTERNAL_SR)
    except Exception as e:
        os.unlink(input_path)
        logger.error("upload_analysis_failed", error=str(e), session_id=session_id)
        raise HTTPException(status_code=400, detail=f"Could not read audio file: {e}")

    # Store session
    _sessions[session_id] = {
        "input_path": input_path,
        "filename": file.filename,
        "format": ext.lstrip("."),
        "file_size": len(content),
        "analysis": analysis,
        "features": features,
        "status": "uploaded",
        "result": None,
        "qc_report": None,
    }

    logger.info(
        "upload_complete",
        session_id=session_id,
        filename=file.filename,
        format=ext,
        duration=analysis.duration,
        input_lufs=analysis.input_lufs,
    )

    return UploadResponse(
        session_id=session_id,
        filename=file.filename,
        format=ext.lstrip("."),
        file_size=len(content),
        duration=analysis.duration,
    )


@router.get("/{session_id}/analysis", response_model=AnalysisResponse)
async def get_analysis(session_id: str) -> AnalysisResponse:
    """Get analysis results for a session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    a: AnalysisResult = session["analysis"]
    result = session.get("result")

    resp = AnalysisResponse(
        input_lufs=round(a.input_lufs, 1),
        input_true_peak=round(a.input_true_peak, 1),
        spectral_centroid=round(a.spectral_centroid, 1),
        crest_factor=round(a.crest_factor, 1),
        stereo_width=round(a.stereo_width, 3),
        bass_energy_ratio=round(a.bass_energy_ratio, 3),
        dynamic_range=round(a.dynamic_range, 1),
        sample_rate=a.sample_rate,
        channels=a.channels,
        duration=round(a.duration, 2),
    )

    if result:
        resp.output_lufs = round(result.output_lufs, 1)
        resp.output_true_peak = round(result.output_true_peak, 1)
        resp.output_dynamic_range = round(result.output_dynamic_range, 1)
        resp.output_stereo_width = round(result.output_stereo_width, 3)
        resp.output_spectral_centroid = round(result.output_spectral_centroid, 1)

    return resp


@router.post("/{session_id}/process", response_model=ProcessResponse)
async def process_audio(session_id: str, req: ProcessRequest) -> ProcessResponse:
    """Trigger the mastering chain with given parameters and metadata."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] == "processing":
        raise HTTPException(status_code=409, detail="Already processing")

    session["status"] = "processing"

    params = MasteringParams(
        brightness=req.brightness,
        tightness=req.tightness,
        width=req.width,
        loudness=req.target_lufs,
        warmth=req.warmth,
        punch=req.punch,
        air=req.air,
    )

    metadata = {
        "title": req.title or Path(session["filename"]).stem,
        "artist": req.artist,
        "album": req.album,
        "genre": req.genre,
        "track_number": req.track_number,
        "year": req.year,
    }

    # Create output directory for this session
    session_output = str(OUTPUT_DIR / session_id)
    os.makedirs(session_output, exist_ok=True)

    try:
        logger.info("mastering_start", session_id=session_id, target_lufs=req.target_lufs)

        result = master_audio(
            input_path=session["input_path"],
            output_dir=session_output,
            session_id=session_id,
            params=params,
            metadata=metadata,
        )

        # Write metadata to output files
        write_metadata(
            wav_path=result.output_wav_path,
            mp3_path=result.output_mp3_path,
            metadata=metadata,
            session_id=session_id,
            output_lufs=result.output_lufs,
            output_true_peak=result.output_true_peak,
        )

        # Run QC (18 automated checks) per RAIN-PLATFORM-SPEC Stage 14
        raw_output, _ = load_audio(result.output_wav_path)
        output_audio = normalize_input(raw_output, INTERNAL_SR)
        platform_slug = req.genre if req.genre in ("vinyl", "podcast") else "spotify"
        qc_report, _ = run_qc(
            output_audio, INTERNAL_SR, platform_slug,
            output_lufs=result.output_lufs,
            output_true_peak=result.output_true_peak,
        )
        session["qc_report"] = qc_report

        # RAIN-CERT provenance chain (Stage 15)
        rain_cert = create_rain_cert(
            session_id=session_id,
            source_file_path=session["input_path"],
            output_file_path=result.output_wav_path,
            processing_params={"target_lufs": req.target_lufs, "brightness": req.brightness},
            output_lufs=result.output_lufs,
            output_true_peak=result.output_true_peak,
        )
        session["rain_cert"] = rain_cert

        # C2PA manifest (EU AI Act Article 50)
        c2pa = create_c2pa_manifest(
            title=metadata.get("title", ""),
            artist=metadata.get("artist", ""),
            format="wav",
            rain_cert=rain_cert,
        )
        session["c2pa_manifest"] = c2pa

        session["result"] = result
        session["status"] = "complete"
        session["metadata"] = metadata

        logger.info(
            "mastering_complete",
            session_id=session_id,
            output_lufs=result.output_lufs,
            output_true_peak=result.output_true_peak,
            qc_passed=qc_report.passed,
            qc_checks=len(qc_report.checks),
        )

        return ProcessResponse(
            session_id=session_id,
            status="complete",
            output_lufs=round(result.output_lufs, 1),
            output_true_peak=round(result.output_true_peak, 1),
            output_dynamic_range=round(result.output_dynamic_range, 1),
            output_stereo_width=round(result.output_stereo_width, 3),
            output_spectral_centroid=round(result.output_spectral_centroid, 1),
        )

    except Exception as e:
        session["status"] = "failed"
        logger.error("mastering_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Mastering failed: {e}")


@router.get("/{session_id}/download/{format}")
async def download_file(session_id: str, format: str) -> FileResponse:
    """Download the mastered file as WAV or MP3."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] != "complete":
        raise HTTPException(status_code=400, detail="Mastering not complete")

    result: MasterResult = session["result"]

    if format.lower() == "wav":
        path = result.output_wav_path
        media_type = "audio/wav"
    elif format.lower() == "mp3":
        path = result.output_mp3_path
        media_type = "audio/mpeg"
    else:
        raise HTTPException(status_code=400, detail="Format must be 'wav' or 'mp3'")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Output file not found")

    filename = Path(path).name
    return FileResponse(
        path=path,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{session_id}/features")
async def get_features(session_id: str) -> dict:
    """Get 43-dimensional feature vector for an uploaded session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    features: FeatureVector = session.get("features")
    if not features:
        raise HTTPException(status_code=400, detail="Features not yet extracted")
    return features.to_dict()


@router.get("/{session_id}/cert")
async def get_rain_cert(session_id: str) -> dict:
    """Get RAIN-CERT provenance certificate for a mastered session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    cert: RainCert | None = session.get("rain_cert")
    if not cert:
        raise HTTPException(status_code=400, detail="RAIN-CERT not yet issued (master first)")
    return cert.to_dict()


@router.get("/{session_id}/c2pa")
async def get_c2pa_manifest(session_id: str) -> dict:
    """Get C2PA v2.2 Content Provenance manifest for EU AI Act Article 50 compliance."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    c2pa = session.get("c2pa_manifest")
    if not c2pa:
        raise HTTPException(status_code=400, detail="C2PA manifest not yet generated (master first)")
    return c2pa.to_dict()


@router.get("/{session_id}/qc")
async def get_qc_report(session_id: str) -> dict:
    """Get QC report (18 automated checks) for a mastered session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    qc_report: QCReport | None = session.get("qc_report")
    if not qc_report:
        raise HTTPException(status_code=400, detail="QC not yet run (master first)")
    return qc_report.to_dict()


@router.get("/pubkey")
async def get_signing_pubkey() -> dict:
    """Return the RAIN-CERT Ed25519 public key in PEM format.
    Used for independent signature verification.
    """
    from app.services.provenance import get_public_key_pem
    return {
        "alg": "Ed25519",
        "public_key_pem": get_public_key_pem(),
        "issuer": "ARCOVEL Technologies International",
        "purpose": "RAIN-CERT signature verification",
    }
