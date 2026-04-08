"""
RAIN Heuristic Fallback — Canonical ProcessingParams per CLAUDE.md

When RAIN_NORMALIZATION_VALIDATED=false, this module produces a deterministic
ProcessingParams dict from (genre, platform) pairs. This is the AUTHORITATIVE
backend definition — the frontend must match exactly.

Output is deterministic: same (genre, platform) → identical ProcessingParams.
"""

from __future__ import annotations

from typing import Any

from app.services.platform_targets import get_platform_target


# Canonical ProcessingParams schema — 46 ONNX neurons decode to these fields.
# sail_stem_gains is [12] (6 decoded + 6 zero-padded), saturation_mode is argmax of 3 logits.
def default_params() -> dict[str, Any]:
    """Return the canonical ProcessingParams with all defaults per CLAUDE.md."""
    return {
        # Loudness target
        "target_lufs": -14.0,
        "true_peak_ceiling": -1.0,

        # Multiband dynamics (3-band: low/mid/high)
        "mb_threshold_low": -18.0,
        "mb_threshold_mid": -15.0,
        "mb_threshold_high": -12.0,
        "mb_ratio_low": 2.5,
        "mb_ratio_mid": 2.0,
        "mb_ratio_high": 2.0,
        "mb_attack_low": 10.0,
        "mb_attack_mid": 5.0,
        "mb_attack_high": 2.0,
        "mb_release_low": 150.0,
        "mb_release_mid": 80.0,
        "mb_release_high": 40.0,

        # EQ (8-band parametric)
        "eq_gains": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],

        # Analog saturation
        "analog_saturation": False,
        "saturation_drive": 0.0,
        "saturation_mode": "tape",

        # Mid/Side processing
        "ms_enabled": False,
        "mid_gain": 0.0,
        "side_gain": 0.0,
        "stereo_width": 1.0,

        # SAIL (Stem-Aware Intelligent Limiting)
        "sail_enabled": False,
        "sail_stem_gains": [0.0] * 12,  # float[12] — 12-stem SAIL v2

        # Vinyl mode
        "vinyl_mode": False,

        # 7 Macro controls (RainNet v2 indices 39-45, sigmoid×10 → [0.0, 10.0])
        "macro_brighten": 5.0,
        "macro_glue": 5.0,
        "macro_width": 5.0,
        "macro_punch": 5.0,
        "macro_warmth": 5.0,
        "macro_space": 5.0,
        "macro_repair": 0.0,
    }


# Genre-specific overrides
GENRE_OVERRIDES: dict[str, dict[str, Any]] = {
    "electronic": {
        "mb_ratio_low": 3.5,
        "mb_ratio_mid": 2.5,
        "mb_ratio_high": 2.5,
        "mb_attack_low": 5.0,
        "mb_attack_mid": 3.0,
        "mb_release_low": 120.0,
        "eq_gains": [0.0, 1.0, 0.0, -0.5, 0.0, 1.0, 1.5, 2.0],
        "ms_enabled": True,
        "side_gain": 1.5,
        "stereo_width": 1.3,
        "analog_saturation": True,
        "saturation_drive": 0.2,
    },
    "hiphop": {
        "mb_ratio_low": 4.0,
        "mb_ratio_mid": 2.5,
        "mb_threshold_low": -15.0,
        "mb_attack_low": 3.0,
        "mb_release_low": 100.0,
        "eq_gains": [1.5, 1.0, 0.0, 0.0, -0.5, 0.5, 1.0, 1.5],
        "ms_enabled": True,
        "side_gain": 1.0,
        "stereo_width": 1.2,
    },
    "rock": {
        "mb_ratio_low": 3.0,
        "mb_ratio_mid": 2.5,
        "mb_ratio_high": 2.5,
        "mb_attack_mid": 4.0,
        "eq_gains": [0.5, 0.0, 0.5, 1.0, 0.0, 0.5, 1.0, 1.5],
        "ms_enabled": True,
        "side_gain": 2.0,
        "stereo_width": 1.2,
        "analog_saturation": True,
        "saturation_drive": 0.3,
        "saturation_mode": "tube",
    },
    "pop": {
        "mb_ratio_low": 2.5,
        "mb_ratio_mid": 2.0,
        "mb_ratio_high": 2.0,
        "eq_gains": [0.0, 0.0, 0.5, 0.5, 0.5, 1.0, 1.5, 2.0],
        "ms_enabled": True,
        "side_gain": 1.5,
        "stereo_width": 1.2,
    },
    "classical": {
        "mb_ratio_low": 1.5,
        "mb_ratio_mid": 1.3,
        "mb_ratio_high": 1.3,
        "mb_threshold_low": -24.0,
        "mb_threshold_mid": -22.0,
        "mb_threshold_high": -20.0,
        "mb_attack_low": 20.0,
        "mb_attack_mid": 15.0,
        "mb_attack_high": 10.0,
        "mb_release_low": 300.0,
        "mb_release_mid": 200.0,
        "mb_release_high": 150.0,
        "eq_gains": [0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.5, 1.0],
        "stereo_width": 1.1,
    },
    "jazz": {
        "mb_ratio_low": 2.0,
        "mb_ratio_mid": 1.5,
        "mb_ratio_high": 1.5,
        "mb_threshold_low": -22.0,
        "mb_threshold_mid": -20.0,
        "mb_threshold_high": -18.0,
        "mb_attack_low": 15.0,
        "mb_attack_mid": 10.0,
        "mb_release_low": 250.0,
        "eq_gains": [0.0, 0.5, 0.0, 0.0, 0.0, 0.5, 1.0, 1.0],
        "analog_saturation": True,
        "saturation_drive": 0.15,
        "saturation_mode": "tube",
        "stereo_width": 1.1,
    },
    "default": {},  # Uses base defaults
}


