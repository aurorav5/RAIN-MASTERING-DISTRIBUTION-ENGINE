"""RainDSP Python bridge.

Prefers pybind11 native extension → subprocess CLI → Python DSP fallback.
On typical deployments (Python-only backend), neither native extension nor CLI
is available, so the Python mastering engine is the actual production path.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
import structlog
from scipy.signal import resample_poly

logger = structlog.get_logger(__name__)


@dataclass
class RenderResult:
    integrated_lufs: float
    short_term_lufs: float
    momentary_lufs: float
    loudness_range: float
    true_peak_dbtp: float
    backend_used: str = "unknown"


def _measure_true_peak(audio: np.ndarray, sr: int) -> float:
    """Measure true peak via 4x oversampling."""
    oversampled = resample_poly(audio, up=4, down=1, axis=0)
    peak_lin = np.max(np.abs(oversampled))
    if peak_lin < 1e-10:
        return -100.0
    return float(20.0 * np.log10(peak_lin))


def _measure_audio(audio: np.ndarray, sr: int, backend: str) -> RenderResult:
    """Measure loudness metrics from audio array."""
    meter = pyln.Meter(sr)
    integrated = meter.integrated_loudness(audio)
    if np.isinf(integrated) or np.isnan(integrated):
        integrated = -70.0

    # Short-term LUFS (3s window) — use last 3 seconds or full duration
    n_short = min(len(audio), int(3.0 * sr))
    short_term = meter.integrated_loudness(audio[-n_short:])
    if np.isinf(short_term) or np.isnan(short_term):
        short_term = integrated

    # Momentary LUFS (400ms window) — use last 400ms
    n_moment = min(len(audio), int(0.4 * sr))
    momentary = meter.integrated_loudness(audio[-n_moment:])
    if np.isinf(momentary) or np.isnan(momentary):
        momentary = integrated

    # Loudness range approximated as difference between quiet and loud sections
    chunk_size = int(3.0 * sr)
    if len(audio) >= chunk_size * 2:
        n_chunks = len(audio) // chunk_size
        chunk_lufs = []
        for i in range(n_chunks):
            chunk = audio[i * chunk_size:(i + 1) * chunk_size]
            cl = meter.integrated_loudness(chunk)
            if np.isfinite(cl):
                chunk_lufs.append(cl)
        loudness_range = max(chunk_lufs) - min(chunk_lufs) if len(chunk_lufs) >= 2 else 0.0
    else:
        loudness_range = 0.0

    true_peak = _measure_true_peak(audio, sr)

    return RenderResult(
        integrated_lufs=round(integrated, 1),
        short_term_lufs=round(short_term, 1),
        momentary_lufs=round(momentary, 1),
        loudness_range=round(loudness_range, 1),
        true_peak_dbtp=round(true_peak, 1),
        backend_used=backend,
    )


class RainDSPBridge:
    """
    Bridge to the RainDSP C++ engine.

    Resolution order:
      1. pybind11 native extension (rain_dsp_native)
      2. Subprocess CLI (rain_dsp_cli)
      3. Python DSP engine (master_engine.py) — the actual server-side production path
    """

    def __init__(self) -> None:
        self._backend = self._detect_backend()
        logger.info("raindsp_bridge_init", backend=self._backend)

    def _detect_backend(self) -> str:
        """Detect which rendering backend is available."""
        try:
            import rain_dsp_native  # type: ignore[import]  # noqa: F401
            return "raindsp_native"
        except ImportError:
            pass

        try:
            result = subprocess.run(
                ["rain_dsp_cli", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return "raindsp_cli"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return "python_dsp"

    def process(self, audio_data: bytes, params: dict) -> tuple[bytes, RenderResult]:
        if self._backend == "raindsp_native":
            return self._process_native(audio_data, params)
        elif self._backend == "raindsp_cli":
            return self._process_subprocess(audio_data, params)
        else:
            return self._process_python(audio_data, params)

    def _process_native(self, audio_data: bytes, params: dict) -> tuple[bytes, RenderResult]:
        """Use pybind11 extension."""
        import rain_dsp_native as rdsp  # type: ignore[import]
        audio, sr = sf.read(io.BytesIO(audio_data), dtype="float64", always_2d=True)
        left = np.ascontiguousarray(audio[:, 0])
        right = np.ascontiguousarray(audio[:, 1] if audio.shape[1] > 1 else audio[:, 0])

        out_left, out_right, result_json = rdsp.process(left, right, sr, json.dumps(params))
        result_dict = json.loads(result_json)

        out_audio = np.stack([out_left, out_right], axis=1)
        buf = io.BytesIO()
        sf.write(buf, out_audio, int(sr), subtype="PCM_24", format="WAV")
        result_dict["backend_used"] = "raindsp_native"
        return buf.getvalue(), RenderResult(**result_dict)

    def _process_subprocess(self, audio_data: bytes, params: dict) -> tuple[bytes, RenderResult]:
        """Subprocess fallback. Requires rain_dsp_cli binary on PATH."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.wav")
            output_path = os.path.join(tmpdir, "output.wav")
            params_path = os.path.join(tmpdir, "params.json")

            with open(input_path, "wb") as f:
                f.write(audio_data)
            with open(params_path, "w") as f:
                json.dump(params, f)

            proc = subprocess.run(
                ["rain_dsp_cli", "--input", input_path, "--output", output_path,
                 "--params", params_path],
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"RAIN-E300: RainDSP subprocess failed: {proc.stderr}")

            result_dict = json.loads(proc.stdout)
            with open(output_path, "rb") as f:
                output_audio = f.read()

        result_dict["backend_used"] = "raindsp_cli"
        return output_audio, RenderResult(**result_dict)

    def _process_python(self, audio_data: bytes, params: dict) -> tuple[bytes, RenderResult]:
        """Python DSP fallback — delegates to the production master_engine."""
        from .master_engine import (
            MasteringParams,
            load_audio_from_buffer,
            normalize_input,
            apply_eq,
            apply_multiband_compression,
            apply_stereo_widening,
            apply_limiter,
            INTERNAL_SR,
        )

        audio, sr = load_audio_from_buffer(audio_data)
        audio = normalize_input(audio, sr)

        mp = MasteringParams(
            brightness=params.get("brightness", 2.0),
            tightness=params.get("tightness", 3.0),
            width=params.get("width", 2.0),
            loudness=params.get("target_lufs", -14.0),
            warmth=params.get("warmth", 0.0),
            punch=params.get("punch", 10.0),
            air=params.get("air", 1.5),
        )

        audio = apply_eq(audio, INTERNAL_SR, mp)
        audio = apply_multiband_compression(audio, INTERNAL_SR, mp)
        audio = apply_stereo_widening(audio, INTERNAL_SR, mp)
        audio = apply_limiter(audio, INTERNAL_SR, mp.loudness)

        # Encode output as 24-bit WAV
        buf = io.BytesIO()
        clipped = np.clip(audio, -1.0, 1.0 - 1.0 / (2 ** 23))
        sf.write(buf, clipped, INTERNAL_SR, subtype="PCM_24", format="WAV")

        result = _measure_audio(audio, INTERNAL_SR, backend="python_dsp")

        logger.info(
            "raindsp_python_fallback_complete",
            integrated_lufs=result.integrated_lufs,
            true_peak_dbtp=result.true_peak_dbtp,
        )

        return buf.getvalue(), result
