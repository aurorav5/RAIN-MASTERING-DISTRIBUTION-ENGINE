"""Tests for the multi-platform loudness penalty predictor."""
from __future__ import annotations

import numpy as np
import pytest

from backend.app.services.loudness_penalty import (
    PLATFORM_RULES,
    LoudnessPenaltyPredictor,
)


def _sine(freq: float, amp_dbfs: float, sample_rate: int, duration_s: float) -> np.ndarray:
    n = int(sample_rate * duration_s)
    amp = 10.0 ** (amp_dbfs / 20.0)
    t = np.arange(n, dtype=np.float64) / sample_rate
    return amp * np.sin(2.0 * np.pi * freq * t)


@pytest.mark.slow
def test_measure_lufs_sine_minus_20_dbfs_is_minus_23_lufs() -> None:
    """A 1 kHz sine at -20 dBFS has integrated loudness ~ -23 LUFS (K-weighted)."""
    sr = 48000
    samples = _sine(1000.0, -20.0, sr, duration_s=5.0)
    predictor = LoudnessPenaltyPredictor()
    lufs = predictor.measure_lufs(samples, sr)
    assert abs(lufs - (-23.0)) < 0.5, f"expected ~-23 LUFS, got {lufs}"


def test_predict_penalty_spotify_normal_loud_master() -> None:
    predictor = LoudnessPenaltyPredictor()
    result = predictor.predict_penalty(-10.0, "spotify_normal")
    assert result["penalty_db"] == pytest.approx(-4.0)
    assert result["target_lufs"] == -14.0
    assert result["applies_limiter"] is False
    assert result["direction"] == "bidirectional"
    assert result["platform"] == "spotify_normal"


def test_predict_penalty_youtube_quiet_master_downward_only() -> None:
    """YouTube is downward-only; a -20 LUFS track gets 0 penalty (played at measured)."""
    predictor = LoudnessPenaltyPredictor()
    result = predictor.predict_penalty(-20.0, "youtube")
    assert result["penalty_db"] == 0.0
    assert result["direction"] == "downward_only"


def test_predict_penalty_apple_music_loud_master_bidirectional() -> None:
    """Apple Sound Check is bidirectional with no limiter — -8 → -16 is -8 dB."""
    predictor = LoudnessPenaltyPredictor()
    result = predictor.predict_penalty(-8.0, "apple_music")
    assert result["penalty_db"] == pytest.approx(-8.0)
    assert result["applies_limiter"] is False
    assert result["direction"] == "bidirectional"


def test_predict_penalty_spotify_loud_limiter_cap() -> None:
    """Spotify Loud limiter caps attenuation at -1 dB for masters above -11 LUFS."""
    predictor = LoudnessPenaltyPredictor()
    result = predictor.predict_penalty(-9.0, "spotify_loud")
    # target - measured = -11 - (-9) = -2; limiter caps to min(-2, -1) = -2.
    # For a master at -9 LUFS, raw penalty is -2 dB, which is <= -1, so limiter
    # clamp of min(penalty, -1) keeps -2. Test the clamp path directly.
    assert result["penalty_db"] <= -1.0
    assert result["applies_limiter"] is True
    # For a borderline master right at -10.5 LUFS: raw penalty = -0.5, then
    # min(-0.5, -1) = -1. Verify clamp engages.
    result2 = predictor.predict_penalty(-10.5, "spotify_loud")
    assert result2["penalty_db"] == pytest.approx(-1.0)


def test_predict_all_platforms_sorted_worst_first() -> None:
    predictor = LoudnessPenaltyPredictor()
    results = predictor.predict_all_platforms(-10.0)
    assert len(results) == 8
    assert len(results) == len(PLATFORM_RULES)
    magnitudes = [abs(r["penalty_db"]) for r in results]
    assert magnitudes == sorted(magnitudes, reverse=True)
    platforms = {r["platform"] for r in results}
    assert platforms == set(PLATFORM_RULES.keys())


def test_predict_penalty_unknown_platform_raises() -> None:
    predictor = LoudnessPenaltyPredictor()
    with pytest.raises(ValueError):
        predictor.predict_penalty(-14.0, "pandora")
