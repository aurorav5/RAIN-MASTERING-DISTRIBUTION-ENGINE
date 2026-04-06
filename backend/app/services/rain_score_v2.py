"""
RAIN Score v2 — Composite Quality + Emotional Impact Metric

The original RAIN Score measured technical compliance:
  Loudness(40) + TruePeak(20) + Codec(20) + Spectral(10) + Stereo(10) = 100

RAIN Score v2 adds:
  - Emotional Impact proxy (energy arc, tension, release detection)
  - Dynamic Integrity (crest factor preservation, micro-dynamics)
  - Translation Score (how well the master translates across playback systems)

Total: Technical(60) + Dynamic(15) + Translation(10) + Emotional(15) = 100

This is what users see and care about. It's the single number that tells them
"is my master ready to release?"
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# Platform targets
PLATFORM_TARGETS: dict[str, dict] = {
    "spotify":      {"lufs": -14.0, "tp_max": -1.0},
    "apple_music":  {"lufs": -16.0, "tp_max": -1.0},
    "youtube":      {"lufs": -14.0, "tp_max": -1.0},
    "tidal":        {"lufs": -14.0, "tp_max": -1.0},
    "amazon_music": {"lufs": -14.0, "tp_max": -1.0},
    "tiktok":       {"lufs": -14.0, "tp_max": -1.0},
    "soundcloud":   {"lufs": -14.0, "tp_max": -1.0},
}


@dataclass
class ScoreBreakdown:
    """Detailed RAIN Score breakdown — this is what the UI displays."""
    # Overall
    overall: int = 0

    # Technical (max 60)
    loudness: float = 0.0        # LUFS compliance (max 25)
    true_peak: float = 0.0       # True peak headroom (max 15)
    spectral: float = 0.0        # Spectral balance (max 10)
    stereo: float = 0.0          # Stereo field quality (max 10)

    # Dynamic Integrity (max 15)
    crest_preservation: float = 0.0    # How much crest factor was preserved (max 8)
    micro_dynamics: float = 0.0        # Short-term loudness variance (max 7)

    # Translation (max 10)
    mono_compat: float = 0.0     # Mono fold-down quality (max 5)
    codec_resilience: float = 0.0  # Estimated lossy codec survival (max 5)

    # Emotional Impact (max 15)
    energy_arc: float = 0.0      # Does the track build and release? (max 5)
    tension_index: float = 0.0   # Dynamic contrast / tension (max 5)
    presence: float = 0.0        # Vocal/lead presence clarity (max 5)

    # Per-platform scores
    platform_scores: dict[str, int] = field(default_factory=dict)

    # Verdict
    verdict: str = ""
    release_ready: bool = False


def _compute_score_sync(
    audio: np.ndarray,
    sr: int,
    input_audio: Optional[np.ndarray] = None,
    input_sr: Optional[int] = None,
    primary_platform: str = "spotify",
) -> ScoreBreakdown:
    """
    Synchronous RAIN Score v2 computation.
    Runs in thread pool — no event loop blocking.
    """
    import pyloudnorm as pyln
    from scipy.signal import resample_poly

    score = ScoreBreakdown()

    # Ensure stereo
    if audio.ndim == 1:
        audio = np.column_stack([audio, audio])

    # --- LUFS measurement ---
    meter = pyln.Meter(sr)
    lufs = meter.integrated_loudness(audio)
    if not np.isfinite(lufs):
        lufs = -70.0

    # --- True peak ---
    oversampled = resample_poly(audio, up=4, down=1, axis=0)
    tp_linear = float(np.max(np.abs(oversampled)))
    tp_db = 20.0 * np.log10(tp_linear) if tp_linear > 1e-10 else -100.0

    # --- Technical: Loudness (max 25) ---
    target = PLATFORM_TARGETS.get(primary_platform, {"lufs": -14.0, "tp_max": -1.0})
    lufs_delta = abs(lufs - target["lufs"])
    score.loudness = max(0.0, 25.0 - lufs_delta * 8.0)

    # --- Technical: True Peak (max 15) ---
    tp_margin = target["tp_max"] - tp_db
    score.true_peak = 15.0 if tp_margin >= 0.0 else max(0.0, 15.0 + tp_margin * 8.0)

    # --- Technical: Spectral Balance (max 10) ---
    mono = np.mean(audio, axis=1)
    n_fft = min(8192, len(mono))
    if n_fft > 256:
        spectrum = np.abs(np.fft.rfft(mono[:n_fft])) ** 2
        # Divide into 8 octave-ish bands and measure variance
        n_bins = len(spectrum)
        band_size = n_bins // 8
        band_energies = []
        for i in range(8):
            start = i * band_size
            end = start + band_size if i < 7 else n_bins
            band_energies.append(float(np.mean(spectrum[start:end])))
        if max(band_energies) > 0:
            normalized = [e / max(band_energies) for e in band_energies]
            variance = float(np.var(normalized))
            score.spectral = max(0.0, 10.0 - variance * 30.0)
        else:
            score.spectral = 5.0
    else:
        score.spectral = 5.0

    # --- Technical: Stereo (max 10) ---
    if audio.shape[1] >= 2:
        corr = float(np.corrcoef(audio[:, 0], audio[:, 1])[0, 1])
        # Ideal: moderate correlation (0.3-0.8). Too high = mono, too low = phase issues
        if 0.3 <= corr <= 0.8:
            score.stereo = 10.0
        elif corr > 0.8:
            score.stereo = 10.0 - (corr - 0.8) * 20.0
        else:
            score.stereo = max(0.0, 10.0 - (0.3 - corr) * 15.0)
    else:
        score.stereo = 5.0

    # --- Dynamic Integrity: Crest Preservation (max 8) ---
    output_rms = float(np.sqrt(np.mean(audio ** 2)))
    output_peak = float(np.max(np.abs(audio)))
    output_crest = 20.0 * np.log10(output_peak / (output_rms + 1e-10))

    if input_audio is not None:
        input_rms = float(np.sqrt(np.mean(input_audio ** 2)))
        input_peak = float(np.max(np.abs(input_audio)))
        input_crest = 20.0 * np.log10(input_peak / (input_rms + 1e-10))
        # How much crest factor was preserved? (ratio, 1.0 = perfect)
        crest_ratio = min(1.0, output_crest / (input_crest + 1e-10))
        score.crest_preservation = crest_ratio * 8.0
    else:
        # Without input reference, score based on absolute crest factor
        # Good masters: 8-14 dB crest factor
        if 8.0 <= output_crest <= 14.0:
            score.crest_preservation = 8.0
        elif output_crest < 8.0:
            score.crest_preservation = max(0.0, output_crest)
        else:
            score.crest_preservation = max(0.0, 8.0 - (output_crest - 14.0))

    # --- Dynamic Integrity: Micro-dynamics (max 7) ---
    # Measure short-term loudness variance (3s windows)
    window_samples = int(3.0 * sr)
    if len(mono) > window_samples * 2:
        st_values = []
        for start in range(0, len(mono) - window_samples, window_samples // 3):
            chunk = mono[start:start + window_samples]
            chunk_rms = float(np.sqrt(np.mean(chunk ** 2)))
            if chunk_rms > 1e-10:
                st_values.append(20.0 * np.log10(chunk_rms))
        if st_values:
            st_variance = float(np.var(st_values))
            # Good variance: 2-8 dB² (not flat, not chaotic)
            if 2.0 <= st_variance <= 8.0:
                score.micro_dynamics = 7.0
            elif st_variance < 2.0:
                score.micro_dynamics = max(0.0, st_variance * 3.5)
            else:
                score.micro_dynamics = max(0.0, 7.0 - (st_variance - 8.0) * 0.5)
        else:
            score.micro_dynamics = 3.5
    else:
        score.micro_dynamics = 3.5

    # --- Translation: Mono Compatibility (max 5) ---
    if audio.shape[1] >= 2:
        mono_sum = audio[:, 0] + audio[:, 1]
        stereo_energy = float(np.sum(audio ** 2))
        mono_energy = float(np.sum(mono_sum ** 2))
        mono_ratio = mono_energy / (stereo_energy + 1e-10)
        # >0.8 = great, <0.5 = phase issues
        score.mono_compat = min(5.0, mono_ratio * 5.0)
    else:
        score.mono_compat = 5.0

    # --- Translation: Codec Resilience (max 5) ---
    # High-frequency energy above 16kHz = more codec damage
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr) if n_fft > 256 else np.array([0])
    if len(freqs) > 1 and n_fft > 256:
        spectrum_full = np.abs(np.fft.rfft(mono[:n_fft])) ** 2
        hf_mask = freqs > 16000
        hf_ratio = float(np.sum(spectrum_full[hf_mask])) / (float(np.sum(spectrum_full)) + 1e-10)
        # Less HF energy = better codec survival
        score.codec_resilience = max(0.0, 5.0 - hf_ratio * 50.0)
    else:
        score.codec_resilience = 3.0

    # --- Emotional Impact: Energy Arc (max 5) ---
    # Does the track have dynamic shape? (builds, drops, crescendos)
    if len(mono) > sr * 10:
        # Divide track into 8 segments, measure RMS arc
        seg_len = len(mono) // 8
        seg_rms = []
        for i in range(8):
            seg = mono[i * seg_len:(i + 1) * seg_len]
            seg_rms.append(float(np.sqrt(np.mean(seg ** 2))))
        if max(seg_rms) > 0:
            normalized_arc = [r / max(seg_rms) for r in seg_rms]
            # Good arc: variance > 0.01 (not flat)
            arc_variance = float(np.var(normalized_arc))
            score.energy_arc = min(5.0, arc_variance * 100.0)
        else:
            score.energy_arc = 2.0
    else:
        score.energy_arc = 2.5

    # --- Emotional Impact: Tension Index (max 5) ---
    # Use short-term loudness variance as tension proxy (computed in micro_dynamics above)
    if "st_variance" in dir() and st_variance is not None:
        score.tension_index = min(5.0, st_variance * 2.0)
    else:
        # Fallback: use crest factor as tension proxy
        score.tension_index = min(5.0, output_crest / 3.0)

    # --- Emotional Impact: Presence (max 5) ---
    # Energy in 2-5kHz (vocal/lead presence band)
    if len(freqs) > 1 and n_fft > 256:
        presence_mask = (freqs >= 2000) & (freqs <= 5000)
        total_mask = (freqs >= 20) & (freqs <= 20000)
        presence_ratio = float(np.sum(spectrum_full[presence_mask])) / (float(np.sum(spectrum_full[total_mask])) + 1e-10)
        # Good: 15-25% of energy in presence band
        if 0.15 <= presence_ratio <= 0.25:
            score.presence = 5.0
        else:
            score.presence = max(0.0, 5.0 - abs(presence_ratio - 0.2) * 50.0)
    else:
        score.presence = 2.5

    # --- Overall ---
    total = (
        score.loudness + score.true_peak + score.spectral + score.stereo +
        score.crest_preservation + score.micro_dynamics +
        score.mono_compat + score.codec_resilience +
        score.energy_arc + score.tension_index + score.presence
    )
    score.overall = round(min(100.0, total))

    # --- Per-platform scores ---
    for platform, tgt in PLATFORM_TARGETS.items():
        p_lufs_delta = abs(lufs - tgt["lufs"])
        p_tp_margin = tgt["tp_max"] - tp_db
        p_loudness = max(0.0, 25.0 - p_lufs_delta * 8.0)
        p_tp = 15.0 if p_tp_margin >= 0.0 else max(0.0, 15.0 + p_tp_margin * 8.0)
        p_total = p_loudness + p_tp + score.spectral + score.stereo + score.micro_dynamics
        score.platform_scores[platform] = round(min(100.0, p_total * 1.33))

    # --- Verdict ---
    if score.overall >= 85:
        score.verdict = "Release-ready. Your master sounds professional and platform-compliant."
        score.release_ready = True
    elif score.overall >= 70:
        score.verdict = "Good quality. Minor adjustments could improve platform compliance."
        score.release_ready = True
    elif score.overall >= 50:
        score.verdict = "Needs work. Check loudness and dynamic balance."
        score.release_ready = False
    else:
        score.verdict = "Significant issues detected. Review the breakdown for details."
        score.release_ready = False

    return score


async def compute_rain_score_v2(
    audio: np.ndarray,
    sr: int,
    input_audio: Optional[np.ndarray] = None,
    input_sr: Optional[int] = None,
    primary_platform: str = "spotify",
) -> ScoreBreakdown:
    """
    Async RAIN Score v2 — runs heavy computation in thread pool.
    """
    return await asyncio.to_thread(
        _compute_score_sync, audio, sr, input_audio, input_sr, primary_platform
    )
