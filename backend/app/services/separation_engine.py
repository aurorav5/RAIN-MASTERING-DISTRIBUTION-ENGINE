"""BS-RoFormer cascaded separation engine — real inference via ZFTurbo packages.

Uses:
  - `bs-roformer-infer` for Pass 1 (6-stem BS-RoFormer SW)
  - `melband-roformer-infer` for Pass 2 (karaoke vocal split) + Pass 4 (dereverb)
  - For Pass 3 (drum sub-separation): spectral method fallback until LarsNet is available

Model checkpoints are auto-managed by the pip packages' MODEL_REGISTRY.
No manual download needed — first inference triggers the download.

Expected tensor conventions
---------------------------
All audio buffers: numpy float32, shape (channels, samples), 44100 Hz.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import structlog
import torch

from app.core.config import settings

logger = structlog.get_logger()

_SR_EXPECTED = 44100

# Model registry slugs (from openmirlab packages)
_BS_ROFORMER_SW_SLUG = "roformer-model-bs-roformer-sw-by-jarredou"
_KARAOKE_SLUG = "roformer-model-mel-roformer-karaoke-aufr33-viperx"
_DEREVERB_SLUG = "roformer-model-melband-roformer-de-reverb-by-anvuew"


def _get_device() -> torch.device:
    device_str = settings.BSROFORMER_DEVICE
    if device_str.startswith("cuda") and not torch.cuda.is_available():
        logger.warning("separation_cuda_unavailable", fallback="cpu")
        return torch.device("cpu")
    return torch.device(device_str)


def _assert_enabled(error_code: str, detail: str) -> None:
    if not settings.SEPARATION_ENABLED:
        raise RuntimeError(
            f"{error_code}: Separation disabled — set SEPARATION_ENABLED=true ({detail})"
        )


# ---------------------------------------------------------------------------
# Model loading — uses the package registries for auto-download
# ---------------------------------------------------------------------------

def load_bsroformer_model(checkpoint_path: str | None = None, device: str | None = None) -> dict:
    """Load BS-RoFormer SW 6-stem model. Returns a dict with model + config + device.

    If checkpoint_path is None, uses the auto-managed registry checkpoint.
    """
    _assert_enabled("RAIN-E620", "load_bsroformer_model")

    try:
        from bs_roformer import MODEL_REGISTRY, get_model_from_config
        from ml_collections import ConfigDict
        import yaml

        dev = torch.device(device or settings.BSROFORMER_DEVICE)
        if dev.type == "cuda" and not torch.cuda.is_available():
            dev = torch.device("cpu")

        entry = MODEL_REGISTRY.get(_BS_ROFORMER_SW_SLUG)
        config_path = Path(f"models/{entry.slug}/{entry.config}")
        ckpt_path = Path(checkpoint_path or f"models/{entry.slug}/{entry.checkpoint}")

        if not config_path.exists() or not ckpt_path.exists():
            # Trigger auto-download via registry
            logger.info("separation_downloading_model", slug=_BS_ROFORMER_SW_SLUG)
            MODEL_REGISTRY.download(_BS_ROFORMER_SW_SLUG)

        with open(config_path) as f:
            config = ConfigDict(yaml.safe_load(f))

        model = get_model_from_config("bs_roformer", config)
        state_dict = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
        model.load_state_dict(state_dict)
        model = model.to(dev).eval()

        logger.info("bsroformer_loaded", slug=_BS_ROFORMER_SW_SLUG, device=str(dev))
        return {"model": model, "config": config, "device": dev, "model_type": "bs_roformer"}

    except ImportError as e:
        raise RuntimeError(
            f"RAIN-E620: bs-roformer-infer not installed — pip install bs-roformer-infer ({e})"
        ) from e


def load_karaoke_model(device: str | None = None) -> dict:
    """Load MVSep Karaoke MelBand RoFormer for vocal lead/backing split."""
    _assert_enabled("RAIN-E620", "load_karaoke_model")

    try:
        from mel_band_roformer import MODEL_REGISTRY, get_model_from_config
        from ml_collections import ConfigDict
        import yaml

        dev = torch.device(device or settings.BSROFORMER_DEVICE)
        if dev.type == "cuda" and not torch.cuda.is_available():
            dev = torch.device("cpu")

        entry = MODEL_REGISTRY.get(_KARAOKE_SLUG)
        config_path = Path(f"models/{entry.slug}/{entry.config}")
        ckpt_path = Path(f"models/{entry.slug}/{entry.checkpoint}")

        if not config_path.exists() or not ckpt_path.exists():
            logger.info("separation_downloading_model", slug=_KARAOKE_SLUG)
            MODEL_REGISTRY.download(_KARAOKE_SLUG)

        with open(config_path) as f:
            config = ConfigDict(yaml.safe_load(f))

        model = get_model_from_config("mel_band_roformer", config)
        state_dict = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
        model.load_state_dict(state_dict)
        model = model.to(dev).eval()

        logger.info("karaoke_model_loaded", slug=_KARAOKE_SLUG, device=str(dev))
        return {"model": model, "config": config, "device": dev, "model_type": "mel_band_roformer"}

    except ImportError as e:
        raise RuntimeError(
            f"RAIN-E620: melband-roformer-infer not installed — pip install melband-roformer-infer ({e})"
        ) from e


def load_dereverb_model(device: str | None = None) -> dict:
    """Load anvuew dereverb MelBand RoFormer."""
    _assert_enabled("RAIN-E620", "load_dereverb_model")

    try:
        from mel_band_roformer import MODEL_REGISTRY, get_model_from_config
        from ml_collections import ConfigDict
        import yaml

        dev = torch.device(device or settings.BSROFORMER_DEVICE)
        if dev.type == "cuda" and not torch.cuda.is_available():
            dev = torch.device("cpu")

        entry = MODEL_REGISTRY.get(_DEREVERB_SLUG)
        config_path = Path(f"models/{entry.slug}/{entry.config}")
        ckpt_path = Path(f"models/{entry.slug}/{entry.checkpoint}")

        if not config_path.exists() or not ckpt_path.exists():
            logger.info("separation_downloading_model", slug=_DEREVERB_SLUG)
            MODEL_REGISTRY.download(_DEREVERB_SLUG)

        with open(config_path) as f:
            config = ConfigDict(yaml.safe_load(f))

        model = get_model_from_config("mel_band_roformer", config)
        state_dict = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
        model.load_state_dict(state_dict)
        model = model.to(dev).eval()

        logger.info("dereverb_model_loaded", slug=_DEREVERB_SLUG, device=str(dev))
        return {"model": model, "config": config, "device": dev, "model_type": "mel_band_roformer"}

    except ImportError as e:
        raise RuntimeError(
            f"RAIN-E620: melband-roformer-infer not installed — pip install melband-roformer-infer ({e})"
        ) from e


# ---------------------------------------------------------------------------
# Inference passes
# ---------------------------------------------------------------------------

def _demix(handle: dict, audio: np.ndarray, sr: int) -> dict[str, np.ndarray]:
    """Run ZFTurbo-style demix on audio. Returns dict of stem_name → ndarray."""
    from utils.model_utils import demix  # from Music-Source-Separation-Training

    assert sr == _SR_EXPECTED, f"Expected {_SR_EXPECTED} Hz, got {sr}"
    if audio.ndim == 1:
        audio = np.stack([audio, audio])  # mono → stereo

    with torch.no_grad():
        waveforms = demix(
            handle["config"],
            handle["model"],
            audio,
            handle["device"],
            model_type=handle["model_type"],
            pbar=False,
        )
    return waveforms


def run_pass_1_6stem(handle: dict, audio: np.ndarray, sr: int) -> dict[str, np.ndarray]:
    """Pass 1 — BS-RoFormer SW → 6 stems: vocals, drums, bass, guitar, piano, other."""
    _assert_enabled("RAIN-E621", "run_pass_1_6stem")

    t0 = time.monotonic()
    stems = _demix(handle, audio, sr)
    elapsed_ms = (time.monotonic() - t0) * 1000

    # Normalize stem names to canonical
    canonical = {}
    for key, val in stems.items():
        name = key.lower().strip()
        if name in ("vocals", "drums", "bass", "guitar", "piano", "other"):
            canonical[name] = val

    logger.info(
        "pass_1_6stem_complete",
        stems=list(canonical.keys()),
        duration_ms=round(elapsed_ms),
        stage="separation",
    )
    return canonical


def run_pass_2_karaoke(
    handle: dict, vocals: np.ndarray, sr: int
) -> tuple[np.ndarray, np.ndarray]:
    """Pass 2 — Karaoke model splits vocals into lead + backing."""
    _assert_enabled("RAIN-E621", "run_pass_2_karaoke")

    t0 = time.monotonic()
    stems = _demix(handle, vocals, sr)
    elapsed_ms = (time.monotonic() - t0) * 1000

    # Karaoke model typically outputs "vocals" (lead) and "other" (backing/instrumental)
    lead = stems.get("vocals", stems.get("lead", vocals))
    backing = stems.get("other", stems.get("backing", np.zeros_like(vocals)))

    logger.info("pass_2_karaoke_complete", duration_ms=round(elapsed_ms), stage="separation")
    return lead, backing


def run_pass_3_drums(handle: Any, drums: np.ndarray, sr: int) -> dict[str, np.ndarray]:
    """Pass 3 — Split drum bus into kick, snare, hats, percussion.

    Until LarsNet is available as a pip package, uses spectral band splitting
    as a reasonable approximation for drum sub-separation.
    """
    _assert_enabled("RAIN-E621", "run_pass_3_drums")

    t0 = time.monotonic()

    # Spectral band splitting fallback (no ML model needed)
    # This is a placeholder until LarsNet is pip-installable
    from scipy.signal import butter, sosfilt

    def bandpass(audio_mono: np.ndarray, low: float, high: float, sr: int) -> np.ndarray:
        sos = butter(4, [low, high], btype="band", fs=sr, output="sos")
        return sosfilt(sos, audio_mono).astype(np.float32)

    def lowpass(audio_mono: np.ndarray, freq: float, sr: int) -> np.ndarray:
        sos = butter(4, freq, btype="low", fs=sr, output="sos")
        return sosfilt(sos, audio_mono).astype(np.float32)

    def highpass(audio_mono: np.ndarray, freq: float, sr: int) -> np.ndarray:
        sos = butter(4, freq, btype="high", fs=sr, output="sos")
        return sosfilt(sos, audio_mono).astype(np.float32)

    result: dict[str, np.ndarray] = {}
    for ch_idx in range(min(drums.shape[0], 2)):
        ch = drums[ch_idx]
        kick_ch = lowpass(ch, 200, sr)
        snare_ch = bandpass(ch, 200, 5000, sr)
        hats_ch = highpass(ch, 5000, sr)
        # Percussion = residual
        perc_ch = ch - kick_ch - snare_ch - hats_ch

        for name, data in [("kick", kick_ch), ("snare", snare_ch), ("hats", hats_ch), ("percussion", perc_ch)]:
            if name not in result:
                result[name] = np.zeros((drums.shape[0], drums.shape[1]), dtype=np.float32)
            result[name][ch_idx] = data

    elapsed_ms = (time.monotonic() - t0) * 1000
    logger.info(
        "pass_3_drums_complete",
        method="spectral_bandpass_fallback",
        duration_ms=round(elapsed_ms),
        stage="separation",
        note="LarsNet integration pending — using frequency-band approximation",
    )
    return result


def run_pass_4_dereverb(
    handle: dict, other: np.ndarray, sr: int
) -> tuple[np.ndarray, np.ndarray]:
    """Pass 4 — anvuew dereverb MelBand RoFormer extracts room/ambience.

    Returns (room, fx_other) where fx_other = other - room (dry residual).
    """
    _assert_enabled("RAIN-E621", "run_pass_4_dereverb")

    t0 = time.monotonic()
    stems = _demix(handle, other, sr)
    elapsed_ms = (time.monotonic() - t0) * 1000

    # Dereverb model outputs "vocals" (dry signal) and "other" (reverb/room)
    # OR "noreverb" and "reverb" depending on config
    dry = stems.get("noreverb", stems.get("vocals", stems.get("dry", other)))
    room = stems.get("reverb", stems.get("other", stems.get("room", np.zeros_like(other))))

    # fx_other is the dry residual (everything except room)
    fx_other = dry

    logger.info("pass_4_dereverb_complete", duration_ms=round(elapsed_ms), stage="separation")
    return room, fx_other
