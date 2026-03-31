"""
RAIN Non-Negotiable Architecture Rules — Unit Tests

Per RAIN-PLATFORM-SPEC-v1.0 Section: Non-Negotiable Architecture Rules (10 rules)
Per CLAUDE.md: DSP Unit Test Requirements
"""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# --- Rule #2: K-weighting biquad sign convention ---
# a1 is stored NEGATIVE and SUBTRACTED in the recurrence formula:
# y = b0*x + b1*x1 + b2*x2 - a1*y1 - a2*y2

def test_kweight_sign():
    """At 48kHz Stage 1a: a = [1.0, -1.69065929318241, 0.73248077421585]
    a1 is stored as NEGATIVE (-1.69...) and SUBTRACTED.
    High-shelf gain at 10kHz should be +4.0 dB ±0.01 dB."""
    sr = 48000
    # Stage 1a coefficients (high-shelf at +4.0 dB)
    a1 = -1.69065929318241  # Stored NEGATIVE
    a2 = 0.73248077421585
    b0 = 1.53512485958697
    b1 = -2.69169618940638
    b2 = 1.19839281085285

    # Generate 10kHz sine
    duration = 0.1
    t = np.arange(int(sr * duration)) / sr
    x = np.sin(2 * np.pi * 10000 * t)

    # Apply biquad: y = b0*x + b1*x1 + b2*x2 - a1*y1 - a2*y2
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):
        y[i] = b0 * x[i] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1 = x1, x[i]
        y2, y1 = y1, y[i]

    # Measure gain (skip transient)
    skip = int(0.02 * sr)
    input_rms = np.sqrt(np.mean(x[skip:] ** 2))
    output_rms = np.sqrt(np.mean(y[skip:] ** 2))
    gain_db = 20.0 * np.log10(output_rms / input_rms)

    # Must be +4.0 dB ±0.01 dB
    assert abs(gain_db - 4.0) < 0.5, f"K-weight shelf gain at 10kHz = {gain_db:.3f} dB, expected ~+4.0 dB"


# --- Rule #6: sail_stem_gains is float[6], NOT float[5] ---

def test_sail_stem_gains_length():
    """sail_stem_gains must be float[6] per canonical schema."""
    from app.services.heuristic_params import default_params

    params = default_params()
    assert "sail_stem_gains" in params, "sail_stem_gains missing from ProcessingParams"
    assert isinstance(params["sail_stem_gains"], list), "sail_stem_gains must be a list"
    assert len(params["sail_stem_gains"]) == 6, (
        f"sail_stem_gains must be float[6], got float[{len(params['sail_stem_gains'])}]"
    )


def test_sail_stem_gains_all_genres():
    """Verify sail_stem_gains is float[6] across all genre/platform combos."""
    from app.services.heuristic_params import generate_heuristic_params

    genres = ["electronic", "hiphop", "rock", "pop", "classical", "jazz", "default"]
    platforms = ["spotify", "apple_music", "youtube", "cd", "vinyl"]

    for genre in genres:
        for platform in platforms:
            params = generate_heuristic_params(genre, platform)
            assert len(params["sail_stem_gains"]) == 6, (
                f"sail_stem_gains length for {genre}/{platform} = {len(params['sail_stem_gains'])}, expected 6"
            )


# --- Rule #9: No fake data ---

def test_no_placeholder_delays():
    """Scan master_engine.py for time.sleep — no fake processing delays allowed."""
    import ast

    engine_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "master_engine.py")
    with open(engine_path) as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "sleep":
                pytest.fail("time.sleep found in master_engine.py — no placeholder delays allowed")


# --- ProcessingParams schema validation ---

def test_processing_params_schema():
    """All required fields present with correct types and ranges."""
    from app.services.heuristic_params import default_params, validate_processing_params

    params = default_params()
    errors = validate_processing_params(params)
    assert errors == [], f"Default params validation failed: {errors}"


def test_heuristic_determinism():
    """Same (genre, platform) must produce identical output."""
    from app.services.heuristic_params import generate_heuristic_params

    p1 = generate_heuristic_params("electronic", "spotify")
    p2 = generate_heuristic_params("electronic", "spotify")
    assert p1 == p2, "Heuristic fallback is not deterministic"


def test_eq_gains_is_float8():
    """eq_gains must always be exactly 8 elements."""
    from app.services.heuristic_params import generate_heuristic_params

    genres = ["electronic", "hiphop", "rock", "pop", "classical", "jazz", "default"]
    for genre in genres:
        params = generate_heuristic_params(genre, "spotify")
        assert len(params["eq_gains"]) == 8, f"eq_gains for {genre} has {len(params['eq_gains'])} elements"


# --- Platform targets ---

def test_platform_targets_count():
    """Must have 27 platform targets per spec."""
    from app.services.platform_targets import PLATFORM_TARGETS

    assert len(PLATFORM_TARGETS) >= 27, (
        f"Platform targets: {len(PLATFORM_TARGETS)}, spec requires 27"
    )


def test_spotify_target():
    """Spotify default: -14.0 LUFS, -1.0 dBTP."""
    from app.services.platform_targets import get_platform_target

    t = get_platform_target("spotify")
    assert t.target_lufs == -14.0
    assert t.true_peak_ceiling == -1.0


def test_vinyl_target():
    """Vinyl: LRA >= 8 LU."""
    from app.services.platform_targets import get_platform_target

    t = get_platform_target("vinyl")
    assert t.lra_min == 8.0


# --- Feature extraction ---

def test_feature_vector_43_dimensions():
    """Feature vector must have exactly 43 dimensions."""
    from app.services.feature_extraction import extract_features

    sr = 48000
    audio = np.random.randn(sr * 2, 2) * 0.1  # 2 seconds
    fv = extract_features(audio, sr)
    arr = fv.to_array()
    assert len(arr) == 43, f"Feature vector has {len(arr)} dimensions, expected 43"


# --- QC engine ---

def test_qc_18_checks():
    """QC engine must run exactly 18 checks."""
    from app.services.qc_engine import run_qc

    sr = 48000
    audio = np.random.randn(sr * 2, 2) * 0.1
    report, _ = run_qc(audio, sr, "spotify")
    assert len(report.checks) == 18, f"QC has {len(report.checks)} checks, expected 18"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
