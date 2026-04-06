"""Audio fingerprinting utilities for RAIN provenance pipeline.

Chromaprint fingerprints give a compact, acoustically-robust identifier that
survives re-encoding, loudness changes, and minor edits — useful for matching
a distributed track back to its RAIN session even if C2PA manifest is stripped.

Target: <100ms on typical 3-minute, 48 kHz stereo input using the native
chromaprint C library via the `acoustid` Python binding.

The `acoustid` / `chromaprint` packages are NOT yet declared in requirements.txt
— per the RAIN blueprint, package addition is deferred. This module attempts a
lazy import and raises RAIN-E743 if unavailable so the pipeline can degrade
gracefully (warn + continue) in tasks/provenance.py.
"""
from __future__ import annotations
import hashlib

import numpy as np
import structlog

logger = structlog.get_logger()


def compute_chromaprint(samples: np.ndarray, sample_rate: int) -> str:
    """Compute an AcoustID/Chromaprint fingerprint string.

    Args:
      samples: int16 or float32 numpy array, mono or stereo.
      sample_rate: e.g. 44100 or 48000.

    Returns: chromaprint fingerprint as a base64-like compact string.

    Raises: RuntimeError RAIN-E743 if chromaprint/acoustid is unavailable.
    """
    try:
        import acoustid  # type: ignore
        import chromaprint  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "RAIN-E743: chromaprint/acoustid package not installed. "
            "Install via `pip install pyacoustid` and ensure libchromaprint "
            f"is on the system. Underlying: {e}"
        )

    try:
        # Convert to int16 mono PCM for chromaprint
        if samples.ndim == 2:
            # Downmix to mono
            mono = samples.mean(axis=0) if samples.shape[0] <= 2 else samples.mean(axis=-1)
        else:
            mono = samples

        if mono.dtype != np.int16:
            mono_i16 = np.clip(mono * 32767.0, -32768, 32767).astype(np.int16)
        else:
            mono_i16 = mono

        fp_gen = chromaprint.Fingerprinter(
            {"sample_rate": sample_rate, "num_channels": 1}
        )
        fp_gen.feed(mono_i16.tobytes())
        fingerprint = fp_gen.finish()
        fp_str = fingerprint if isinstance(fingerprint, str) else fingerprint.decode("ascii", errors="replace")
        logger.info(
            "chromaprint_computed",
            sample_rate=sample_rate,
            fp_len=len(fp_str),
            stage="provenance",
        )
        return fp_str
    except Exception as e:
        raise RuntimeError(f"RAIN-E743: chromaprint compute failed: {e}") from e


def compute_sha256(audio_bytes: bytes) -> str:
    """Compute SHA-256 hex digest of raw audio bytes."""
    return hashlib.sha256(audio_bytes).hexdigest()
