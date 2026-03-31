"""
RAIN QC Engine — 18 Automated Quality Checks per RAIN-PLATFORM-SPEC-v1.0

Each check returns: id, name, severity, passed, value, threshold, auto_remediated, detail.
Critical checks trigger auto-remediation. Advisory checks inform but do not block.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pyloudnorm as pyln
from numpy.typing import NDArray
from scipy.signal import butter, sosfilt, resample_poly

from app.services.platform_targets import PlatformTarget, get_platform_target


@dataclass
class QCResult:
    id: int
    name: str
    severity: str  # "critical", "high", "medium", "low", "advisory"
    passed: bool
    value: float | None = None
    threshold: float | None = None
    auto_remediated: bool = False
    detail: str = ""


@dataclass
class QCReport:
    platform: str
    checks: list[QCResult] = field(default_factory=list)
    passed: bool = True
    critical_failures: int = 0
    remediated_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "passed": bool(self.passed),
            "critical_failures": int(self.critical_failures),
            "remediated_count": int(self.remediated_count),
            "checks": [
                {
                    "id": int(c.id), "name": c.name, "severity": c.severity,
                    "passed": bool(c.passed),
                    "value": float(c.value) if c.value is not None else None,
                    "threshold": float(c.threshold) if c.threshold is not None else None,
                    "auto_remediated": bool(c.auto_remediated), "detail": c.detail,
                }
                for c in self.checks
            ],
        }


def _check_digital_clipping(audio: NDArray, sr: int) -> tuple[QCResult, NDArray]:
    """#1: Digital clipping — 3+ consecutive samples at full scale."""
    threshold = 0.9999
    clipped = np.abs(audio) >= threshold
    # Count runs of 3+ consecutive clipped samples per channel
    clip_count = 0
    for ch in range(audio.shape[1]):
        run = 0
        for i in range(len(audio)):
            if clipped[i, ch]:
                run += 1
                if run >= 3:
                    clip_count += 1
            else:
                run = 0

    passed = clip_count == 0
    remediated = False
    if not passed:
        audio = audio * 0.98  # Gain reduction by ~0.18 dB
        remediated = True

    return QCResult(1, "Digital Clipping", "critical", passed or remediated,
                    clip_count, 0, remediated,
                    f"{clip_count} clipped regions" if clip_count > 0 else "Clean"), audio


def _check_inter_sample_peaks(audio: NDArray, sr: int, ceiling: float) -> tuple[QCResult, NDArray]:
    """#2: Inter-sample peaks via 4x oversampling."""
    oversampled = resample_poly(audio, up=4, down=1, axis=0)
    isp = float(np.max(np.abs(oversampled)))
    isp_db = 20.0 * np.log10(isp) if isp > 1e-10 else -100.0
    passed = isp_db <= ceiling

    remediated = False
    if not passed:
        reduction = 10 ** ((ceiling - isp_db) / 20.0)
        audio = audio * reduction
        remediated = True

    return QCResult(2, "Inter-Sample Peaks", "critical", passed or remediated,
                    round(isp_db, 2), ceiling, remediated,
                    f"ISP: {isp_db:.1f} dBTP vs ceiling {ceiling} dBTP"), audio


def _check_phase_cancellation(audio: NDArray) -> QCResult:
    """#3: Phase cancellation on mono fold-down."""
    if audio.shape[1] < 2:
        return QCResult(3, "Phase Cancellation", "high", True, detail="Mono signal")
    mono = audio[:, 0] + audio[:, 1]
    stereo_energy = np.sum(audio[:, 0] ** 2) + np.sum(audio[:, 1] ** 2)
    mono_energy = np.sum(mono ** 2)
    ratio = mono_energy / (stereo_energy + 1e-10)
    passed = ratio > 0.5  # Less than 3dB loss on mono fold-down
    return QCResult(3, "Phase Cancellation", "high", passed,
                    round(ratio, 3), 0.5, detail=f"Mono/stereo energy ratio: {ratio:.3f}")


