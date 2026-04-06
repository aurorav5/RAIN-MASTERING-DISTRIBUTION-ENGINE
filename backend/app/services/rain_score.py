"""RAIN Score — composite 0-100 quality metric. Weights: 40+20+20+10+10=100."""
from __future__ import annotations
import numpy as np
from typing import Optional
import structlog

logger = structlog.get_logger()

# Platform targets (authoritative — mirrors heuristics.py)
PLATFORM_TARGETS: dict[str, dict] = {
    "spotify":      {"lufs": -14.0, "tp_max": -1.0, "codec": "ogg_q9"},
    "apple_music":  {"lufs": -16.0, "tp_max": -1.0, "codec": "aac_256"},
    "youtube":      {"lufs": -14.0, "tp_max": -1.0, "codec": "aac_128"},
    "tidal":        {"lufs": -14.0, "tp_max": -1.0, "codec": "flac"},
    "amazon_music": {"lufs": -14.0, "tp_max": -1.0, "codec": "aac_256"},
    "tiktok":       {"lufs": -14.0, "tp_max": -1.0, "codec": "aac_128"},
    "soundcloud":   {"lufs": -14.0, "tp_max": -1.0, "codec": "ogg_128"},
}


def _compute_measurements_sync(audio_data: bytes) -> tuple[float, float, float]:
    """Synchronous measurement — runs in thread pool off the event loop."""
    import soundfile as sf
    import pyloudnorm as pyln
    import io

    audio_arr, sr = sf.read(io.BytesIO(audio_data), dtype="float64", always_2d=True)
    meter = pyln.Meter(sr)
    lufs = float(meter.integrated_loudness(audio_arr))
    tp_lin = float(np.max(np.abs(audio_arr)))
    tp = 20.0 * np.log10(tp_lin) if tp_lin > 0 else -120.0

    if audio_arr.shape[1] >= 2:
        corr = float(np.corrcoef(audio_arr[:, 0], audio_arr[:, 1])[0, 1])
        stereo_score = float(np.clip((1.0 - abs(corr)) * 10.0 + 5.0, 0.0, 10.0))
    else:
        stereo_score = 5.0
    return lufs, tp, stereo_score


async def compute_rain_score(
    audio_data: bytes,
    primary_platform: str,
    mel: Optional[np.ndarray] = None,
) -> dict:
    """
    Compute RAIN Score: 0-100 composite quality metric.
    Heavy numpy/soundfile work offloaded to thread pool (P1-3.7 fix).
    """
    import asyncio

    lufs, tp, stereo_score = await asyncio.to_thread(
        _compute_measurements_sync, audio_data
    )

    scores: dict[str, int] = {}
    for platform, target in PLATFORM_TARGETS.items():
        # Loudness compliance (0-40): 10pts per LU deviation
        lufs_delta = abs(lufs - target["lufs"])
        loudness_score = max(0.0, 40.0 - lufs_delta * 10.0)

        # True peak headroom (0-20): 10pts per dB over ceiling
        tp_margin = target["tp_max"] - tp
        tp_score = 20.0 if tp_margin >= 0.0 else max(0.0, 20.0 + tp_margin * 10.0)

        # Codec penalty (0-20): estimates lossy encoding damage from mel high-freq content
        codec_penalty = _estimate_codec_penalty(mel, platform) if mel is not None else 3.0
        codec_score = max(0.0, 20.0 - codec_penalty * 4.0)

        # Spectral balance (0-10): variance of per-band energy
        spectral_score = _estimate_spectral_balance(mel) if mel is not None else 7.0

        platform_total = loudness_score + tp_score + codec_score + spectral_score + stereo_score
        scores[platform] = round(min(100.0, platform_total))

    overall = round(sum(scores.values()) / len(scores))
    return {
        "overall": overall,
        "integrated_lufs": round(lufs, 2),
        "true_peak_dbtp": round(tp, 2),
        **scores,
    }


_codec_ort_session = None

_PLATFORM_IDS: dict[str, int] = {
    "spotify": 0, "apple_music": 1, "youtube": 2, "tidal": 3,
    "amazon_music": 4, "tiktok": 5, "soundcloud": 6, "broadcast": 7,
}


def _estimate_codec_penalty(mel: np.ndarray, platform: str) -> float:
    """
    Estimate codec quality loss (0-5 scale).

    If CODEC_NET_ENABLED and the ONNX checkpoint is loaded, uses CodecNet inference.
    Otherwise falls back to the high-frequency energy heuristic (deterministic).
    """
    from app.core.config import settings

    if getattr(settings, "CODEC_NET_ENABLED", False):
        penalty = _codecnet_inference(mel, platform)
        if penalty is not None:
            return penalty

    # Heuristic fallback (deterministic for same mel + platform)
    logger.debug("codec_penalty_heuristic", platform=platform, stage="rain_score")
    high_freq_energy = float(mel[-16:].mean()) if mel is not None else 0.3
    if platform in ("tiktok", "soundcloud", "youtube"):
        return min(5.0, high_freq_energy * 3.0)
    if platform in ("spotify", "amazon_music"):
        return min(2.5, high_freq_energy * 1.5)
    return min(1.0, high_freq_energy * 0.5)  # flac/high-quality


def _codecnet_inference(mel: np.ndarray, platform: str) -> Optional[float]:
    """Run CodecNet ONNX inference. Returns penalty float or None on failure."""
    global _codec_ort_session

    if _codec_ort_session is None:
        from pathlib import Path
        ckpt = Path("ml/checkpoints/codec_net.onnx")
        if not ckpt.exists():
            logger.info("codecnet_checkpoint_missing", path=str(ckpt))
            return None
        try:
            import onnxruntime as ort
            _codec_ort_session = ort.InferenceSession(
                str(ckpt), providers=["CPUExecutionProvider"]
            )
        except Exception as e:
            logger.error("codecnet_load_failed", error=str(e), error_code="RAIN-E401")
            return None

    try:
        mel_input = np.array(mel, dtype=np.float32)
        if mel_input.ndim == 2:
            mel_input = mel_input[np.newaxis, np.newaxis, :128, :128]

        # Pad if needed
        if mel_input.shape[2] < 128 or mel_input.shape[3] < 128:
            padded = np.zeros((1, 1, 128, 128), dtype=np.float32)
            h, w = min(128, mel_input.shape[2]), min(128, mel_input.shape[3])
            padded[0, 0, :h, :w] = mel_input[0, 0, :h, :w]
            mel_input = padded

        platform_id = np.array([_PLATFORM_IDS.get(platform, 0)], dtype=np.int64)
        inputs = _codec_ort_session.get_inputs()
        output = _codec_ort_session.run(
            None,
            {inputs[0].name: mel_input, inputs[1].name: platform_id},
        )
        # Output: [B, 8, 8] — mean across bands for this platform
        pid = _PLATFORM_IDS.get(platform, 0)
        penalty = float(np.clip(output[0][0, :, pid].mean() * 5.0, 0.0, 5.0))

        logger.info("codecnet_inference_ok", platform=platform, penalty=round(penalty, 2))
        return penalty

    except Exception as e:
        logger.error("codecnet_inference_failed", error=str(e), error_code="RAIN-E401")
        return None


def _estimate_spectral_balance(mel: np.ndarray) -> float:
    """
    Score spectral balance 0-10. Well-balanced = energy distributed across spectrum.
    Uses variance of per-octave band energies.
    """
    if mel is None:
        return 7.0
    band_energies = [float(mel[i * 16:(i + 1) * 16].mean()) for i in range(8)]
    variance = float(np.var(band_energies))
    return float(max(0.0, 10.0 - variance * 20.0))
