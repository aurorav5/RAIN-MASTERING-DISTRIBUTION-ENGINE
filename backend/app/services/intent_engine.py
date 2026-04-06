"""
RAIN Intent Engine — Language → Structured Control Signals

This is the missing layer between user language and RainNet execution.
The Intent Engine translates natural language into deterministic, constrained
control signals that RainNet can execute.

Pipeline: Language → Intent Engine → Control Signals → RainNet → DSP → Validation

The Intent Engine is NOT a prompt wrapper. It is a structured decision system
that maps linguistic intent to bounded parameter deltas with confidence scores
and explicit restraint gates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Control Signal Schema — the output of the Intent Engine
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ControlSignal:
    """A single parameter adjustment with intent metadata."""
    parameter: str          # Canonical macro name: brighten, glue, width, punch, warmth, space, repair
    delta: float            # Signed change: +2.0 means "increase by 2"
    confidence: float       # 0.0-1.0: how confident we are this is what the user wants
    reason: str             # Human-readable: "User asked for more punch"
    source_phrase: str      # The exact words that triggered this signal


@dataclass
class IntentResult:
    """Complete output of the Intent Engine for one user utterance."""
    signals: list[ControlSignal] = field(default_factory=list)
    platform_target: Optional[str] = None       # "spotify", "apple_music", etc.
    style_reference: Optional[str] = None       # "like Drake", "radio-ready"
    restraint_flags: list[str] = field(default_factory=list)  # Reasons NOT to act
    explanation: str = ""                        # Plain-language summary for the user
    raw_intent: str = ""                         # Classified intent category


# ---------------------------------------------------------------------------
# Intent Classification — what is the user actually asking for?
# ---------------------------------------------------------------------------

INTENT_PATTERNS: list[tuple[str, list[str], str]] = [
    # (intent_name, keyword_patterns, description)
    ("louder",          ["loud", "louder", "volume", "pump", "bang", "slap", "hit hard", "smack"],
     "User wants increased perceived loudness"),
    ("warmer",          ["warm", "analog", "vinyl", "tape", "vintage", "rich", "thick", "fat"],
     "User wants harmonic warmth and analog character"),
    ("brighter",        ["bright", "crisp", "air", "sparkle", "shimmer", "presence", "clarity", "clear"],
     "User wants high-frequency presence and air"),
    ("wider",           ["wide", "stereo", "spatial", "immersive", "surround", "spread", "panoramic"],
     "User wants wider stereo image"),
    ("punchier",        ["punch", "punchy", "impact", "transient", "attack", "snap", "drum", "kick", "hit"],
     "User wants transient emphasis and impact"),
    ("cleaner",         ["clean", "noise", "hiss", "click", "pop", "repair", "fix", "remove", "denoise"],
     "User wants spectral repair and noise removal"),
    ("deeper",          ["deep", "space", "depth", "reverb", "room", "ambient", "atmospheric"],
     "User wants spatial depth and ambience"),
    ("tighter",         ["tight", "glue", "cohesive", "together", "unified", "gel", "bus", "compress"],
     "User wants bus compression and mix cohesion"),
    ("platform",        ["spotify", "apple", "youtube", "tidal", "soundcloud", "amazon", "tiktok", "radio",
                         "streaming", "playlist", "release", "distribute"],
     "User is targeting a specific platform or distribution"),
    ("reference",       ["like", "sound like", "similar to", "reference", "vibe of", "feel of", "style of"],
     "User is referencing an artist or track style"),
    ("reduce",          ["less", "reduce", "lower", "decrease", "pull back", "tone down", "soften", "subtle",
                         "gentle", "too much", "back off"],
     "User wants to reduce an existing quality"),
    ("vocal_focus",     ["vocal", "voice", "sing", "rapper", "mc", "lead", "lyrics", "words"],
     "User wants vocal clarity and presence"),
]


def classify_intent(text: str) -> list[tuple[str, float, str]]:
    """
    Classify user text into one or more intents with confidence scores.
    Returns list of (intent_name, confidence, matched_phrase).
    """
    text_lower = text.lower()
    matches: list[tuple[str, float, str]] = []

    for intent_name, keywords, _desc in INTENT_PATTERNS:
        for keyword in keywords:
            if keyword in text_lower:
                # Confidence based on keyword specificity
                confidence = min(0.95, 0.6 + len(keyword) * 0.03)
                matches.append((intent_name, confidence, keyword))
                break  # One match per intent category

    return matches


# ---------------------------------------------------------------------------
# Signal Generation — intent → parameter deltas
# ---------------------------------------------------------------------------

# Base delta magnitudes per intent (conservative defaults)
INTENT_TO_SIGNALS: dict[str, list[tuple[str, float]]] = {
    "louder":       [("punch", +2.0), ("glue", +1.5)],
    "warmer":       [("warmth", +2.5), ("brighten", -0.8)],
    "brighter":     [("brighten", +2.0)],
    "wider":        [("width", +2.0), ("space", +1.0)],
    "punchier":     [("punch", +2.5)],
    "cleaner":      [("repair", +3.0)],
    "deeper":       [("space", +2.0), ("warmth", +0.5)],
    "tighter":      [("glue", +2.5)],
    "vocal_focus":  [("brighten", +1.5), ("width", -0.5)],
}

# Platform LUFS targets (for platform intent)
PLATFORM_TARGETS: dict[str, str] = {
    "spotify": "spotify", "apple": "apple_music", "apple music": "apple_music",
    "youtube": "youtube", "tidal": "tidal", "soundcloud": "soundcloud",
    "amazon": "amazon_music", "tiktok": "tiktok", "radio": "broadcast",
    "streaming": "spotify", "playlist": "spotify",
}

# Intensity modifiers
INTENSITY_AMPLIFIERS = ["very", "much", "lot", "really", "super", "way more", "heavy", "extreme", "max"]
INTENSITY_DAMPENERS = ["slightly", "little", "bit", "touch", "subtle", "gentle", "hint"]


def _detect_intensity_modifier(text: str) -> float:
    """Returns a multiplier: >1 for amplifiers, <1 for dampeners."""
    text_lower = text.lower()
    for word in INTENSITY_AMPLIFIERS:
        if word in text_lower:
            return 1.5
    for word in INTENSITY_DAMPENERS:
        if word in text_lower:
            return 0.5
    return 1.0


def _detect_platform(text: str) -> Optional[str]:
    """Extract platform target from user text."""
    text_lower = text.lower()
    for keyword, platform_id in PLATFORM_TARGETS.items():
        if keyword in text_lower:
            return platform_id
    return None


def _detect_reference(text: str) -> Optional[str]:
    """Extract artist/style reference from user text."""
    # Pattern: "like [artist]", "sound like [artist]", "vibe of [artist]"
    patterns = [
        r"(?:sound\s+)?like\s+([A-Z][a-zA-Z\s]+?)(?:\.|,|$|\s+but|\s+with)",
        r"vibe\s+of\s+([A-Z][a-zA-Z\s]+?)(?:\.|,|$)",
        r"style\s+of\s+([A-Z][a-zA-Z\s]+?)(?:\.|,|$)",
        r"reference[:\s]+([A-Z][a-zA-Z\s]+?)(?:\.|,|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Restraint System — when NOT to act
# ---------------------------------------------------------------------------

@dataclass
class RestraintCheck:
    """A single restraint evaluation."""
    parameter: str
    current_value: float
    proposed_value: float
    blocked: bool
    reason: str


def evaluate_restraints(
    current_macros: dict[str, float],
    signals: list[ControlSignal],
) -> tuple[list[ControlSignal], list[str]]:
    """
    Apply restraint gates to proposed control signals.
    Returns (filtered_signals, restraint_reasons).

    Restraint philosophy: Don't over-process. If something is already good,
    leave it alone. The best mastering is the mastering you can't hear.
    """
    filtered: list[ControlSignal] = []
    reasons: list[str] = []

    for signal in signals:
        current = current_macros.get(signal.parameter, 5.0)
        proposed = max(0.0, min(10.0, current + signal.delta))

        # GATE 1: Already at extreme — don't push further
        if signal.delta > 0 and current >= 9.0:
            reasons.append(
                f"{signal.parameter.upper()} is already at {current:.1f} — "
                f"pushing further risks over-processing"
            )
            continue

        if signal.delta < 0 and current <= 1.0:
            reasons.append(
                f"{signal.parameter.upper()} is already at {current:.1f} — "
                f"can't reduce further without losing character"
            )
            continue

        # GATE 2: Conflicting signals — warmth vs brightness
        if signal.parameter == "warmth" and signal.delta > 0:
            brighten_current = current_macros.get("brighten", 5.0)
            if brighten_current > 7.0:
                # Reduce the warmth boost to prevent mud
                signal = ControlSignal(
                    parameter=signal.parameter,
                    delta=signal.delta * 0.6,
                    confidence=signal.confidence * 0.8,
                    reason=signal.reason + " (tempered — brightness is high)",
                    source_phrase=signal.source_phrase,
                )
                reasons.append(
                    "BRIGHTEN is already high — tempering WARMTH increase to avoid muddiness"
                )

        if signal.parameter == "brighten" and signal.delta > 0:
            warmth_current = current_macros.get("warmth", 2.5)
            if warmth_current > 7.0:
                signal = ControlSignal(
                    parameter=signal.parameter,
                    delta=signal.delta * 0.6,
                    confidence=signal.confidence * 0.8,
                    reason=signal.reason + " (tempered — warmth is high)",
                    source_phrase=signal.source_phrase,
                )
                reasons.append(
                    "WARMTH is already high — tempering BRIGHTEN increase to avoid harshness"
                )

        # GATE 3: Width + mono compatibility
        if signal.parameter == "width" and signal.delta > 0:
            if current >= 7.0:
                signal = ControlSignal(
                    parameter=signal.parameter,
                    delta=min(signal.delta, 1.0),
                    confidence=signal.confidence * 0.7,
                    reason=signal.reason + " (capped — mono compatibility risk)",
                    source_phrase=signal.source_phrase,
                )
                reasons.append(
                    "WIDTH is high — capping increase to preserve mono compatibility"
                )

        # GATE 4: Don't stack punch + glue too aggressively
        if signal.parameter in ("punch", "glue"):
            other = "glue" if signal.parameter == "punch" else "punch"
            other_val = current_macros.get(other, 5.0)
            if other_val > 7.0 and signal.delta > 0:
                signal = ControlSignal(
                    parameter=signal.parameter,
                    delta=signal.delta * 0.7,
                    confidence=signal.confidence * 0.8,
                    reason=signal.reason + f" (tempered — {other.upper()} already high)",
                    source_phrase=signal.source_phrase,
                )

        filtered.append(signal)

    return filtered, reasons


# ---------------------------------------------------------------------------
# Main Entry Point — the full Intent Engine pipeline
# ---------------------------------------------------------------------------

def process_intent(
    user_text: str,
    current_macros: dict[str, float],
    current_analysis: Optional[dict] = None,
) -> IntentResult:
    """
    Full Intent Engine pipeline:
    1. Classify intent from user text
    2. Generate control signals
    3. Apply restraint gates
    4. Build explanation

    Args:
        user_text: Raw user input ("make it warmer and punchier")
        current_macros: Current macro values {brighten: 5.0, glue: 6.0, ...}
        current_analysis: Optional analysis data (LUFS, true peak, etc.)

    Returns:
        IntentResult with filtered signals, restraints, and explanation.
    """
    result = IntentResult(raw_intent=user_text)

    # Step 1: Classify
    intents = classify_intent(user_text)
    if not intents:
        result.explanation = (
            "I'm not sure what you're looking for. Try describing the sound — "
            "like 'make it warmer', 'more punch', or 'ready for Spotify'."
        )
        return result

    # Step 2: Detect modifiers
    intensity = _detect_intensity_modifier(user_text)
    is_reduction = any(name == "reduce" for name, _, _ in intents)

    # Step 3: Detect platform and reference
    result.platform_target = _detect_platform(user_text)
    result.style_reference = _detect_reference(user_text)

    # Step 4: Generate signals
    signals: list[ControlSignal] = []

    for intent_name, confidence, matched_phrase in intents:
        if intent_name in ("platform", "reference", "reduce"):
            continue  # These modify other intents, not generate signals directly

        base_signals = INTENT_TO_SIGNALS.get(intent_name, [])
        for param, base_delta in base_signals:
            delta = base_delta * intensity
            if is_reduction:
                delta = -abs(delta) * 0.6  # Reductions are gentler

            signals.append(ControlSignal(
                parameter=param,
                delta=round(delta, 1),
                confidence=round(confidence, 2),
                reason=f"User intent: {intent_name}",
                source_phrase=matched_phrase,
            ))

    # Step 5: Analysis-aware adjustments
    if current_analysis:
        input_lufs = current_analysis.get("input_lufs")
        if input_lufs is not None and input_lufs > -10.0:
            # Already very loud — don't push louder
            signals = [s for s in signals if not (s.parameter == "punch" and s.delta > 0)]
            result.restraint_flags.append(
                f"Input is already loud ({input_lufs:.1f} LUFS) — skipping loudness boost"
            )

    # Step 6: Apply restraint system
    signals, restraint_reasons = evaluate_restraints(current_macros, signals)
    result.restraint_flags.extend(restraint_reasons)
    result.signals = signals

    # Step 7: Build explanation
    result.explanation = _build_explanation(signals, result.restraint_flags, result.platform_target)

    logger.info(
        "intent_processed",
        intents=[i[0] for i in intents],
        signals_count=len(signals),
        restraints_count=len(result.restraint_flags),
        platform=result.platform_target,
        reference=result.style_reference,
    )

    return result


def _build_explanation(
    signals: list[ControlSignal],
    restraints: list[str],
    platform: Optional[str],
) -> str:
    """Build a plain-language explanation of what changes are being suggested."""
    parts: list[str] = []

    if not signals and not restraints:
        return "No changes needed — your current settings sound good for this."

    if signals:
        changes = []
        for s in signals:
            direction = "increased" if s.delta > 0 else "decreased"
            changes.append(f"**{s.parameter.upper()}** {direction} by {abs(s.delta):.1f}")
        parts.append("Here's what I'd adjust: " + ", ".join(changes) + ".")

    if platform:
        parts.append(f"Optimized for **{platform.replace('_', ' ').title()}** streaming requirements.")

    if restraints:
        parts.append("")
        parts.append("I held back on a few things:")
        for r in restraints:
            parts.append(f"- {r}")

    parts.append("")
    parts.append("Hit **Apply** to hear the difference, or tell me to adjust further.")

    return "\n".join(parts)