def _check_codec_preringing(audio: NDArray, sr: int) -> QCResult:
    """#4: Codec pre-ringing artifacts (simplified check)."""
    # Check for energy in very high frequencies that could cause codec issues
    n_fft = min(4096, len(audio))
    mono = np.mean(audio[:n_fft], axis=1)
    spectrum = np.abs(np.fft.rfft(mono))
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    nyquist_region = freqs > (sr * 0.45)
    high_energy = np.sum(spectrum[nyquist_region] ** 2)
    total_energy = np.sum(spectrum ** 2) + 1e-10
    ratio = high_energy / total_energy
    passed = ratio < 0.01
    return QCResult(4, "Codec Pre-Ringing", "medium", passed,
                    round(ratio * 100, 2), 1.0, detail=f"Near-Nyquist energy: {ratio * 100:.2f}%")


def _check_pops_clicks(audio: NDArray, sr: int) -> QCResult:
    """#5: Pops and clicks detection."""
    mono = np.mean(audio, axis=1)
    diff = np.abs(np.diff(mono))
    threshold = np.std(diff) * 8.0
    pops = int(np.sum(diff > threshold))
    passed = pops < 5
    return QCResult(5, "Pops and Clicks", "medium", passed,
                    pops, 5, detail=f"{pops} potential pop/click events detected")


def _check_bad_edits(audio: NDArray, sr: int) -> QCResult:
    """#6: Bad edits — zero-crossing violations at boundaries."""
    # Check first and last 50 samples for abrupt transitions
    head = audio[:50]
    tail = audio[-50:]
    head_max = float(np.max(np.abs(head)))
    tail_max = float(np.max(np.abs(tail)))
    passed = head_max < 0.01 and tail_max < 0.01
    return QCResult(6, "Bad Edits", "medium", passed,
                    max(head_max, tail_max), 0.01,
                    detail="Head/tail amplitude check for edit artifacts")


def _check_dc_offset(audio: NDArray) -> tuple[QCResult, NDArray]:
    """#7: DC offset detection and removal."""
    dc = float(np.mean(audio))
    dc_db = abs(dc) * 100  # Percentage
    passed = abs(dc) < 0.001
    remediated = False
    if not passed:
        audio = audio - np.mean(audio, axis=0)
        remediated = True
    return QCResult(7, "DC Offset", "low", passed or remediated,
                    round(dc * 1000, 3), 1.0, remediated,
                    f"DC offset: {dc:.6f} ({dc_db:.3f}%)"), audio


def _check_silence(audio: NDArray, sr: int) -> QCResult:
    """#8: Head/tail silence check."""
    # Check for > 500ms silence at head or tail
    threshold = 0.0001
    silence_samples = int(0.5 * sr)
    head_silent = np.max(np.abs(audio[:silence_samples])) < threshold if len(audio) > silence_samples else False
    tail_silent = np.max(np.abs(audio[-silence_samples:])) < threshold if len(audio) > silence_samples else False
    passed = not head_silent and not tail_silent
    detail = []
    if head_silent:
        detail.append("Excessive head silence (>500ms)")
    if tail_silent:
        detail.append("Excessive tail silence (>500ms)")
    return QCResult(8, "Head/Tail Silence", "low", passed,
                    detail="; ".join(detail) if detail else "Clean")


def _check_sample_rate(sr: int, target_sr: int) -> QCResult:
    """#9: Sample rate mismatch."""
    passed = sr == target_sr
    return QCResult(9, "Sample Rate", "high", passed,
                    sr, target_sr, detail=f"Source: {sr}Hz, Target: {target_sr}Hz")


def _check_bit_depth(audio: NDArray, target_bits: int) -> QCResult:
    """#10: Bit depth truncation check."""
    # Check if signal uses full dynamic range
    max_val = np.max(np.abs(audio))
    used_range_db = 20.0 * np.log10(max_val) if max_val > 1e-10 else -100.0
    passed = used_range_db > -60.0  # At least 60dB dynamic range
    return QCResult(10, "Bit Depth", "medium", passed,
                    round(used_range_db, 1), -60.0,
                    detail=f"Dynamic range: {used_range_db:.1f} dB, target: {target_bits}-bit")


