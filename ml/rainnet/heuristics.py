"""
Heuristic fallback processing parameters.
Used when RAIN_NORMALIZATION_VALIDATED=false (always currently) or inference fails.
This is AUTHORITATIVE -- the frontend (PART-5 heuristic-params.ts) must match these values exactly.
All field names follow the canonical ProcessingParams schema from CLAUDE.md.
"""
from typing import Optional

GENRE_PRESETS: dict[str, dict] = {
    "electronic": {
        "mb_threshold_low": -18.0, "mb_threshold_mid": -16.0, "mb_threshold_high": -14.0,
        "mb_ratio_low": 3.0, "mb_ratio_mid": 2.5, "mb_ratio_high": 2.0,
        "stereo_width": 1.3, "analog_saturation": False,
        "macro_brighten": 5.0, "macro_glue": 6.0, "macro_width": 7.0,
        "macro_punch": 5.0, "macro_warmth": 3.0, "macro_space": 6.0, "macro_repair": 0.0,
    },
    "hiphop": {
        "mb_threshold_low": -16.0, "mb_threshold_mid": -14.0, "mb_threshold_high": -14.0,
        "mb_ratio_low": 3.5, "mb_ratio_mid": 2.5, "mb_ratio_high": 2.0,
        "stereo_width": 1.1, "analog_saturation": True, "saturation_drive": 0.2,
        "macro_brighten": 4.0, "macro_glue": 7.0, "macro_width": 4.0,
        "macro_punch": 8.0, "macro_warmth": 5.0, "macro_space": 3.0, "macro_repair": 0.0,
    },
    "rock": {
        "mb_threshold_low": -18.0, "mb_threshold_mid": -16.0, "mb_threshold_high": -12.0,
        "mb_ratio_low": 2.5, "mb_ratio_mid": 2.0, "mb_ratio_high": 2.5,
        "analog_saturation": True, "saturation_drive": 0.15,
        "macro_brighten": 5.0, "macro_glue": 5.0, "macro_width": 5.0,
        "macro_punch": 7.0, "macro_warmth": 6.0, "macro_space": 4.0, "macro_repair": 0.0,
    },
    "pop": {
        "mb_threshold_low": -20.0, "mb_threshold_mid": -18.0, "mb_threshold_high": -16.0,
        "mb_ratio_low": 2.0, "mb_ratio_mid": 2.0, "mb_ratio_high": 1.8,
        "stereo_width": 1.1,
        "macro_brighten": 6.0, "macro_glue": 5.0, "macro_width": 5.0,
        "macro_punch": 5.0, "macro_warmth": 4.0, "macro_space": 5.0, "macro_repair": 0.0,
    },
    "classical": {
        "mb_threshold_low": -24.0, "mb_threshold_mid": -22.0, "mb_threshold_high": -22.0,
        "mb_ratio_low": 1.5, "mb_ratio_mid": 1.5, "mb_ratio_high": 1.5,
        "stereo_width": 0.95,
        "macro_brighten": 3.0, "macro_glue": 2.0, "macro_width": 4.0,
        "macro_punch": 2.0, "macro_warmth": 3.0, "macro_space": 7.0, "macro_repair": 0.0,
    },
    "jazz": {
        "mb_threshold_low": -22.0, "mb_threshold_mid": -20.0, "mb_threshold_high": -20.0,
        "mb_ratio_low": 2.0, "mb_ratio_mid": 1.8, "mb_ratio_high": 1.5,
        "analog_saturation": True, "saturation_drive": 0.1,
        "macro_brighten": 3.0, "macro_glue": 4.0, "macro_width": 4.0,
        "macro_punch": 3.0, "macro_warmth": 6.0, "macro_space": 6.0, "macro_repair": 0.0,
    },
    "default": {
        "mb_threshold_low": -20.0, "mb_threshold_mid": -18.0, "mb_threshold_high": -16.0,
        "mb_ratio_low": 2.5, "mb_ratio_mid": 2.0, "mb_ratio_high": 2.0,
        "macro_brighten": 5.0, "macro_glue": 5.0, "macro_width": 5.0,
        "macro_punch": 5.0, "macro_warmth": 5.0, "macro_space": 5.0, "macro_repair": 0.0,
    },
}

PLATFORM_LUFS: dict[str, float] = {
    "spotify": -14.0,
    "apple_music": -16.0,
    "youtube": -14.0,
    "tidal": -14.0,
    "amazon_music": -14.0,
    "tiktok": -14.0,
    "soundcloud": -14.0,
    "vinyl": -14.0,
}

BASE_PARAMS: dict = {
    # Loudness target (overridden by platform)
    "target_lufs": -14.0,
    "true_peak_ceiling": -1.0,
    # Multiband dynamics
    "mb_threshold_low": -20.0, "mb_threshold_mid": -18.0, "mb_threshold_high": -16.0,
    "mb_ratio_low": 2.5, "mb_ratio_mid": 2.0, "mb_ratio_high": 2.0,
    "mb_attack_low": 10.0, "mb_attack_mid": 5.0, "mb_attack_high": 2.0,
    "mb_release_low": 150.0, "mb_release_mid": 80.0, "mb_release_high": 40.0,
    # EQ
    "eq_gains": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    # Analog saturation
    "analog_saturation": False, "saturation_drive": 0.0, "saturation_mode": "tape",
    # Mid/Side
    "ms_enabled": False, "mid_gain": 0.0, "side_gain": 0.0, "stereo_width": 1.0,
    # SAIL
    "sail_enabled": False, "sail_stem_gains": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    # Vinyl
    "vinyl_mode": False,
    # Macro controls
    "macro_brighten": 5.0, "macro_glue": 5.0, "macro_width": 5.0,
    "macro_punch": 5.0, "macro_warmth": 5.0, "macro_space": 5.0, "macro_repair": 0.0,
}

# Total scalar dimensions: 2 + 12 + 8 + 3 + 4 + 7 + 1 + 7 = 44 named fields
# (eq_gains expands to 8, sail_stem_gains expands to 6 => 46 scalar values)


def get_heuristic_params(
    genre: Optional[str],
    platform: str,
    vinyl: bool = False,
) -> dict:
    """
    Returns a complete ProcessingParams dict with all 46 parameter dimensions.
    Output is deterministic for the same (genre, platform) pair.
    Always returns all fields -- no optional keys.
    """
    # Deep-copy lists to avoid mutation of BASE_PARAMS
    params = {k: (v.copy() if isinstance(v, list) else v) for k, v in BASE_PARAMS.items()}
    preset = GENRE_PRESETS.get(genre or "default", GENRE_PRESETS["default"])
    params.update(preset)
    params["target_lufs"] = PLATFORM_LUFS.get(platform, -14.0)
    params["true_peak_ceiling"] = -3.0 if vinyl else -1.0
    params["vinyl_mode"] = vinyl
    return params
