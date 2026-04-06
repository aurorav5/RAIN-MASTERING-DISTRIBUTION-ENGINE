"""AudioSeal (Meta) watermarking wrapper for RAIN.

AudioSeal is a neural audio watermarking system from Meta AI Research that
provides ~90-100% detection rate and survives common compression + re-encoding
(MP3/AAC/Opus) while remaining perceptually transparent. Each watermark
carries a 16-bit payload that can encode a session-derived message ID.

The `audioseal` PyPI package is NOT yet declared in requirements.txt — per the
RAIN blueprint, package addition is deferred to a later phase. This module
attempts a lazy import and raises RAIN-E742 if unavailable so the pipeline
can degrade gracefully (warn + continue) in tasks/provenance.py.

Supported input: stereo (or mono) samples at 44.1 or 48 kHz, float32 in [-1, 1].
"""
from __future__ import annotations
import hashlib
from typing import Optional

import numpy as np
import structlog

logger = structlog.get_logger()

_SUPPORTED_SR = (44100, 48000)


def _derive_message(session_hash: str, key_seed: str) -> int:
    """Derive a deterministic 16-bit message from session_hash + key_seed."""
    h = hashlib.sha256(f"{key_seed}:{session_hash}".encode()).digest()
    return int.from_bytes(h[:2], "big") & 0xFFFF


def _load_audioseal():
    """Lazy-import AudioSeal; raise RAIN-E742 with guidance if missing."""
    try:
        from audioseal import AudioSeal  # type: ignore
        return AudioSeal
    except ImportError as e:
        raise RuntimeError(
            "RAIN-E742: AudioSeal package not installed. "
            "Install via `pip install audioseal` to enable watermarking. "
            f"Underlying: {e}"
        )


def embed_watermark(
    samples: np.ndarray,
    sample_rate: int,
    message: Optional[int] = None,
    session_hash: Optional[str] = None,
    key_seed: Optional[str] = None,
) -> np.ndarray:
    """Embed an AudioSeal watermark into the given samples.

    Args:
      samples: float32 numpy array, shape (n_samples,) or (n_channels, n_samples).
      sample_rate: 44100 or 48000.
      message: 16-bit int payload; if None, derived from session_hash + key_seed.
      session_hash: used to derive message when message is None.
      key_seed: used to derive message when message is None (defaults to settings.AUDIOSEAL_KEY_SEED).

    Returns: watermarked samples, same shape/dtype as input.

    Raises: RuntimeError RAIN-E742 if AudioSeal is unavailable.
    """
    if sample_rate not in _SUPPORTED_SR:
        raise ValueError(
            f"RAIN-E742: unsupported sample_rate {sample_rate}; must be one of {_SUPPORTED_SR}"
        )

    AudioSeal = _load_audioseal()
    import torch  # type: ignore

    if message is None:
        from app.core.config import settings
        seed = key_seed or getattr(settings, "AUDIOSEAL_KEY_SEED", "rain-default-seed")
        sh = session_hash or "no-session"
        message = _derive_message(sh, seed)

    # Normalize shape to (batch=1, channels, n_samples) for AudioSeal
    if samples.ndim == 1:
        wav = torch.from_numpy(samples.astype(np.float32)).unsqueeze(0).unsqueeze(0)
        out_1d = True
        n_channels = 1
    elif samples.ndim == 2:
        # AudioSeal expects channels-first
        wav = torch.from_numpy(samples.astype(np.float32)).unsqueeze(0)
        out_1d = False
        n_channels = samples.shape[0]
    else:
        raise ValueError(f"RAIN-E742: samples must be 1D or 2D, got shape {samples.shape}")

    try:
        model = AudioSeal.load_generator("audioseal_wm_16bits")
        # Pack 16-bit message into a 16-element bit tensor
        bits = torch.tensor(
            [[(message >> i) & 1 for i in range(16)]], dtype=torch.int32
        )
        watermarked = model(wav, sample_rate=sample_rate, message=bits, alpha=1.0)
        wm_samples = watermarked.squeeze(0).cpu().numpy().astype(samples.dtype)
        if out_1d:
            wm_samples = wm_samples.squeeze(0)
        logger.info(
            "audioseal_embedded",
            sample_rate=sample_rate,
            n_channels=n_channels,
            message=message,
            stage="provenance",
        )
        return wm_samples
    except Exception as e:
        raise RuntimeError(f"RAIN-E742: AudioSeal embed failed: {e}") from e


def detect_watermark(
    samples: np.ndarray,
    sample_rate: int,
) -> tuple[bool, Optional[int], float]:
    """Detect an AudioSeal watermark and recover its 16-bit message.

    Returns: (detected, message, confidence)
      - detected: True if watermark probability > 0.5
      - message: recovered 16-bit int payload, or None if not detected
      - confidence: probability in [0.0, 1.0]

    Raises: RuntimeError RAIN-E742 if AudioSeal is unavailable.
    """
    if sample_rate not in _SUPPORTED_SR:
        raise ValueError(
            f"RAIN-E742: unsupported sample_rate {sample_rate}; must be one of {_SUPPORTED_SR}"
        )

    AudioSeal = _load_audioseal()
    import torch  # type: ignore

    if samples.ndim == 1:
        wav = torch.from_numpy(samples.astype(np.float32)).unsqueeze(0).unsqueeze(0)
    elif samples.ndim == 2:
        wav = torch.from_numpy(samples.astype(np.float32)).unsqueeze(0)
    else:
        raise ValueError(f"RAIN-E742: samples must be 1D or 2D, got shape {samples.shape}")

    try:
        detector = AudioSeal.load_detector("audioseal_detector_16bits")
        result, msg_probs = detector.detect_watermark(wav, sample_rate=sample_rate)
        confidence = float(result)
        detected = confidence > 0.5
        if detected:
            # msg_probs is shape (1, 16); threshold at 0.5 per bit
            bits = (msg_probs.squeeze(0) > 0.5).int().tolist()
            message = 0
            for i, b in enumerate(bits):
                message |= (int(b) & 1) << i
            return True, message, confidence
        return False, None, confidence
    except Exception as e:
        raise RuntimeError(f"RAIN-E742: AudioSeal detect failed: {e}") from e
