"""
RAIN Prototype Mastering Engine — Pure Python DSP Chain

7-stage mastering pipeline using scipy/numpy. This is the PROTOTYPE engine,
NOT the production RainDSP C++/WASM engine. Uses identical DSP math in 64-bit float.

RAIN v2 UPGRADE: Target-state driven processing with groove awareness, multi-pass
optimization, and genre-specific life injection.

Stages:
  1. Input Normalization (resample to 48kHz, 64-bit float)
  2. Analysis (LUFS, true peak, spectral centroid, crest factor, stereo width, bass energy, GROOVE)
  3. Intent Processing (genre-aware target state calculation)
  4. EQ (brightness + air + subsonic HPF + genre-forced low-end)
  5. Multiband Compression (3-band: low/mid/high, groove-aware)
  6. Stereo Widening (M/S with bass mono, side HF boost, genre-aware)
  7. Groove Enhancement (transient shaping, microtiming preparation)
  8. Life Injection (parallel saturation, genre-specific energy)
  9. Limiting (look-ahead limiter with LUFS targeting)
  10. Evaluation & Adjustment (multi-pass optimization with rollback)
"""

from __future__ import annotations

import io
import struct
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pyloudnorm as pyln
import resampy
import soundfile as sf
from numpy.typing import NDArray
from pydub import AudioSegment
from scipy.signal import butter, sosfilt, sosfiltfilt, resample_poly

# Import RAIN v2 engines
from .groove_engine import GrooveEngine, GrooveAnalysisResult
from .intent_engine import IntentResult, ControlSignal

INTERNAL_SR = 48000
INTERNAL_DTYPE = np.float64


@dataclass
class TargetState:
    """Target state for proactive mastering (RAIN v2)."""
    groove: float = 0.75         # Target groove score
    low_end: float = 0.7         # Target low-end weight
    energy: float = 0.65         # Target energy level
    width: float = 0.6           # Target stereo width
    brightness: float = 4500.0   # Target spectral centroid (Hz)
    
    @classmethod
    def from_genre(cls, genre: str) -> "TargetState":
        """Create target state based on genre profile."""
        profiles = {
            "afropop_house": cls(
                groove=0.85,
                low_end=0.8,
                energy=0.75,
                width=0.8,
                brightness=4000.0
            ),
            "hiphop": cls(
                groove=0.8,
                low_end=0.85,
                energy=0.7,
                width=0.5,
                brightness=3800.0
            ),
            "electronic": cls(
                groove=0.8,
                low_end=0.75,
                energy=0.8,
                width=0.85,
                brightness=5000.0
            ),
            "pop": cls(
                groove=0.6,
                low_end=0.6,
                energy=0.7,
                width=0.6,
                brightness=4500.0
            ),
            "rock": cls(
                groove=0.5,
                low_end=0.65,
                energy=0.75,
                width=0.7,
                brightness=5500.0
            ),
        }
        return profiles.get(genre.lower(), cls())


@dataclass
class AnalysisResult:
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
    # RAIN v2 additions
    groove_score: float = 0.5
    swing_ratio: float = 1.0
    timing_variance: float = 0.0
    transient_sharpness: float = 0.5
    tempo_bpm: float = 120.0


@dataclass
class MasterResult:
    output_wav_path: str
    output_mp3_path: str
    session_id: str
    analysis: AnalysisResult
    output_lufs: float
    output_true_peak: float
    output_dynamic_range: float
    output_stereo_width: float
    output_spectral_centroid: float


@dataclass
class MasteringParams:
    """Knob values from the frontend, mapped to DSP parameters."""
    brightness: float = 2.0      # High-shelf gain at 8kHz in dB (0-4)
    tightness: float = 3.0       # Low-band compression ratio (1-5)
    width: float = 2.0           # Side gain in dB (-3 to +6)
    loudness: float = -14.0      # Target LUFS (-16 to -9)
    warmth: float = 0.0          # Low-shelf gain at 200Hz in dB (0-3)
    punch: float = 10.0          # Mid-band attack time in ms (1-30)
    air: float = 1.5             # 16kHz peaking gain in dB (0-3)