def generate_heuristic_params(genre: str, platform: str) -> dict[str, Any]:
    """Generate a deterministic ProcessingParams dict from (genre, platform).

    This is the MANDATORY fallback when RAIN_NORMALIZATION_VALIDATED=false.
    Output is deterministic: same inputs always produce identical output.
    """
    params = default_params()

    # Apply platform target
    target = get_platform_target(platform)
    params["target_lufs"] = target.target_lufs
    params["true_peak_ceiling"] = target.true_peak_ceiling

    # Vinyl mode
    if platform == "vinyl":
        params["vinyl_mode"] = True
        params["true_peak_ceiling"] = -3.0

    # Apply genre overrides
    overrides = GENRE_OVERRIDES.get(genre, GENRE_OVERRIDES["default"])
    for key, value in overrides.items():
        params[key] = value

    return params


def validate_processing_params(params: dict[str, Any]) -> list[str]:
    """Validate a ProcessingParams dict against the canonical schema.

    Returns a list of error strings. Empty list = valid.
    """
    errors: list[str] = []
    canonical = default_params()

    # Check all required fields present
    for key in canonical:
        if key not in params:
            errors.append(f"Missing field: {key}")

    # Check no extra fields
    for key in params:
        if key not in canonical:
            errors.append(f"Unexpected field: {key}")

    # Range checks
    if "target_lufs" in params:
        v = params["target_lufs"]
        if not (-24.0 <= v <= -8.0):
            errors.append(f"target_lufs {v} out of range [-24.0, -8.0]")

    if "true_peak_ceiling" in params:
        v = params["true_peak_ceiling"]
        if not (-6.0 <= v <= 0.0):
            errors.append(f"true_peak_ceiling {v} out of range [-6.0, 0.0]")

    if "eq_gains" in params:
        eq = params["eq_gains"]
        if not isinstance(eq, list) or len(eq) != 8:
            errors.append(f"eq_gains must be float[8], got length {len(eq) if isinstance(eq, list) else type(eq)}")
        elif any(not (-12.0 <= g <= 12.0) for g in eq):
            errors.append("eq_gains values must be in range [-12.0, +12.0]")

    if "sail_stem_gains" in params:
        sg = params["sail_stem_gains"]
        if not isinstance(sg, list) or len(sg) != 12:
            errors.append(f"sail_stem_gains must be float[12], got length {len(sg) if isinstance(sg, list) else type(sg)}")

    # Validate 7 macros if present (all must be in [0.0, 10.0])
    for macro_name in ("macro_brighten", "macro_glue", "macro_width", "macro_punch",
                        "macro_warmth", "macro_space", "macro_repair"):
        if macro_name in params:
            v = params[macro_name]
            if not (0.0 <= v <= 10.0):
                errors.append(f"{macro_name} {v} out of range [0.0, 10.0]")

    for prefix in ("mb_ratio_", ):
        for band in ("low", "mid", "high"):
            key = f"{prefix}{band}"
            if key in params and not (1.0 <= params[key] <= 20.0):
                errors.append(f"{key} {params[key]} out of range [1.0, 20.0]")

    if "stereo_width" in params:
        v = params["stereo_width"]
        if not (0.0 <= v <= 2.0):
            errors.append(f"stereo_width {v} out of range [0.0, 2.0]")

    return errors