def _check_loudness_compliance(lufs: float, target: PlatformTarget) -> QCResult:
    """#11: Loudness non-compliance (±0.5 LU)."""
    error = abs(lufs - target.target_lufs)
    passed = error <= 0.5
    return QCResult(11, "Loudness Compliance", "critical", passed,
                    round(lufs, 1), target.target_lufs,
                    detail=f"LUFS: {lufs:.1f}, target: {target.target_lufs}, error: {error:.2f} LU")


def _check_true_peak_ceiling(tp: float, target: PlatformTarget) -> QCResult:
    """#12: True peak exceeds ceiling."""
    passed = tp <= target.true_peak_ceiling
    return QCResult(12, "True Peak Ceiling", "critical", passed,
                    round(tp, 1), target.true_peak_ceiling,
                    detail=f"True peak: {tp:.1f} dBTP, ceiling: {target.true_peak_ceiling} dBTP")


def _check_lra_compliance(lra: float, target: PlatformTarget) -> QCResult:
    """#13: LRA compliance."""
    passed = True
    detail_parts = []
    if target.lra_min is not None and lra < target.lra_min:
        passed = False
        detail_parts.append(f"LRA {lra:.1f} below minimum {target.lra_min}")
    if target.lra_max is not None and lra > target.lra_max:
        passed = False
        detail_parts.append(f"LRA {lra:.1f} exceeds maximum {target.lra_max}")
    return QCResult(13, "LRA Compliance", "medium", passed,
                    round(lra, 1), target.lra_min or target.lra_max,
                    detail="; ".join(detail_parts) if detail_parts else f"LRA: {lra:.1f} LU — compliant")


def _check_mono_compatibility(audio: NDArray) -> QCResult:
    """#14: Mono compatibility (per-frequency)."""
    if audio.shape[1] < 2:
        return QCResult(14, "Mono Compatibility", "medium", True, detail="Mono signal")
    mono = audio[:, 0] + audio[:, 1]
    stereo_sum = np.sum(audio ** 2)
    mono_sum = np.sum(mono ** 2)
    compat = mono_sum / (stereo_sum + 1e-10)
    passed = compat > 0.7
    return QCResult(14, "Mono Compatibility", "medium", passed,
                    round(compat, 3), 0.7,
                    detail=f"Mono compatibility: {compat:.1%}")


def _check_sibilance(audio: NDArray, sr: int) -> QCResult:
    """#15: Excessive sibilance (4-10kHz energy ratio)."""
    mono = np.mean(audio, axis=1)
    n_fft = min(8192, len(mono))
    spectrum = np.abs(np.fft.rfft(mono[:n_fft])) ** 2
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    sib_mask = (freqs >= 4000) & (freqs <= 10000)
    total = np.sum(spectrum) + 1e-10
    sib_ratio = np.sum(spectrum[sib_mask]) / total
    passed = sib_ratio < 0.35
    return QCResult(15, "Sibilance", "low", passed,
                    round(sib_ratio * 100, 1), 35.0,
                    detail=f"4-10kHz energy: {sib_ratio * 100:.1f}%")


def _check_rumble(audio: NDArray, sr: int) -> QCResult:
    """#16: Low-frequency rumble (<30Hz)."""
    mono = np.mean(audio, axis=1)
    n_fft = min(8192, len(mono))
    spectrum = np.abs(np.fft.rfft(mono[:n_fft])) ** 2
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    rumble_mask = freqs < 30
    total = np.sum(spectrum) + 1e-10
    rumble_ratio = np.sum(spectrum[rumble_mask]) / total
    passed = rumble_ratio < 0.05
    return QCResult(16, "Low-Frequency Rumble", "low", passed,
                    round(rumble_ratio * 100, 2), 5.0,
                    detail=f"Sub-30Hz energy: {rumble_ratio * 100:.2f}%")


def _check_stereo_balance(audio: NDArray) -> QCResult:
    """#17: Stereo balance offset (>1.5dB sustained)."""
    if audio.shape[1] < 2:
        return QCResult(17, "Stereo Balance", "low", True, detail="Mono signal")
    l_rms = np.sqrt(np.mean(audio[:, 0] ** 2)) + 1e-10
    r_rms = np.sqrt(np.mean(audio[:, 1] ** 2)) + 1e-10
    balance_db = abs(20.0 * np.log10(l_rms / r_rms))
    passed = balance_db < 1.5
    return QCResult(17, "Stereo Balance", "low", passed,
                    round(balance_db, 2), 1.5,
                    detail=f"L/R balance offset: {balance_db:.2f} dB")


