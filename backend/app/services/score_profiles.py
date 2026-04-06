"""
RAIN Score Profile Calibration — Same Track, Different Valid Scores

Different users value different things:
  - Club producers → loudness + punch
  - Audiophiles → dynamics + translation
  - Pop artists → clarity + vocal presence
  - Lo-fi creators → warmth + character

Same track → different valid RAIN Scores depending on the scoring profile.

Also includes confidence-weighted emotional scoring to prevent users
from distrusting absolute emotional metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Score Profile Definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScoreWeights:
    """Weight distribution for RAIN Score components (must sum to 100)."""
    loudness: float        # Max contribution to overall score
    true_peak: float
    spectral: float
    stereo: float
    crest_preservation: float
    micro_dynamics: float
    mono_compat: float
    codec_resilience: float
    energy_arc: float
    tension_index: float
    presence: float

    @property
    def total(self) -> float:
        return (
            self.loudness + self.true_peak + self.spectral + self.stereo +
            self.crest_preservation + self.micro_dynamics +
            self.mono_compat + self.codec_resilience +
            self.energy_arc + self.tension_index + self.presence
        )


# The profiles — each tells the scoring system what matters most
PROFILES: dict[str, ScoreWeights] = {
    "streaming": ScoreWeights(
        # Standard streaming optimization (Spotify, Apple, etc.)
        loudness=25, true_peak=15, spectral=10, stereo=10,
        crest_preservation=8, micro_dynamics=7,
        mono_compat=5, codec_resilience=5,
        energy_arc=5, tension_index=5, presence=5,
    ),
    "club": ScoreWeights(
        # Club/DJ: loudness and punch are king, dynamics less important
        loudness=30, true_peak=10, spectral=8, stereo=5,
        crest_preservation=3, micro_dynamics=4,
        mono_compat=8, codec_resilience=7,
        energy_arc=10, tension_index=10, presence=5,
    ),
    "audiophile": ScoreWeights(
        # Audiophile: dynamics, translation, and stereo quality dominate
        loudness=10, true_peak=15, spectral=12, stereo=13,
        crest_preservation=12, micro_dynamics=10,
        mono_compat=3, codec_resilience=3,
        energy_arc=7, tension_index=8, presence=7,
    ),
    "vocal": ScoreWeights(
        # Vocal-forward (pop, R&B, podcast): presence and clarity
        loudness=20, true_peak=12, spectral=8, stereo=8,
        crest_preservation=7, micro_dynamics=5,
        mono_compat=5, codec_resilience=5,
        energy_arc=5, tension_index=5, presence=20,
    ),
    "lofi": ScoreWeights(
        # Lo-fi/chill: character matters more than compliance
        loudness=10, true_peak=10, spectral=8, stereo=10,
        crest_preservation=5, micro_dynamics=7,
        mono_compat=3, codec_resilience=3,
        energy_arc=12, tension_index=12, presence=20,
    ),
    "broadcast": ScoreWeights(
        # Broadcast/radio: strict compliance + translation
        loudness=25, true_peak=20, spectral=10, stereo=5,
        crest_preservation=5, micro_dynamics=5,
        mono_compat=10, codec_resilience=10,
        energy_arc=3, tension_index=3, presence=4,
    ),
}

DEFAULT_PROFILE = "streaming"


@dataclass
class CalibratedScore:
    """RAIN Score with profile context and confidence."""
    overall: int
    profile: str
    profile_label: str

    # Component scores (normalized to profile weights)
    components: dict[str, ComponentScore] = field(default_factory=dict)

    # Confidence
    overall_confidence: float = 0.0  # 0-1: how confident are we in this score?
    confidence_factors: list[str] = field(default_factory=list)

    # Verdict
    verdict: str = ""
    release_ready: bool = False

    # Descriptive emotional summary (not absolute numbers)
    emotional_summary: str = ""

    # Comparison to other profiles
    profile_comparison: dict[str, int] = field(default_factory=dict)


@dataclass
class ComponentScore:
    """Single component of the RAIN Score."""
    raw: float           # Unweighted score (0-max_possible)
    weighted: float      # Weighted contribution to overall
    max_possible: float  # Maximum this component can contribute
    percentage: float    # raw / max_possible as 0-100%
    label: str           # Human-readable: "Loudness Compliance"
    detail: str          # "−14.2 LUFS (target: −14.0, error: 0.2 LU)"
    confidence: float    # 0-1: confidence in this measurement


# ---------------------------------------------------------------------------
# Profile Labels
# ---------------------------------------------------------------------------

PROFILE_LABELS: dict[str, str] = {
    "streaming": "Streaming Optimized",
    "club": "Club / DJ Ready",
    "audiophile": "Audiophile Grade",
    "vocal": "Vocal-Forward",
    "lofi": "Lo-Fi / Character",
    "broadcast": "Broadcast Compliant",
}


# ---------------------------------------------------------------------------
# Confidence Estimation
# ---------------------------------------------------------------------------

def estimate_confidence(
    components: dict[str, ComponentScore],
    audio_duration: float,
    has_input_reference: bool,
) -> tuple[float, list[str]]:
    """
    Estimate overall score confidence.

    Confidence is lower when:
    - Track is very short (< 30s) — statistics are unreliable
    - No input reference (can't measure crest preservation)
    - Emotional metrics are in ambiguous zones
    - Spectral analysis uses small FFT windows

    Returns (confidence_0_to_1, [reason_strings])
    """
    confidence = 0.85  # Base confidence
    factors: list[str] = []

    if audio_duration < 30.0:
        confidence -= 0.15
        factors.append(f"Short track ({audio_duration:.0f}s) — statistics less reliable")

    if audio_duration < 10.0:
        confidence -= 0.20
        factors.append("Very short track — emotional metrics are estimates only")

    if not has_input_reference:
        confidence -= 0.10
        factors.append("No input reference — crest preservation is estimated, not measured")

    # Check emotional component confidence
    for name in ("energy_arc", "tension_index", "presence"):
        comp = components.get(name)
        if comp and comp.confidence < 0.5:
            confidence -= 0.05
            factors.append(f"{comp.label}: medium confidence ({comp.confidence:.0%})")

    confidence = max(0.1, min(1.0, confidence))

    if not factors:
        factors.append("High confidence — sufficient track length and reference data")

    return round(confidence, 2), factors


# ---------------------------------------------------------------------------
# Emotional Summary Generator
# ---------------------------------------------------------------------------

def generate_emotional_summary(
    energy_arc: float,
    tension_index: float,
    presence: float,
    profile: str,
) -> str:
    """
    Generate a DESCRIPTIVE emotional summary instead of absolute numbers.

    "This track shows strong energy consistency but limited dynamic contrast"
    NOT "Emotional Impact: 11/15"
    """
    parts: list[str] = []

    # Energy arc interpretation
    if energy_arc > 4.0:
        parts.append("strong dynamic shape with clear energy builds")
    elif energy_arc > 2.5:
        parts.append("moderate energy variation throughout")
    else:
        parts.append("relatively consistent energy level")

    # Tension interpretation
    if tension_index > 4.0:
        parts.append("good dynamic contrast between sections")
    elif tension_index > 2.5:
        parts.append("moderate dynamic contrast")
    else:
        parts.append("limited dynamic contrast — the track feels flat dynamically")

    # Presence interpretation
    if presence > 4.0:
        parts.append("clear lead element presence")
    elif presence > 2.5:
        parts.append("adequate lead presence")
    else:
        parts.append("the lead element may be buried in the mix")

    summary = "This track shows " + parts[0]
    if len(parts) > 1:
        summary += ", " + parts[1]
    if len(parts) > 2:
        summary += ", and " + parts[2]

    summary += "."

    # Profile-specific commentary
    if profile == "club" and energy_arc < 3.0:
        summary += " For club use, consider adding more dynamic build/drop contrast."
    elif profile == "audiophile" and tension_index < 2.5:
        summary += " Audiophile listeners may find the dynamics too compressed."
    elif profile == "vocal" and presence < 3.0:
        summary += " The vocal may need more presence for this style."

    return summary


# ---------------------------------------------------------------------------
# Score Calibration — apply profile weights to raw scores
# ---------------------------------------------------------------------------

def calibrate_score(
    raw_scores: dict[str, float],
    raw_maxes: dict[str, float],
    raw_details: dict[str, str],
    audio_duration: float = 180.0,
    has_input_reference: bool = False,
    profile: str = DEFAULT_PROFILE,
) -> CalibratedScore:
    """
    Apply profile-specific weighting to raw score components.

    Args:
        raw_scores: {component_name: raw_score}
        raw_maxes: {component_name: max_possible_raw_score}
        raw_details: {component_name: detail_string}
        audio_duration: Track duration in seconds
        has_input_reference: Whether input audio was provided for comparison
        profile: Scoring profile name

    Returns:
        CalibratedScore with profile-weighted results and confidence.
    """
    weights = PROFILES.get(profile, PROFILES[DEFAULT_PROFILE])
    label = PROFILE_LABELS.get(profile, profile.title())

    weight_map: dict[str, float] = {
        "loudness": weights.loudness,
        "true_peak": weights.true_peak,
        "spectral": weights.spectral,
        "stereo": weights.stereo,
        "crest_preservation": weights.crest_preservation,
        "micro_dynamics": weights.micro_dynamics,
        "mono_compat": weights.mono_compat,
        "codec_resilience": weights.codec_resilience,
        "energy_arc": weights.energy_arc,
        "tension_index": weights.tension_index,
        "presence": weights.presence,
    }

    component_labels: dict[str, str] = {
        "loudness": "Loudness Compliance",
        "true_peak": "True Peak Headroom",
        "spectral": "Spectral Balance",
        "stereo": "Stereo Field",
        "crest_preservation": "Dynamic Preservation",
        "micro_dynamics": "Micro-Dynamics",
        "mono_compat": "Mono Compatibility",
        "codec_resilience": "Codec Resilience",
        "energy_arc": "Energy Arc",
        "tension_index": "Dynamic Contrast",
        "presence": "Lead Presence",
    }

    components: dict[str, ComponentScore] = {}
    total_weighted = 0.0

    for name, weight in weight_map.items():
        raw = raw_scores.get(name, 0.0)
        raw_max = raw_maxes.get(name, 10.0)

        # Normalize raw score to 0-1, then scale by profile weight
        normalized = min(1.0, raw / raw_max) if raw_max > 0 else 0.0
        weighted = normalized * weight
        total_weighted += weighted

        # Component confidence (emotional metrics get lower confidence)
        comp_confidence = 0.9
        if name in ("energy_arc", "tension_index", "presence"):
            comp_confidence = 0.6 if audio_duration > 30 else 0.3

        components[name] = ComponentScore(
            raw=round(raw, 1),
            weighted=round(weighted, 1),
            max_possible=weight,
            percentage=round(normalized * 100, 0),
            label=component_labels.get(name, name),
            detail=raw_details.get(name, ""),
            confidence=comp_confidence,
        )

    overall = round(min(100.0, total_weighted))

    # Confidence
    conf, conf_factors = estimate_confidence(components, audio_duration, has_input_reference)

    # Emotional summary
    emotional = generate_emotional_summary(
        raw_scores.get("energy_arc", 2.5),
        raw_scores.get("tension_index", 2.5),
        raw_scores.get("presence", 2.5),
        profile,
    )

    # Verdict
    if overall >= 85:
        verdict = f"Release-ready ({label}). Professional quality for this profile."
        release_ready = True
    elif overall >= 70:
        verdict = f"Good quality ({label}). Minor adjustments could improve compliance."
        release_ready = True
    elif overall >= 50:
        verdict = f"Needs work ({label}). Check the component breakdown for specifics."
        release_ready = False
    else:
        verdict = f"Significant issues ({label}). Review loudness and dynamic balance."
        release_ready = False

    # Cross-profile comparison
    comparison: dict[str, int] = {}
    for p_name, p_weights in PROFILES.items():
        if p_name == profile:
            continue
        p_total = 0.0
        p_weight_map = {
            "loudness": p_weights.loudness, "true_peak": p_weights.true_peak,
            "spectral": p_weights.spectral, "stereo": p_weights.stereo,
            "crest_preservation": p_weights.crest_preservation,
            "micro_dynamics": p_weights.micro_dynamics,
            "mono_compat": p_weights.mono_compat,
            "codec_resilience": p_weights.codec_resilience,
            "energy_arc": p_weights.energy_arc, "tension_index": p_weights.tension_index,
            "presence": p_weights.presence,
        }
        for c_name, c_weight in p_weight_map.items():
            raw = raw_scores.get(c_name, 0.0)
            raw_max = raw_maxes.get(c_name, 10.0)
            normalized = min(1.0, raw / raw_max) if raw_max > 0 else 0.0
            p_total += normalized * c_weight
        comparison[p_name] = round(min(100.0, p_total))

    return CalibratedScore(
        overall=overall,
        profile=profile,
        profile_label=label,
        components=components,
        overall_confidence=conf,
        confidence_factors=conf_factors,
        verdict=verdict,
        release_ready=release_ready,
        emotional_summary=emotional,
        profile_comparison=comparison,
    )
