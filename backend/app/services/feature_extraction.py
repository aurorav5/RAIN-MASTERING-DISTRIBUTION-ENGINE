"""
RAIN 43-Dimensional Feature Extraction — per RAIN-PLATFORM-SPEC-v1.0

Feature groups:
  Loudness (5):  integrated_lufs, short_term_max, momentary_max, lra, true_peak
  Dynamics (6):  crest_factor, dynamic_range, rms_level, peak_to_rms, compression_ratio_est, transient_density
  Spectral (16): centroid, spread, rolloff, flux, flatness, kurtosis, skewness, entropy,
                 energy_sub, energy_low, energy_mid, energy_high_mid, energy_high, energy_air,
                 spectral_tilt, spectral_contrast
  Stereo (7):    width, correlation, mid_energy, side_energy, ms_ratio, balance, mono_compat
  Transient (5): attack_time_avg, attack_strength, transient_count, transient_density, sustain_ratio
  Tonal (4):     pitch_confidence, harmonic_ratio, inharmonicity, tonal_power_ratio
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

import numpy as np
import pyloudnorm as pyln
from numpy.typing import NDArray
from scipy.signal import butter, sosfilt, resample_poly

INTERNAL_DTYPE = np.float64


@dataclass
class FeatureVector:
    """43-dimensional feature vector per RAIN-PLATFORM-SPEC-v1.0 Stage 4."""
    # Loudness (5)
    integrated_lufs: float = -70.0
    short_term_max: float = -70.0
    momentary_max: float = -70.0
    lra: float = 0.0
    true_peak: float = -100.0

    # Dynamics (6)
    crest_factor: float = 0.0
    dynamic_range: float = 0.0
    rms_level: float = -70.0
    peak_to_rms: float = 0.0
    compression_ratio_est: float = 1.0
    transient_density: float = 0.0

    # Spectral (16)
    spectral_centroid: float = 0.0
    spectral_spread: float = 0.0
    spectral_rolloff: float = 0.0
    spectral_flux: float = 0.0
    spectral_flatness: float = 0.0
    spectral_kurtosis: float = 0.0
    spectral_skewness: float = 0.0
    spectral_entropy: float = 0.0
    energy_sub: float = 0.0       # <60Hz
    energy_low: float = 0.0       # 60-250Hz
    energy_mid: float = 0.0       # 250-2kHz
    energy_high_mid: float = 0.0  # 2-6kHz
    energy_high: float = 0.0      # 6-12kHz
    energy_air: float = 0.0       # >12kHz
    spectral_tilt: float = 0.0
    spectral_contrast: float = 0.0

    # Stereo (7)
    stereo_width: float = 0.0
    stereo_correlation: float = 0.0
    mid_energy: float = 0.0
    side_energy: float = 0.0
    ms_ratio: float = 0.0
    stereo_balance: float = 0.0
    mono_compat: float = 0.0

    # Transient (5)
    attack_time_avg: float = 0.0
    attack_strength: float = 0.0
    transient_count: int = 0
    transient_density_per_sec: float = 0.0
    sustain_ratio: float = 0.0

    # Tonal (4)
    pitch_confidence: float = 0.0
    harmonic_ratio: float = 0.0
    inharmonicity: float = 0.0
    tonal_power_ratio: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def to_array(self) -> NDArray[np.float64]:
        return np.array([getattr(self, f.name) for f in fields(self)], dtype=np.float64)


def _true_peak(audio: NDArray, sr: int) -> float:
    oversampled = resample_poly(audio, up=4, down=1, axis=0)
    peak = np.max(np.abs(oversampled))
    if peak < 1e-10:
        return -100.0
    return float(20.0 * np.log10(peak))


def _band_energy(spectrum: NDArray, freqs: NDArray, lo: float, hi: float) -> float:
    mask = (freqs >= lo) & (freqs < hi)
    total = np.sum(spectrum)
    if total < 1e-10:
        return 0.0
    return float(np.sum(spectrum[mask]) / total)


def _spectral_stats(mono: NDArray, sr: int, n_fft: int = 4096) -> dict[str, float]:
    """Compute spectral statistics over multiple frames."""
    hop = n_fft // 2
    n_frames = max(1, (len(mono) - n_fft) // hop)

    centroids = []
    spreads = []
    rolloffs = []
    flatnesses = []
    fluxes = []
    prev_spec = None

    for i in range(n_frames):
        start = i * hop
        frame = mono[start:start + n_fft]
        if len(frame) < n_fft:
            break
        spectrum = np.abs(np.fft.rfft(frame * np.hanning(n_fft))) ** 2
        freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
        total = np.sum(spectrum) + 1e-10

        # Centroid
        centroid = np.sum(freqs * spectrum) / total
        centroids.append(centroid)

        # Spread (std dev)
        spread = np.sqrt(np.sum(((freqs - centroid) ** 2) * spectrum) / total)
        spreads.append(spread)

        # Rolloff (85%)
        cumsum = np.cumsum(spectrum)
        rolloff_idx = np.searchsorted(cumsum, 0.85 * total)
        rolloffs.append(freqs[min(rolloff_idx, len(freqs) - 1)])

        # Flatness (geometric mean / arithmetic mean)
        log_spec = np.log(spectrum + 1e-10)
        geo_mean = np.exp(np.mean(log_spec))
        arith_mean = np.mean(spectrum)
        flatnesses.append(geo_mean / (arith_mean + 1e-10))

        # Flux
        if prev_spec is not None:
            flux = np.sum((spectrum - prev_spec) ** 2)
            fluxes.append(flux)
        prev_spec = spectrum

    # Full-signal spectral stats
    full_spec = np.abs(np.fft.rfft(mono[:min(len(mono), 8 * n_fft)])) ** 2
    full_freqs = np.fft.rfftfreq(min(len(mono), 8 * n_fft), 1.0 / sr)
    full_total = np.sum(full_spec) + 1e-10

    # Kurtosis and skewness
    norm_spec = full_spec / full_total
    mean_f = np.sum(full_freqs * norm_spec)
    var_f = np.sum(((full_freqs - mean_f) ** 2) * norm_spec)
    std_f = np.sqrt(var_f) + 1e-10
    skew = np.sum(((full_freqs - mean_f) ** 3) * norm_spec) / (std_f ** 3)
    kurt = np.sum(((full_freqs - mean_f) ** 4) * norm_spec) / (std_f ** 4)

    # Entropy
    norm_spec_clip = np.clip(norm_spec, 1e-10, None)
    entropy = -np.sum(norm_spec_clip * np.log2(norm_spec_clip))

    # Band energies
    sub = _band_energy(full_spec, full_freqs, 0, 60)
    low = _band_energy(full_spec, full_freqs, 60, 250)
    mid = _band_energy(full_spec, full_freqs, 250, 2000)
    high_mid = _band_energy(full_spec, full_freqs, 2000, 6000)
    high = _band_energy(full_spec, full_freqs, 6000, 12000)
    air_e = _band_energy(full_spec, full_freqs, 12000, sr / 2)

    # Tilt (linear regression of log spectrum)
    log_f = np.log10(full_freqs[1:] + 1e-10)
    log_s = 10 * np.log10(full_spec[1:] + 1e-10)
    if len(log_f) > 1:
        tilt = float(np.polyfit(log_f, log_s, 1)[0])
    else:
        tilt = 0.0

    # Contrast (max - min in octave bands)
    contrasts = []
    for lo_hz, hi_hz in [(60, 120), (120, 250), (250, 500), (500, 1000), (1000, 2000), (2000, 4000)]:
        band_mask = (full_freqs >= lo_hz) & (full_freqs < hi_hz)
        band = full_spec[band_mask]
        if len(band) > 0:
            contrasts.append(np.max(band) - np.min(band))
    contrast = float(np.mean(contrasts)) if contrasts else 0.0

    return {
        "centroid": float(np.mean(centroids)) if centroids else 0.0,
        "spread": float(np.mean(spreads)) if spreads else 0.0,
        "rolloff": float(np.mean(rolloffs)) if rolloffs else 0.0,
        "flux": float(np.mean(fluxes)) if fluxes else 0.0,
        "flatness": float(np.mean(flatnesses)) if flatnesses else 0.0,
        "kurtosis": float(kurt),
        "skewness": float(skew),
        "entropy": float(entropy),
        "sub": sub, "low": low, "mid": mid, "high_mid": high_mid, "high": high, "air": air_e,
        "tilt": tilt,
        "contrast": contrast,
    }


def _stereo_features(audio: NDArray) -> dict[str, float]:
    """Compute stereo features."""
    if audio.shape[1] < 2:
        return {"width": 0, "correlation": 1, "mid_energy": 1, "side_energy": 0,
                "ms_ratio": 0, "balance": 0, "mono_compat": 1}

    left, right = audio[:, 0], audio[:, 1]
    mid = (left + right) * 0.5
    side = (left - right) * 0.5

    mid_e = float(np.sum(mid ** 2))
    side_e = float(np.sum(side ** 2))
    width = side_e / (mid_e + 1e-10)

    # Correlation
    corr = np.corrcoef(left, right)[0, 1] if len(left) > 1 else 1.0
    if np.isnan(corr):
        corr = 1.0

    # Balance (dB difference L vs R)
    l_rms = np.sqrt(np.mean(left ** 2)) + 1e-10
    r_rms = np.sqrt(np.mean(right ** 2)) + 1e-10
    balance = float(20.0 * np.log10(l_rms / r_rms))

    # Mono compatibility (energy preserved in mono fold-down)
    mono_e = np.sum((left + right) ** 2)
    stereo_e = np.sum(left ** 2) + np.sum(right ** 2)
    mono_compat = float(mono_e / (stereo_e + 1e-10))

    return {
        "width": float(width),
        "correlation": float(corr),
        "mid_energy": float(mid_e / (mid_e + side_e + 1e-10)),
        "side_energy": float(side_e / (mid_e + side_e + 1e-10)),
        "ms_ratio": float(side_e / (mid_e + 1e-10)),
        "balance": balance,
        "mono_compat": mono_compat,
    }


def _transient_features(mono: NDArray, sr: int) -> dict[str, float]:
    """Detect transients and measure attack characteristics."""
    # Envelope follower
    abs_mono = np.abs(mono)
    hop = int(0.005 * sr)  # 5ms hop
    n_frames = len(abs_mono) // hop
    envelope = np.array([np.max(abs_mono[i * hop:(i + 1) * hop]) for i in range(n_frames)])

    if len(envelope) < 3:
        return {"attack_time_avg": 0, "attack_strength": 0, "transient_count": 0,
                "transient_density_per_sec": 0, "sustain_ratio": 0}

    # Detect transients (envelope rises > threshold)
    diff = np.diff(envelope)
    threshold = np.std(diff) * 1.5
    transient_frames = np.where(diff > threshold)[0]

    count = len(transient_frames)
    duration = len(mono) / sr

    # Average attack time (frames between onset and peak)
    attack_times = []
    for tf in transient_frames:
        if tf + 5 < len(envelope):
            peak_idx = tf + np.argmax(envelope[tf:tf + 10])
            attack_times.append((peak_idx - tf) * hop / sr * 1000)  # ms

    # Sustain ratio (RMS / peak)
    rms = np.sqrt(np.mean(mono ** 2))
    peak = np.max(np.abs(mono))
    sustain = rms / (peak + 1e-10)

    return {
        "attack_time_avg": float(np.mean(attack_times)) if attack_times else 0.0,
        "attack_strength": float(np.mean(diff[transient_frames])) if count > 0 else 0.0,
        "transient_count": count,
        "transient_density_per_sec": count / duration if duration > 0 else 0.0,
        "sustain_ratio": float(sustain),
    }


def _tonal_features(mono: NDArray, sr: int) -> dict[str, float]:
    """Estimate tonal characteristics."""
    n_fft = min(8192, len(mono))
    spectrum = np.abs(np.fft.rfft(mono[:n_fft] * np.hanning(n_fft)))
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)

    # Find fundamental via autocorrelation
    autocorr = np.correlate(mono[:n_fft], mono[:n_fft], mode='full')
    autocorr = autocorr[len(autocorr) // 2:]
    # Look for peaks in plausible pitch range (50Hz - 4kHz)
    min_lag = int(sr / 4000)
    max_lag = min(int(sr / 50), len(autocorr) - 1)

    if max_lag > min_lag:
        pitch_region = autocorr[min_lag:max_lag]
        if len(pitch_region) > 0 and np.max(pitch_region) > 0:
            peak_idx = np.argmax(pitch_region) + min_lag
            pitch_confidence = float(autocorr[peak_idx] / (autocorr[0] + 1e-10))
        else:
            pitch_confidence = 0.0
    else:
        pitch_confidence = 0.0

    # Harmonic ratio (energy at harmonics vs total)
    total_energy = np.sum(spectrum ** 2) + 1e-10
    # Simple: ratio of top 10 spectral peaks to total
    top_k = min(20, len(spectrum))
    top_indices = np.argsort(spectrum)[-top_k:]
    harmonic_energy = np.sum(spectrum[top_indices] ** 2)
    harmonic_ratio = float(harmonic_energy / total_energy)

    # Tonal power ratio
    sorted_spec = np.sort(spectrum)[::-1]
    tonal_power = np.sum(sorted_spec[:top_k])
    noise_power = np.sum(sorted_spec[top_k:]) + 1e-10
    tpr = float(tonal_power / noise_power)

    return {
        "pitch_confidence": pitch_confidence,
        "harmonic_ratio": harmonic_ratio,
        "inharmonicity": 1.0 - harmonic_ratio,
        "tonal_power_ratio": tpr,
    }


def extract_features(audio: NDArray[np.float64], sr: int) -> FeatureVector:
    """Extract the full 43-dimensional feature vector from audio.

    Args:
        audio: Stereo audio as (samples, 2) float64 array
        sr: Sample rate

    Returns:
        FeatureVector with all 43 dimensions populated
    """
    mono = np.mean(audio, axis=1)
    fv = FeatureVector()

    # === Loudness (5) ===
    meter = pyln.Meter(sr)
    lufs = meter.integrated_loudness(audio)
    fv.integrated_lufs = lufs if not (np.isinf(lufs) or np.isnan(lufs)) else -70.0

    # Short-term (3s blocks)
    block_3s = int(3.0 * sr)
    if len(mono) >= block_3s:
        n_blocks = len(mono) // block_3s
        st_values = []
        for i in range(n_blocks):
            block = audio[i * block_3s:(i + 1) * block_3s]
            st = meter.integrated_loudness(block)
            if not (np.isinf(st) or np.isnan(st)):
                st_values.append(st)
        fv.short_term_max = max(st_values) if st_values else fv.integrated_lufs
    else:
        fv.short_term_max = fv.integrated_lufs

    # Momentary (400ms blocks)
    block_400ms = int(0.4 * sr)
    if len(mono) >= block_400ms:
        n_blocks = len(mono) // block_400ms
        mom_values = []
        for i in range(min(n_blocks, 50)):  # Cap at 50 for performance
            block = audio[i * block_400ms:(i + 1) * block_400ms]
            mom = meter.integrated_loudness(block)
            if not (np.isinf(mom) or np.isnan(mom)):
                mom_values.append(mom)
        fv.momentary_max = max(mom_values) if mom_values else fv.integrated_lufs
    else:
        fv.momentary_max = fv.integrated_lufs

    # LRA (loudness range = difference between high and low short-term)
    if len(mono) >= block_3s:
        fv.lra = fv.short_term_max - fv.integrated_lufs
    else:
        fv.lra = 0.0

    fv.true_peak = _true_peak(audio, sr)

    # === Dynamics (6) ===
    rms = np.sqrt(np.mean(mono ** 2))
    peak = np.max(np.abs(mono))
    fv.rms_level = float(20.0 * np.log10(rms + 1e-10))
    fv.crest_factor = float(20.0 * np.log10(peak / (rms + 1e-10))) if rms > 1e-10 else 0.0
    fv.dynamic_range = fv.crest_factor
    fv.peak_to_rms = fv.crest_factor
    fv.compression_ratio_est = max(1.0, fv.crest_factor / 12.0) if fv.crest_factor > 0 else 1.0

    transient = _transient_features(mono, sr)
    fv.transient_density = transient["transient_density_per_sec"]

    # === Spectral (16) ===
    spec = _spectral_stats(mono, sr)
    fv.spectral_centroid = spec["centroid"]
    fv.spectral_spread = spec["spread"]
    fv.spectral_rolloff = spec["rolloff"]
    fv.spectral_flux = spec["flux"]
    fv.spectral_flatness = spec["flatness"]
    fv.spectral_kurtosis = spec["kurtosis"]
    fv.spectral_skewness = spec["skewness"]
    fv.spectral_entropy = spec["entropy"]
    fv.energy_sub = spec["sub"]
    fv.energy_low = spec["low"]
    fv.energy_mid = spec["mid"]
    fv.energy_high_mid = spec["high_mid"]
    fv.energy_high = spec["high"]
    fv.energy_air = spec["air"]
    fv.spectral_tilt = spec["tilt"]
    fv.spectral_contrast = spec["contrast"]

    # === Stereo (7) ===
    stereo = _stereo_features(audio)
    fv.stereo_width = stereo["width"]
    fv.stereo_correlation = stereo["correlation"]
    fv.mid_energy = stereo["mid_energy"]
    fv.side_energy = stereo["side_energy"]
    fv.ms_ratio = stereo["ms_ratio"]
    fv.stereo_balance = stereo["balance"]
    fv.mono_compat = stereo["mono_compat"]

    # === Transient (5) ===
    fv.attack_time_avg = transient["attack_time_avg"]
    fv.attack_strength = transient["attack_strength"]
    fv.transient_count = transient["transient_count"]
    fv.transient_density_per_sec = transient["transient_density_per_sec"]
    fv.sustain_ratio = transient["sustain_ratio"]

    # === Tonal (4) ===
    tonal = _tonal_features(mono, sr)
    fv.pitch_confidence = tonal["pitch_confidence"]
    fv.harmonic_ratio = tonal["harmonic_ratio"]
    fv.inharmonicity = tonal["inharmonicity"]
    fv.tonal_power_ratio = tonal["tonal_power_ratio"]

    return fv
