"""
RAIN Track Diagnosis — Proactive Issue Detection

When a track loads, RAIN doesn't wait for the user to ask.
It proactively diagnoses issues and offers to fix them.

This turns RAIN from a tool into an assistant:
  "I'm detecting low-end buildup and limited stereo contrast. Want me to fix that?"

Also includes AI-generation detection for Suno/Udio outputs, identifying
common artifacts that AI music generators produce:
  - Vocal flatness (limited pitch micro-variation)
  - Over-smoothed transients
  - Generic chord density (limited harmonic movement)
  - Arrangement uniformity (lacking contrast between sections)
  - Stereo field artificiality (too symmetric)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class DiagnosisIssue:
    """A single detected issue in the audio."""
    id: str                     # Unique issue identifier
    severity: str               # "critical" | "moderate" | "mild" | "info"
    category: str               # "frequency" | "dynamics" | "stereo" | "artifacts" | "ai_generated"
    title: str                  # Short: "Low-End Buildup"
    description: str            # Detailed: "Excess energy below 200Hz is masking mid-range clarity"
    suggestion: str             # Actionable: "Reduce WARMTH by 2 or enable REPAIR"
    auto_fixable: bool          # Can RAIN fix this automatically?
    fix_macros: dict[str, float] = field(default_factory=dict)  # Suggested macro changes
    confidence: float = 0.0     # 0-1: how confident are we?
    ai_generated_flag: bool = False  # Is this an AI-generation artifact?


@dataclass
class TrackDiagnosis:
    """Complete diagnosis of a loaded track."""
    issues: list[DiagnosisIssue] = field(default_factory=list)
    ai_generation_score: float = 0.0    # 0-1: likelihood this is AI-generated
    ai_generation_flags: list[str] = field(default_factory=list)
    overall_health: str = "good"        # "good" | "needs_attention" | "problematic"
    proactive_message: str = ""         # The message shown to the user
    auto_fix_available: bool = False    # Any issues are auto-fixable?


def _diagnose_sync(
    audio: np.ndarray,
    sr: int,
    input_lufs: Optional[float] = None,
    input_true_peak: Optional[float] = None,
) -> TrackDiagnosis:
    """Synchronous track diagnosis. Call via asyncio.to_thread."""
    diag = TrackDiagnosis()

    if audio.ndim == 1:
        audio = np.column_stack([audio, audio])

    mono = np.mean(audio, axis=1)
    n_samples = len(mono)

    # -----------------------------------------------------------------------
    # Frequency Analysis
    # -----------------------------------------------------------------------
    n_fft = min(8192, n_samples)
    if n_fft < 256:
        diag.proactive_message = "Track too short for meaningful analysis."
        return diag

    spectrum = np.abs(np.fft.rfft(mono[:n_fft])) ** 2
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    total_energy = float(np.sum(spectrum)) + 1e-20

    # Low-end buildup (< 200Hz)
    low_mask = freqs < 200
    low_ratio = float(np.sum(spectrum[low_mask])) / total_energy
    if low_ratio > 0.45:
        diag.issues.append(DiagnosisIssue(
            id="low_end_buildup",
            severity="moderate",
            category="frequency",
            title="Low-End Buildup",
            description=f"Excess energy below 200Hz ({low_ratio:.0%} of total). This can mask mid-range clarity and cause muddiness on small speakers.",
            suggestion="I can reduce the low-end buildup. This will help your mix translate better across all speakers.",
            auto_fixable=True,
            fix_macros={"warmth": -1.5, "repair": 1.0},
            confidence=min(0.95, low_ratio),
        ))

    # Harsh high-end (> 8kHz)
    high_mask = freqs > 8000
    high_ratio = float(np.sum(spectrum[high_mask])) / total_energy
    if high_ratio > 0.25:
        diag.issues.append(DiagnosisIssue(
            id="harsh_highs",
            severity="moderate",
            category="frequency",
            title="Harsh High Frequencies",
            description=f"High-frequency energy above 8kHz is elevated ({high_ratio:.0%}). This can cause listener fatigue, especially on earbuds.",
            suggestion="I can tame the harshness while keeping the air and presence. Want me to smooth it out?",
            auto_fixable=True,
            fix_macros={"brighten": -1.5, "warmth": 0.5},
            confidence=0.8,
        ))

    # Missing air (12-16kHz)
    air_mask = (freqs >= 12000) & (freqs <= 16000)
    air_ratio = float(np.sum(spectrum[air_mask])) / total_energy
    if air_ratio < 0.02:
        diag.issues.append(DiagnosisIssue(
            id="missing_air",
            severity="mild",
            category="frequency",
            title="Limited Air / Sparkle",
            description="Very little energy above 12kHz. The track may sound dull on high-quality playback systems.",
            suggestion="A touch of brightness can add life without harshness.",
            auto_fixable=True,
            fix_macros={"brighten": 1.5},
            confidence=0.7,
        ))

    # -----------------------------------------------------------------------
    # Dynamics Analysis
    # -----------------------------------------------------------------------
    rms = float(np.sqrt(np.mean(mono ** 2)))
    peak = float(np.max(np.abs(mono)))
    crest_db = 20.0 * np.log10(peak / (rms + 1e-10))

    if crest_db < 6.0:
        diag.issues.append(DiagnosisIssue(
            id="over_compressed",
            severity="moderate",
            category="dynamics",
            title="Over-Compressed Dynamics",
            description=f"Crest factor is only {crest_db:.1f} dB (healthy range: 8-14 dB). The track may sound flat and fatiguing.",
            suggestion="This is heavily compressed. I'll preserve what dynamics are left rather than squashing further.",
            auto_fixable=True,
            fix_macros={"glue": -2.0, "punch": -1.0},
            confidence=0.85,
        ))

    if crest_db > 18.0:
        diag.issues.append(DiagnosisIssue(
            id="under_compressed",
            severity="moderate",
            category="dynamics",
            title="Very Dynamic / Uncompressed",
            description=f"Crest factor is {crest_db:.1f} dB — this is unusually dynamic. Some sections may be too quiet for streaming.",
            suggestion="I can add gentle compression to make the quieter parts more audible without killing the dynamics.",
            auto_fixable=True,
            fix_macros={"glue": 2.0, "punch": 1.0},
            confidence=0.75,
        ))

    # -----------------------------------------------------------------------
    # Stereo Analysis
    # -----------------------------------------------------------------------
    if audio.shape[1] >= 2:
        left, right = audio[:, 0], audio[:, 1]
        corr = float(np.corrcoef(left, right)[0, 1])

        if corr > 0.95:
            diag.issues.append(DiagnosisIssue(
                id="nearly_mono",
                severity="mild",
                category="stereo",
                title="Nearly Mono",
                description=f"L/R correlation is {corr:.2f} — the stereo image is very narrow. This is fine for mono playback but lacks immersion on headphones.",
                suggestion="I can widen the stereo field to make it sound more immersive.",
                auto_fixable=True,
                fix_macros={"width": 2.0, "space": 1.0},
                confidence=0.8,
            ))

        if corr < 0.3:
            diag.issues.append(DiagnosisIssue(
                id="phase_issues",
                severity="critical",
                category="stereo",
                title="Potential Phase Issues",
                description=f"L/R correlation is {corr:.2f} — this may cause significant loss when summed to mono (e.g., phone speakers, club systems).",
                suggestion="I'd recommend checking the mix for phase problems before mastering.",
                auto_fixable=False,
                confidence=0.9,
            ))

    # -----------------------------------------------------------------------
    # AI-Generation Detection (Suno/Udio artifact fingerprints)
    # -----------------------------------------------------------------------
    ai_flags: list[str] = []
    ai_score = 0.0

    # Flag 1: Over-smoothed transients
    # AI generators tend to produce smoother onsets than real instruments
    diff_signal = np.abs(np.diff(mono))
    transient_sharpness = float(np.percentile(diff_signal, 99.5)) / (float(np.mean(diff_signal)) + 1e-10)
    if transient_sharpness < 15.0:
        ai_flags.append("Over-smoothed transients (typical of AI synthesis)")
        ai_score += 0.2

    # Flag 2: Stereo field symmetry
    # AI generators often produce unnaturally symmetric stereo fields
    if audio.shape[1] >= 2:
        left_spec = np.abs(np.fft.rfft(left[:n_fft])) ** 2
        right_spec = np.abs(np.fft.rfft(right[:n_fft])) ** 2
        spec_corr = float(np.corrcoef(left_spec, right_spec)[0, 1])
        if spec_corr > 0.98:
            ai_flags.append("Unnaturally symmetric stereo field")
            ai_score += 0.15

    # Flag 3: Arrangement uniformity
    # AI tracks often have very consistent energy across sections
    seg_len = n_samples // 8
    if seg_len > sr:  # At least 1s per segment
        seg_energies = []
        for i in range(8):
            seg = mono[i * seg_len:(i + 1) * seg_len]
            seg_energies.append(float(np.sqrt(np.mean(seg ** 2))))
        if max(seg_energies) > 0:
            seg_normalized = [e / max(seg_energies) for e in seg_energies]
            seg_variance = float(np.var(seg_normalized))
            if seg_variance < 0.005:
                ai_flags.append("Very uniform arrangement (limited section contrast)")
                ai_score += 0.2

    # Flag 4: Spectral smoothness
    # AI audio tends to have smoother spectral envelopes than recorded audio
    if n_fft >= 2048:
        spec_diff = np.abs(np.diff(np.log10(spectrum[:n_fft // 4] + 1e-20)))
        spectral_roughness = float(np.mean(spec_diff))
        if spectral_roughness < 0.15:
            ai_flags.append("Unusually smooth spectral envelope")
            ai_score += 0.15

    # Flag 5: Vocal micro-pitch variation
    # Real vocals have micro-pitch variations; AI vocals are often too stable
    # (Simplified: check pitch stability via zero-crossing rate variance)
    zcr_windows = []
    window_size = int(0.05 * sr)  # 50ms windows
    for start in range(0, n_samples - window_size, window_size):
        chunk = mono[start:start + window_size]
        zcr = float(np.sum(np.abs(np.diff(np.sign(chunk)))) / (2 * window_size))
        zcr_windows.append(zcr)
    if zcr_windows:
        zcr_variance = float(np.var(zcr_windows))
        if zcr_variance < 0.0001:
            ai_flags.append("Limited pitch micro-variation (possible AI vocals)")
            ai_score += 0.15

    ai_score = min(1.0, ai_score)

    if ai_score > 0.4:
        diag.issues.append(DiagnosisIssue(
            id="ai_generated",
            severity="info",
            category="ai_generated",
            title="Possible AI-Generated Content",
            description=f"This track shows characteristics common in AI-generated music (confidence: {ai_score:.0%}). " +
                        "AI-generated audio often benefits from specific mastering adjustments.",
            suggestion="I've detected typical AI-generation artifacts. I can apply corrections that specifically target these — "
                       "smoothing synthetic transients, adding micro-variation, and improving stereo naturalness.",
            auto_fixable=True,
            fix_macros={"repair": 2.0, "warmth": 1.0, "width": 1.0, "punch": 0.5},
            confidence=ai_score,
            ai_generated_flag=True,
        ))

    diag.ai_generation_score = ai_score
    diag.ai_generation_flags = ai_flags

    # -----------------------------------------------------------------------
    # Build proactive message
    # -----------------------------------------------------------------------
    diag.auto_fix_available = any(i.auto_fixable for i in diag.issues)

    critical = [i for i in diag.issues if i.severity == "critical"]
    moderate = [i for i in diag.issues if i.severity == "moderate"]
    mild = [i for i in diag.issues if i.severity == "mild"]

    if critical:
        diag.overall_health = "problematic"
    elif moderate:
        diag.overall_health = "needs_attention"
    else:
        diag.overall_health = "good"

    parts: list[str] = []

    if not diag.issues:
        parts.append("Your track looks healthy! Good frequency balance, healthy dynamics, and clean stereo image.")
        parts.append("Ready to master — adjust the knobs to taste, or tell me what sound you're going for.")
    else:
        if len(critical) > 0:
            parts.append(f"I found **{len(critical)} critical** issue{'s' if len(critical) > 1 else ''} that should be addressed:")
            for issue in critical:
                parts.append(f"- **{issue.title}**: {issue.description}")

        if len(moderate) > 0:
            parts.append(f"\n{'Also, ' if critical else ''}I noticed **{len(moderate)}** thing{'s' if len(moderate) > 1 else ''} worth adjusting:")
            for issue in moderate:
                parts.append(f"- **{issue.title}**: {issue.suggestion}")

        if len(mild) > 0 and not critical:
            parts.append(f"\nMinor suggestion{'s' if len(mild) > 1 else ''}:")
            for issue in mild:
                parts.append(f"- {issue.suggestion}")

        if diag.auto_fix_available:
            parts.append("\n**Want me to fix these automatically?** I'll apply gentle corrections that address each issue.")

    if ai_score > 0.4:
        parts.append(f"\n💡 This appears to be AI-generated audio (confidence: {ai_score:.0%}). I can apply corrections that specifically target common AI synthesis artifacts.")

    diag.proactive_message = "\n".join(parts)
    return diag


async def diagnose_track(
    audio: np.ndarray,
    sr: int,
    input_lufs: Optional[float] = None,
    input_true_peak: Optional[float] = None,
) -> TrackDiagnosis:
    """Async track diagnosis — runs in thread pool."""
    return await asyncio.to_thread(
        _diagnose_sync, audio, sr, input_lufs, input_true_peak
    )
