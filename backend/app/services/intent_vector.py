"""
RAIN Intent Vector System — Continuous Perceptual Space

Evolution from discrete intent categories to a continuous latent intent vector.
Categories are kept for interpretability but conflicts are resolved in
continuous vector space, not by rule stacking.

"Make it warmer but still crisp and a bit wider" is NOT 3 separate intents.
It's a single point in a 7-dimensional perceptual space:
  [warmth: +0.6, brightness: +0.2, width: +0.4, punch: 0, glue: 0, space: 0, repair: 0]

The Intent Vector System:
1. Parses keywords → discrete intent hits (existing classifier)
2. Converts discrete hits → continuous intent vector (weighted blend)
3. Applies perceptual constraints in vector space (not rule stacking)
4. Predicts side effects before applying ("If I do this, what breaks?")
5. Produces final bounded deltas with chain reasoning
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# The 7 perceptual dimensions (maps 1:1 to MacroValues)
# ---------------------------------------------------------------------------

DIMENSIONS = ["brighten", "glue", "width", "punch", "warmth", "space", "repair"]
DIM_INDEX = {name: i for i, name in enumerate(DIMENSIONS)}
N_DIMS = len(DIMENSIONS)


@dataclass
class IntentVector:
    """A point in the 7-dimensional perceptual space.
    Values are signed deltas in [-1.0, +1.0] representing the
    desired direction and magnitude of change.
    """
    values: np.ndarray = field(default_factory=lambda: np.zeros(N_DIMS, dtype=np.float64))
    confidence: float = 0.0
    source_intents: list[str] = field(default_factory=list)

    def __getitem__(self, key: str) -> float:
        return float(self.values[DIM_INDEX[key]])

    def __setitem__(self, key: str, val: float) -> None:
        self.values[DIM_INDEX[key]] = val

    @property
    def magnitude(self) -> float:
        return float(np.linalg.norm(self.values))

    def to_dict(self) -> dict[str, float]:
        return {name: float(self.values[i]) for i, name in enumerate(DIMENSIONS)}


# ---------------------------------------------------------------------------
# Perceptual Basis Vectors — each intent maps to a direction in the space
# ---------------------------------------------------------------------------
# These encode domain knowledge: "louder" isn't just punch, it's a blend
# of punch + glue with slight brightness reduction.

INTENT_BASIS: dict[str, np.ndarray] = {
    #                       brighten  glue   width  punch  warmth space  repair
    "louder":     np.array([-0.1,     0.4,   0.0,   0.6,   0.0,   0.0,   0.0]),
    "warmer":     np.array([-0.2,     0.0,   0.0,   0.0,   0.7,   0.1,   0.0]),
    "brighter":   np.array([ 0.8,     0.0,   0.0,   0.0,  -0.1,   0.0,   0.0]),
    "wider":      np.array([ 0.0,     0.0,   0.7,   0.0,   0.0,   0.3,   0.0]),
    "punchier":   np.array([ 0.0,     0.1,   0.0,   0.8,   0.0,   0.0,   0.0]),
    "cleaner":    np.array([ 0.1,     0.0,   0.0,   0.0,   0.0,   0.0,   0.9]),
    "deeper":     np.array([ 0.0,     0.0,   0.1,   0.0,   0.2,   0.7,   0.0]),
    "tighter":    np.array([ 0.0,     0.8,   0.0,   0.1,   0.0,   0.0,   0.0]),
    "vocal_focus":np.array([ 0.4,     0.0,  -0.2,   0.0,   0.0,   0.0,   0.1]),
}

# Normalize all basis vectors to unit length
for key in INTENT_BASIS:
    norm = np.linalg.norm(INTENT_BASIS[key])
    if norm > 1e-10:
        INTENT_BASIS[key] = INTENT_BASIS[key] / norm


# ---------------------------------------------------------------------------
# Perceptual Interaction Matrix — how dimensions affect each other
# ---------------------------------------------------------------------------
# Positive = reinforcing, Negative = conflicting
# This encodes: "warmth fights brightness", "punch stacks with glue", etc.

INTERACTION_MATRIX = np.array([
    #  brt   glu   wid   pun   wrm   spc   rep
    [ 1.0,  0.0,  0.0,  0.0, -0.4,  0.0,  0.1],  # brighten
    [ 0.0,  1.0,  0.0,  0.3,  0.0,  0.0,  0.0],  # glue
    [ 0.0,  0.0,  1.0,  0.0,  0.0,  0.3, -0.1],  # width
    [ 0.0,  0.3,  0.0,  1.0,  0.0, -0.2,  0.0],  # punch
    [-0.4,  0.0,  0.0,  0.0,  1.0,  0.1,  0.0],  # warmth
    [ 0.0,  0.0,  0.3, -0.2,  0.1,  1.0,  0.0],  # space
    [ 0.1,  0.0, -0.1,  0.0,  0.0,  0.0,  1.0],  # repair
], dtype=np.float64)


# ---------------------------------------------------------------------------
# Side Effect Predictor — "if I do this, what will change?"
# ---------------------------------------------------------------------------

@dataclass
class SideEffect:
    """A predicted side effect of applying a change."""
    dimension: str
    impact: float        # Positive = improvement, negative = degradation
    description: str
    confidence: float    # How confident we are in this prediction


def predict_side_effects(
    intent_vec: IntentVector,
    current_macros: dict[str, float],
) -> list[SideEffect]:
    """
    Predict what will change (positively or negatively) if we apply this intent.
    Uses the interaction matrix to estimate cross-dimensional effects.

    This is the "If I do this, what breaks?" layer.
    """
    effects: list[SideEffect] = []
    deltas = intent_vec.values

    # Compute interaction effects
    interaction_effects = INTERACTION_MATRIX @ deltas

    for i, dim in enumerate(DIMENSIONS):
        direct_delta = deltas[i]
        interaction_delta = interaction_effects[i] - direct_delta  # Subtract self-interaction
        proposed = current_macros.get(dim, 5.0) + direct_delta * 5.0  # Scale to 0-10

        # Only report significant side effects
        if abs(interaction_delta) > 0.1:
            effect_desc = _describe_side_effect(dim, interaction_delta, proposed, current_macros.get(dim, 5.0))
            if effect_desc:
                effects.append(SideEffect(
                    dimension=dim,
                    impact=round(interaction_delta, 2),
                    description=effect_desc,
                    confidence=min(0.9, abs(interaction_delta)),
                ))

    # Sort by absolute impact (most significant first)
    effects.sort(key=lambda e: abs(e.impact), reverse=True)
    return effects[:4]  # Top 4 most significant


def _describe_side_effect(dim: str, interaction: float, proposed: float, current: float) -> Optional[str]:
    """Generate a human-readable description of a side effect."""
    labels = {
        "brighten": ("brightness", "crisp", "dull"),
        "glue": ("cohesion", "glued-together", "loose"),
        "width": ("stereo width", "wide", "narrow"),
        "punch": ("punch", "impactful", "soft"),
        "warmth": ("warmth", "warm", "cold"),
        "space": ("spatial depth", "spacious", "dry"),
        "repair": ("cleanliness", "clean", "noisy"),
    }

    label, pos_adj, neg_adj = labels.get(dim, (dim, "more", "less"))

    if interaction > 0.15:
        return f"{label.title()} may increase slightly ({pos_adj}er feel)"
    elif interaction < -0.15:
        if proposed > 8.0:
            return f"Risk: {label} pushed high — may sound over-processed"
        elif proposed < 2.0:
            return f"Warning: {label} may drop too low ({neg_adj} sound)"
        else:
            return f"{label.title()} may decrease slightly ({neg_adj}er feel)"
    return None


# ---------------------------------------------------------------------------
# Vector-Space Intent Resolution
# ---------------------------------------------------------------------------

def resolve_intent(
    text: str,
    current_macros: dict[str, float],
    intensity_modifier: float = 1.0,
) -> tuple[IntentVector, list[SideEffect], list[str]]:
    """
    Full intent resolution in continuous vector space.

    1. Parse text → discrete intent hits
    2. Blend discrete hits → continuous intent vector using basis vectors
    3. Apply perceptual constraints (interaction matrix)
    4. Predict side effects
    5. Apply boundary constraints

    Returns: (intent_vector, side_effects, chain_reasoning)
    """
    from app.services.intent_engine import classify_intent, _detect_intensity_modifier

    # Step 1: Classify
    intents = classify_intent(text)
    intensity = _detect_intensity_modifier(text)
    combined_intensity = intensity * intensity_modifier

    if not intents:
        return IntentVector(), [], ["No clear intent detected from input."]

    # Step 2: Blend into continuous vector
    intent_vec = IntentVector()
    total_confidence = 0.0

    for intent_name, confidence, matched_phrase in intents:
        if intent_name in ("platform", "reference", "reduce"):
            continue

        basis = INTENT_BASIS.get(intent_name)
        if basis is None:
            continue

        # Check if user wants reduction
        is_reduction = any(word in text.lower() for word in ["less", "reduce", "lower", "back off", "too much"])

        weight = confidence * combined_intensity
        if is_reduction:
            weight = -abs(weight) * 0.6

        intent_vec.values += basis * weight
        intent_vec.source_intents.append(intent_name)
        total_confidence += confidence

    if total_confidence > 0:
        intent_vec.confidence = min(0.95, total_confidence / len(intents))

    # Step 3: Apply interaction constraints
    # The interaction matrix can amplify or dampen cross-dimensional effects
    constrained = INTERACTION_MATRIX @ intent_vec.values
    # Blend: 70% direct intent, 30% interaction-aware
    intent_vec.values = 0.7 * intent_vec.values + 0.3 * constrained

    # Step 4: Boundary constraints
    chain_reasoning: list[str] = []

    for i, dim in enumerate(DIMENSIONS):
        current = current_macros.get(dim, 5.0)
        proposed_delta = intent_vec.values[i] * 5.0  # Scale from [-1,1] to [-5,5]
        proposed_val = current + proposed_delta

        # Clamp to [0, 10]
        if proposed_val > 10.0:
            intent_vec.values[i] = (10.0 - current) / 5.0
            chain_reasoning.append(f"Capped {dim.upper()} at 10.0 (was heading to {proposed_val:.1f})")
        elif proposed_val < 0.0:
            intent_vec.values[i] = -current / 5.0
            chain_reasoning.append(f"Floored {dim.upper()} at 0.0 (was heading to {proposed_val:.1f})")

        # Soft restraint at extremes
        if current >= 8.5 and intent_vec.values[i] > 0:
            intent_vec.values[i] *= 0.3
            chain_reasoning.append(
                f"Tempered {dim.upper()} boost — already at {current:.1f}, "
                f"small adjustment to avoid over-processing"
            )

    # Step 5: Predict side effects
    side_effects = predict_side_effects(intent_vec, current_macros)

    # Add side effect chain reasoning
    for effect in side_effects:
        if abs(effect.impact) > 0.2:
            chain_reasoning.append(effect.description)

    return intent_vec, side_effects, chain_reasoning


def intent_vector_to_deltas(
    vec: IntentVector,
    scale: float = 5.0,
) -> dict[str, float]:
    """Convert an IntentVector to concrete macro deltas (in 0-10 space).

    A value of 0.4 in the vector → +2.0 delta on the macro.
    """
    deltas: dict[str, float] = {}
    for i, dim in enumerate(DIMENSIONS):
        delta = vec.values[i] * scale
        if abs(delta) > 0.05:  # Skip negligible changes
            deltas[dim] = round(delta, 1)
    return deltas


def intent_vector_to_absolute(
    vec: IntentVector,
    current_macros: dict[str, float],
    scale: float = 5.0,
) -> dict[str, float]:
    """Convert an IntentVector to absolute macro values (clamped to 0-10)."""
    result: dict[str, float] = {}
    for i, dim in enumerate(DIMENSIONS):
        delta = vec.values[i] * scale
        if abs(delta) > 0.05:
            new_val = current_macros.get(dim, 5.0) + delta
            result[dim] = round(max(0.0, min(10.0, new_val)), 1)
    return result