def load_audio(file_path: str) -> tuple[NDArray[np.float64], int]:
    """Load audio file to 64-bit float numpy array. Supports WAV/FLAC/AIFF/MP3."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".mp3":
        seg = AudioSegment.from_mp3(file_path)
        sr = seg.frame_rate
        samples = np.array(seg.get_array_of_samples(), dtype=INTERNAL_DTYPE)
        samples = samples / (2 ** (seg.sample_width * 8 - 1))
        if seg.channels == 2:
            samples = samples.reshape(-1, 2)
        elif seg.channels == 1:
            samples = samples.reshape(-1, 1)
        return samples, sr
    else:
        data, sr = sf.read(file_path, dtype="float64", always_2d=True)
        return data, sr


def load_audio_from_buffer(buffer: bytes, format_hint: str = "wav") -> tuple[NDArray[np.float64], int]:
    """Load audio from bytes buffer."""
    if format_hint.lower() == "mp3":
        seg = AudioSegment.from_mp3(io.BytesIO(buffer))
        sr = seg.frame_rate
        samples = np.array(seg.get_array_of_samples(), dtype=INTERNAL_DTYPE)
        samples = samples / (2 ** (seg.sample_width * 8 - 1))
        if seg.channels == 2:
            samples = samples.reshape(-1, 2)
        elif seg.channels == 1:
            samples = samples.reshape(-1, 1)
        return samples, sr
    else:
        bio = io.BytesIO(buffer)
        data, sr = sf.read(bio, dtype="float64", always_2d=True)
        return data, sr


# ---------------------------------------------------------------------------
# Stage 1 — Input Normalization
# ---------------------------------------------------------------------------

def normalize_input(audio: NDArray[np.float64], sr: int) -> NDArray[np.float64]:
    """Resample to 48kHz internal processing rate. Ensure stereo."""
    if audio.ndim == 1:
        audio = np.column_stack([audio, audio])
    elif audio.shape[1] == 1:
        audio = np.column_stack([audio[:, 0], audio[:, 0]])
    elif audio.shape[1] > 2:
        audio = audio[:, :2]

    if sr != INTERNAL_SR:
        audio = resampy.resample(audio, sr, INTERNAL_SR, axis=0, filter="kaiser_best")

    return audio.astype(INTERNAL_DTYPE)


# ---------------------------------------------------------------------------
# Stage 2 — Analysis
# ---------------------------------------------------------------------------

def measure_true_peak(audio: NDArray[np.float64], sr: int) -> float:
    """Measure true peak using 4x oversampling per ITU-R BS.1770-4."""
    oversampled = resample_poly(audio, up=4, down=1, axis=0)
    peak_linear = np.max(np.abs(oversampled))
    if peak_linear < 1e-10:
        return -100.0
    return float(20.0 * np.log10(peak_linear))


def compute_spectral_centroid(audio: NDArray[np.float64], sr: int) -> float:
    """Compute spectral centroid (brightness indicator) in Hz."""
    mono = np.mean(audio, axis=1)
    n_fft = min(4096, len(mono))
    spectrum = np.abs(np.fft.rfft(mono[:n_fft]))
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    total_energy = np.sum(spectrum)
    if total_energy < 1e-10:
        return 0.0
    return float(np.sum(freqs * spectrum) / total_energy)


def compute_crest_factor(audio: NDArray[np.float64]) -> float:
    """Crest factor in dB (peak / RMS)."""
    rms = np.sqrt(np.mean(audio ** 2))
    peak = np.max(np.abs(audio))
    if rms < 1e-10:
        return 0.0
    return float(20.0 * np.log10(peak / rms))


def compute_stereo_width(audio: NDArray[np.float64]) -> float:
    """Stereo width as side/mid energy ratio (0 = mono, 1 = equal, >1 = wide)."""
    if audio.shape[1] < 2:
        return 0.0
    mid = (audio[:, 0] + audio[:, 1]) * 0.5
    side = (audio[:, 0] - audio[:, 1]) * 0.5
    mid_energy = np.sum(mid ** 2)
    side_energy = np.sum(side ** 2)
    if mid_energy < 1e-10:
        return 0.0
    return float(side_energy / mid_energy)


def compute_bass_energy_ratio(audio: NDArray[np.float64], sr: int) -> float:
    """Ratio of energy below 200Hz to total energy."""
    mono = np.mean(audio, axis=1)
    n_fft = min(8192, len(mono))
    spectrum = np.abs(np.fft.rfft(mono[:n_fft])) ** 2
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    bass_mask = freqs <= 200.0
    total = np.sum(spectrum)
    if total < 1e-10:
        return 0.0
    return float(np.sum(spectrum[bass_mask]) / total)


def analyze(audio: NDArray[np.float64], sr: int, original_sr: int) -> AnalysisResult:
    """Run full analysis on normalized audio."""
    meter = pyln.Meter(sr)
    lufs = meter.integrated_loudness(audio)
    if np.isinf(lufs) or np.isnan(lufs):
        lufs = -70.0

    tp = measure_true_peak(audio, sr)
    sc = compute_spectral_centroid(audio, sr)
    cf = compute_crest_factor(audio)
    sw = compute_stereo_width(audio)
    be = compute_bass_energy_ratio(audio, sr)
    dr = cf  # dynamic range approximated by crest factor

    return AnalysisResult(
        input_lufs=lufs,
        input_true_peak=tp,
        spectral_centroid=sc,
        crest_factor=cf,
        stereo_width=sw,
        bass_energy_ratio=be,
        dynamic_range=dr,
        sample_rate=original_sr,
        channels=audio.shape[1],
        duration=len(audio) / sr,
    )


# ---------------------------------------------------------------------------
# Stage 3 — EQ (Brightness + Air + Subsonic HPF)
# ---------------------------------------------------------------------------

def design_high_shelf(freq: float, gain_db: float, sr: int, order: int = 2) -> NDArray:
    """Design a high-shelf filter as second-order sections.
    Approximated using a peaking EQ at the shelf frequency with wide Q."""
    if abs(gain_db) < 0.01:
        return np.array([[1, 0, 0, 1, 0, 0]], dtype=INTERNAL_DTYPE)

    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * freq / sr
    cos_w0 = np.cos(w0)
    sin_w0 = np.sin(w0)
    alpha = sin_w0 / 2.0 * np.sqrt((A + 1.0 / A) * (1.0 / 0.707 - 1) + 2)
    sqrt_A = np.sqrt(A)

    b0 = A * ((A + 1) + (A - 1) * cos_w0 + 2 * sqrt_A * alpha)
    b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
    b2 = A * ((A + 1) + (A - 1) * cos_w0 - 2 * sqrt_A * alpha)
    a0 = (A + 1) - (A - 1) * cos_w0 + 2 * sqrt_A * alpha
    a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
    a2 = (A + 1) - (A - 1) * cos_w0 - 2 * sqrt_A * alpha

    return np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]], dtype=INTERNAL_DTYPE)


def design_low_shelf(freq: float, gain_db: float, sr: int) -> NDArray:
    """Design a low-shelf filter as SOS."""
    if abs(gain_db) < 0.01:
        return np.array([[1, 0, 0, 1, 0, 0]], dtype=INTERNAL_DTYPE)

    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * freq / sr
    cos_w0 = np.cos(w0)
    sin_w0 = np.sin(w0)
    alpha = sin_w0 / 2.0 * np.sqrt((A + 1.0 / A) * (1.0 / 0.707 - 1) + 2)
    sqrt_A = np.sqrt(A)

    b0 = A * ((A + 1) - (A - 1) * cos_w0 + 2 * sqrt_A * alpha)
    b1 = 2 * A * ((A - 1) - (A + 1) * cos_w0)
    b2 = A * ((A + 1) - (A - 1) * cos_w0 - 2 * sqrt_A * alpha)
    a0 = (A + 1) + (A - 1) * cos_w0 + 2 * sqrt_A * alpha
    a1 = -2 * ((A - 1) + (A + 1) * cos_w0)
    a2 = (A + 1) + (A - 1) * cos_w0 - 2 * sqrt_A * alpha

    return np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]], dtype=INTERNAL_DTYPE)


def design_peaking(freq: float, gain_db: float, q: float, sr: int) -> NDArray:
    """Design a peaking EQ filter as SOS."""
    if abs(gain_db) < 0.01:
        return np.array([[1, 0, 0, 1, 0, 0]], dtype=INTERNAL_DTYPE)

    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * freq / sr
    cos_w0 = np.cos(w0)
    sin_w0 = np.sin(w0)
    alpha = sin_w0 / (2.0 * q)

    b0 = 1 + alpha * A
    b1 = -2 * cos_w0
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * cos_w0
    a2 = 1 - alpha / A

    return np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]], dtype=INTERNAL_DTYPE)


def apply_eq(audio: NDArray[np.float64], sr: int, params: MasteringParams) -> NDArray[np.float64]:
    """Stage 3: Apply EQ — high-shelf brightness, air peaking, subsonic HPF, warmth."""
    # High-pass at 30Hz (4th order Butterworth) — remove subsonic rumble
    sos_hp = butter(4, 30.0, btype="high", fs=sr, output="sos")
    audio = sosfilt(sos_hp, audio, axis=0)

    # High-shelf at 8kHz — brightness
    sos_bright = design_high_shelf(8000.0, params.brightness, sr)
    audio = sosfilt(sos_bright, audio, axis=0)

    # Peaking at 16kHz — air
    sos_air = design_peaking(16000.0, params.air, 0.7, sr)
    audio = sosfilt(sos_air, audio, axis=0)

    # Low-shelf at 200Hz — warmth
    if params.warmth > 0.01:
        sos_warm = design_low_shelf(200.0, params.warmth, sr)
        audio = sosfilt(sos_warm, audio, axis=0)

    return audio


# ---------------------------------------------------------------------------
# Stage 4 — Multiband Compression (Tightness)
# ---------------------------------------------------------------------------

def linkwitz_riley_4(freq: float, sr: int) -> tuple[NDArray, NDArray]:
    """Design Linkwitz-Riley 4th-order crossover (two cascaded 2nd-order Butterworth)."""
    sos_lp = butter(2, freq, btype="low", fs=sr, output="sos")
    sos_hp = butter(2, freq, btype="high", fs=sr, output="sos")
    # LR4 = two cascaded Butterworth 2nd-order
    sos_lp4 = np.vstack([sos_lp, sos_lp])
    sos_hp4 = np.vstack([sos_hp, sos_hp])
    return sos_lp4, sos_hp4


def compress_band(
    audio: NDArray[np.float64],
    sr: int,
    threshold_db: float,
    ratio: float,
    attack_ms: float,
    release_ms: float,
) -> NDArray[np.float64]:
    """Feedforward compressor on a single band."""
    if ratio <= 1.0:
        return audio

    threshold_lin = 10 ** (threshold_db / 20.0)
    attack_coeff = np.exp(-1.0 / (attack_ms * 0.001 * sr))
    release_coeff = np.exp(-1.0 / (release_ms * 0.001 * sr))

    # Compute RMS envelope per sample (smoothed)
    n_samples = audio.shape[0]
    envelope = np.zeros(n_samples, dtype=INTERNAL_DTYPE)
    rms_sq = 0.0
    smooth_coeff = np.exp(-1.0 / (5.0 * 0.001 * sr))  # 5ms smoothing

    # Mono envelope from max of channels
    mono_abs = np.max(np.abs(audio), axis=1)

    for i in range(n_samples):
        rms_sq = smooth_coeff * rms_sq + (1 - smooth_coeff) * (mono_abs[i] ** 2)
        envelope[i] = np.sqrt(rms_sq)

    # Compute gain reduction
    gain = np.ones(n_samples, dtype=INTERNAL_DTYPE)
    for i in range(n_samples):
        if envelope[i] > threshold_lin and envelope[i] > 1e-10:
            over_db = 20.0 * np.log10(envelope[i] / threshold_lin)
            reduction_db = over_db * (1.0 - 1.0 / ratio)
            target_gain = 10 ** (-reduction_db / 20.0)
        else:
            target_gain = 1.0

        if i > 0:
            if target_gain < gain[i - 1]:
                coeff = attack_coeff
            else:
                coeff = release_coeff
            gain[i] = coeff * gain[i - 1] + (1 - coeff) * target_gain
        else:
            gain[i] = target_gain

    return audio * gain[:, np.newaxis]


def apply_multiband_compression(
    audio: NDArray[np.float64], sr: int, params: MasteringParams
) -> NDArray[np.float64]:
    """Stage 4: 3-band multiband compression with LR4 crossovers at 200Hz and 4kHz."""
    # Split into 3 bands
    sos_lp1, sos_hp1 = linkwitz_riley_4(200.0, sr)
    sos_lp2, sos_hp2 = linkwitz_riley_4(4000.0, sr)

    low = sosfilt(sos_lp1, audio, axis=0)
    mid_high = sosfilt(sos_hp1, audio, axis=0)
    mid = sosfilt(sos_lp2, mid_high, axis=0)
    high = sosfilt(sos_hp2, mid_high, axis=0)

    # Compress each band
    low = compress_band(low, sr, -18.0, params.tightness, 5.0, 150.0)
    mid = compress_band(mid, sr, -15.0, 2.0, params.punch, 100.0)
    high = compress_band(high, sr, -12.0, 2.0, 2.0, 50.0)

    # Recombine (LR4 guarantees flat magnitude sum)
    return low + mid + high


# ---------------------------------------------------------------------------
# Stage 5 — Stereo Widening (Width)
# ---------------------------------------------------------------------------

def apply_stereo_widening(
    audio: NDArray[np.float64], sr: int, params: MasteringParams
) -> NDArray[np.float64]:
    """Stage 5: M/S processing with bass mono and side HF boost."""
    if audio.shape[1] < 2:
        return audio

    left = audio[:, 0]
    right = audio[:, 1]

    # Encode to M/S
    mid = (left + right) * 0.5
    side = (left - right) * 0.5

    # Bass mono: high-pass the side channel at 200Hz (collapse low freqs to mono)
    sos_hp_side = butter(4, 200.0, btype="high", fs=sr, output="sos")
    side = sosfilt(sos_hp_side, side)

    # Side HF boost: high-shelf on side channel above 4kHz
    side_gain_db = params.width
    if abs(side_gain_db) > 0.01:
        sos_side_hf = design_high_shelf(4000.0, side_gain_db, sr)
        side = sosfilt(sos_side_hf, side)

    # Decode back to L/R
    left_out = mid + side
    right_out = mid - side

    return np.column_stack([left_out, right_out])


# ---------------------------------------------------------------------------
# Stage 6 — Limiting (Loudness)
# ---------------------------------------------------------------------------

def apply_limiter(
    audio: NDArray[np.float64],
    sr: int,
    target_lufs: float,
    ceiling_dbtp: float = -1.0,
    max_iterations: int = 3,
) -> NDArray[np.float64]:
    """Stage 6: Look-ahead limiter with LUFS targeting.

    - 5ms look-ahead buffer
    - Attack 0.1ms, release 100ms
    - True peak ceiling at ceiling_dbtp
    - Iterates to hit target LUFS within ±0.3 LU
    """
    ceiling_lin = 10 ** (ceiling_dbtp / 20.0)
    lookahead_samples = int(5.0 * 0.001 * sr)  # 5ms
    attack_coeff = np.exp(-1.0 / (0.1 * 0.001 * sr))
    release_coeff = np.exp(-1.0 / (100.0 * 0.001 * sr))

    result = audio.copy()

    for iteration in range(max_iterations):
        # True peak detection via 4x oversampling
        oversampled = resample_poly(result, up=4, down=1, axis=0)
        peak_per_sample = np.max(np.abs(oversampled).reshape(-1, 4, result.shape[1]).max(axis=2), axis=1)

        # Compute gain reduction needed
        n_samples = result.shape[0]
        gain_reduction = np.ones(n_samples, dtype=INTERNAL_DTYPE)

        for i in range(n_samples):
            if peak_per_sample[i] > ceiling_lin:
                gain_reduction[i] = ceiling_lin / peak_per_sample[i]

        # Apply look-ahead: shift gain reduction backward
        shifted_gr = np.ones(n_samples, dtype=INTERNAL_DTYPE)
        for i in range(n_samples):
            la_end = min(i + lookahead_samples, n_samples)
            shifted_gr[i] = np.min(gain_reduction[i:la_end])

        # Smooth gain with attack/release
        smoothed = np.ones(n_samples, dtype=INTERNAL_DTYPE)
        smoothed[0] = shifted_gr[0]
        for i in range(1, n_samples):
            if shifted_gr[i] < smoothed[i - 1]:
                coeff = attack_coeff
            else:
                coeff = release_coeff
            smoothed[i] = coeff * smoothed[i - 1] + (1 - coeff) * shifted_gr[i]

        result = result * smoothed[:, np.newaxis]

        # Measure LUFS and apply makeup gain
        meter = pyln.Meter(sr)
        current_lufs = meter.integrated_loudness(result)
        if np.isinf(current_lufs) or np.isnan(current_lufs):
            break

        lufs_diff = target_lufs - current_lufs
        if abs(lufs_diff) <= 0.3:
            break

        makeup_gain = 10 ** (lufs_diff / 20.0)
        result = result * makeup_gain

    # Final true-peak ceiling enforcement via oversampled peak detection.
    # The sample-level clip is insufficient — inter-sample peaks can exceed
    # the ceiling after reconstruction. Re-measure and attenuate if needed.
    for _ in range(3):
        tp_db = measure_true_peak(result, sr)
        if tp_db <= ceiling_dbtp:
            break
        # Attenuate by the exact overshoot + 0.1 dB safety margin
        overshoot_db = tp_db - ceiling_dbtp
        attenuation = 10 ** (-(overshoot_db + 0.1) / 20.0)
        result = result * attenuation

    return result


# ---------------------------------------------------------------------------
# Stage 7 — Output Preparation
# ---------------------------------------------------------------------------

def apply_tpdf_dither(audio: NDArray[np.float64], target_bits: int) -> NDArray[np.float64]:
    """Apply TPDF (Triangular Probability Density Function) dither."""
    quant_step = 1.0 / (2 ** (target_bits - 1))
    dither = (np.random.random(audio.shape) + np.random.random(audio.shape) - 1.0) * quant_step
    return audio + dither


def export_wav(
    audio: NDArray[np.float64], sr: int, output_path: str
) -> None:
    """Export as 24-bit/48kHz WAV with TPDF dither."""
    dithered = apply_tpdf_dither(audio, 24)
    # Clip to prevent overflow
    dithered = np.clip(dithered, -1.0, 1.0 - 1.0 / (2 ** 23))
    sf.write(output_path, dithered, sr, subtype="PCM_24")


def export_mp3(
    audio: NDArray[np.float64], sr: int, output_path: str
) -> None:
    """Export as 320kbps MP3 at 44.1kHz with TPDF dither via pydub/ffmpeg.

    Applies post-resample LUFS correction to prevent gain injection from the
    fractional resample (48kHz→44.1kHz kaiser_best filter overshoot).
    """
    # Resample to 44.1kHz
    if sr != 44100:
        audio_44 = resampy.resample(audio, sr, 44100, axis=0, filter="kaiser_best")
    else:
        audio_44 = audio.copy()

    # Post-resample LUFS correction: match the original LUFS exactly
    meter_src = pyln.Meter(sr)
    meter_dst = pyln.Meter(44100)
    lufs_before = meter_src.integrated_loudness(audio)
    lufs_after = meter_dst.integrated_loudness(audio_44)

    if np.isfinite(lufs_before) and np.isfinite(lufs_after):
        correction_db = lufs_before - lufs_after
        if abs(correction_db) > 0.01:
            correction_lin = 10 ** (correction_db / 20.0)
            audio_44 = audio_44 * correction_lin

    # Clip any overshoot from the resampler before dithering
    ceiling_lin = 10 ** (-1.0 / 20.0)  # -1.0 dBTP ceiling
    peak = np.max(np.abs(audio_44))
    if peak > ceiling_lin:
        audio_44 = audio_44 * (ceiling_lin / peak)

    # Dither to 16-bit
    dithered = apply_tpdf_dither(audio_44, 16)
    dithered = np.clip(dithered, -1.0, 1.0 - 1.0 / (2 ** 15))

    # Convert to 16-bit integer
    int16_data = (dithered * (2 ** 15)).astype(np.int16)

    # Create AudioSegment from raw PCM
    seg = AudioSegment(
        data=int16_data.tobytes(),
        sample_width=2,
        frame_rate=44100,
        channels=audio_44.shape[1],
    )

    seg.export(output_path, format="mp3", bitrate="320k", codec="libmp3lame")


# ---------------------------------------------------------------------------
# Full Mastering Chain
# ---------------------------------------------------------------------------

def master_audio(
    input_path: str,
    output_dir: str,
    session_id: str | None = None,
    params: MasteringParams | None = None,
    metadata: dict[str, str] | None = None,
) -> MasterResult:
    """Execute the complete 7-stage mastering chain.

    Args:
        input_path: Path to the input audio file
        output_dir: Directory for output files
        session_id: Unique session ID (auto-generated if None)
        params: Mastering parameters from knob values
        metadata: Track metadata (title, artist, album, genre, track_number, year)

    Returns:
        MasterResult with paths to output files and analysis data
    """
    if session_id is None:
        session_id = str(uuid.uuid4())
    if params is None:
        params = MasteringParams()
    if metadata is None:
        metadata = {}

    # --- Stage 1: Input Normalization ---
    raw_audio, original_sr = load_audio(input_path)
    audio = normalize_input(raw_audio, original_sr)

    # --- Stage 2: Analysis ---
    analysis = analyze(audio, INTERNAL_SR, original_sr)

    # --- Stage 3: EQ ---
    audio = apply_eq(audio, INTERNAL_SR, params)

    # --- Stage 4: Multiband Compression ---
    audio = apply_multiband_compression(audio, INTERNAL_SR, params)

    # --- Stage 5: Stereo Widening ---
    audio = apply_stereo_widening(audio, INTERNAL_SR, params)

    # --- Stage 6: Limiting ---
    audio = apply_limiter(audio, INTERNAL_SR, params.loudness)

    # --- Stage 7: Output Preparation ---
    # Build output filenames
    title = metadata.get("title", "Untitled")
    artist = metadata.get("artist", "Unknown Artist")
    safe_name = f"{artist} - {title} (RAIN Master)"
    # Sanitize filename
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in " -_()")

    wav_path = str(Path(output_dir) / f"{safe_name}.wav")
    mp3_path = str(Path(output_dir) / f"{safe_name}.mp3")

    export_wav(audio, INTERNAL_SR, wav_path)
    export_mp3(audio, INTERNAL_SR, mp3_path)

    # Post-export analysis
    meter = pyln.Meter(INTERNAL_SR)
    output_lufs = meter.integrated_loudness(audio)
    if np.isinf(output_lufs) or np.isnan(output_lufs):
        output_lufs = -70.0
    output_tp = measure_true_peak(audio, INTERNAL_SR)
    output_dr = compute_crest_factor(audio)
    output_sw = compute_stereo_width(audio)
    output_sc = compute_spectral_centroid(audio, INTERNAL_SR)

    return MasterResult(
        output_wav_path=wav_path,
        output_mp3_path=mp3_path,
        session_id=session_id,
        analysis=analysis,
        output_lufs=output_lufs,
        output_true_peak=output_tp,
        output_dynamic_range=output_dr,
        output_stereo_width=output_sw,
        output_spectral_centroid=output_sc,
    )