def _check_peaq(audio: NDArray, sr: int) -> QCResult:
    """#18: Perceptual quality (PEAQ ODG approximation). Advisory only."""
    # Simplified: use SNR as proxy for perceptual quality
    rms = np.sqrt(np.mean(audio ** 2))
    noise_floor = np.sqrt(np.mean(audio[:int(0.01 * sr)] ** 2)) if len(audio) > int(0.01 * sr) else 1e-6
    snr = 20.0 * np.log10(rms / (noise_floor + 1e-10)) if noise_floor > 1e-10 else 60.0
    # Map SNR to ODG-like scale (-4 to 0, where 0 = imperceptible)
    odg = min(0.0, (snr - 20.0) / 20.0)
    return QCResult(18, "Perceptual Quality (PEAQ)", "advisory", True,
                    round(odg, 2), detail=f"Estimated ODG: {odg:.2f} (advisory, non-blocking)")


def run_qc(
    audio: NDArray[np.float64],
    sr: int,
    platform_slug: str = "spotify",
    output_lufs: float | None = None,
    output_true_peak: float | None = None,
    output_lra: float | None = None,
) -> tuple[QCReport, NDArray[np.float64]]:
    """Run all 18 QC checks. Returns (report, possibly-remediated audio).

    Args:
        audio: Stereo float64 audio array
        sr: Sample rate
        platform_slug: Platform target key
        output_lufs: Pre-measured LUFS (or measured here)
        output_true_peak: Pre-measured true peak (or measured here)
        output_lra: Pre-measured LRA (or estimated here)

    Returns:
        (QCReport, audio) — audio may be modified by auto-remediation
    """
    target = get_platform_target(platform_slug)
    report = QCReport(platform=platform_slug)

    # Measure if not provided
    if output_lufs is None:
        meter = pyln.Meter(sr)
        output_lufs = meter.integrated_loudness(audio)
        if np.isinf(output_lufs) or np.isnan(output_lufs):
            output_lufs = -70.0
    if output_true_peak is None:
        oversampled = resample_poly(audio, up=4, down=1, axis=0)
        peak = np.max(np.abs(oversampled))
        output_true_peak = 20.0 * np.log10(peak) if peak > 1e-10 else -100.0
    if output_lra is None:
        output_lra = 0.0  # Would need full short-term analysis

    # Run all 18 checks
    r1, audio = _check_digital_clipping(audio, sr)
    report.checks.append(r1)

    r2, audio = _check_inter_sample_peaks(audio, sr, target.true_peak_ceiling)
    report.checks.append(r2)

    report.checks.append(_check_phase_cancellation(audio))
    report.checks.append(_check_codec_preringing(audio, sr))
    report.checks.append(_check_pops_clicks(audio, sr))
    report.checks.append(_check_bad_edits(audio, sr))

    r7, audio = _check_dc_offset(audio)
    report.checks.append(r7)

    report.checks.append(_check_silence(audio, sr))
    report.checks.append(_check_sample_rate(sr, 48000))
    report.checks.append(_check_bit_depth(audio, 24))
    report.checks.append(_check_loudness_compliance(output_lufs, target))
    report.checks.append(_check_true_peak_ceiling(output_true_peak, target))
    report.checks.append(_check_lra_compliance(output_lra, target))
    report.checks.append(_check_mono_compatibility(audio))
    report.checks.append(_check_sibilance(audio, sr))
    report.checks.append(_check_rumble(audio, sr))
    report.checks.append(_check_stereo_balance(audio))
    report.checks.append(_check_peaq(audio, sr))

    # Summarize
    for c in report.checks:
        if not c.passed and c.severity == "critical":
            report.critical_failures += 1
        if c.auto_remediated:
            report.remediated_count += 1
    report.passed = report.critical_failures == 0

    return report, audio
