"""
Multi-platform loudness penalty predictor for RAIN.

Predicts the normalization penalty (in dB) that each major streaming platform
will apply to a master based on its measured integrated loudness (LUFS-I).

Loudness targets per platform come from published platform documentation and
industry consensus. Measurement is performed using ITU-R BS.1770-4 /
EBU R 128 K-weighting (via pyloudnorm).

Platform rules (EXACT):
  - Spotify Normal:     -14 LUFS, bidirectional, no limiter
  - Spotify Loud:       -11 LUFS, bidirectional, limiter 5ms/100ms at -1 dBTP
  - Apple Sound Check:  -16 LUFS, bidirectional, no limiter
  - YouTube:            -14 LUFS, downward only, no limiter
  - Tidal:              -14 LUFS, downward only, no limiter (album-only)
  - Amazon Music:       -14 LUFS, bidirectional, no limiter
  - SoundCloud:         -14 LUFS, downward only, no limiter
  - Deezer:             -15 LUFS, bidirectional, no limiter

Penalty calculation:
    penalty_db = platform_target - measured_lufs_I
    if direction == "downward_only" and penalty_db > 0: penalty_db = 0
    if applies_limiter and measured_lufs > -11: penalty_db = min(penalty_db, -1)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
import structlog

logger = structlog.get_logger()


Platform = Literal[
    "spotify_normal",
    "spotify_loud",
    "apple_music",
    "youtube",
    "tidal",
    "amazon_music",
    "soundcloud",
    "deezer",
]

Direction = Literal["bidirectional", "downward_only"]


@dataclass(frozen=True)
class PlatformRule:
    target_lufs: float
    direction: Direction
    applies_limiter: bool
    limiter_ceiling_dbtp: Optional[float]
    album_only: bool


PLATFORM_RULES: dict[str, PlatformRule] = {
    "spotify_normal": PlatformRule(
        target_lufs=-14.0,
        direction="bidirectional",
        applies_limiter=False,
        limiter_ceiling_dbtp=None,
        album_only=False,
    ),
    "spotify_loud": PlatformRule(
        target_lufs=-11.0,
        direction="bidirectional",
        applies_limiter=True,
        limiter_ceiling_dbtp=-1.0,
        album_only=False,
    ),
    "apple_music": PlatformRule(
        target_lufs=-16.0,
        direction="bidirectional",
        applies_limiter=False,
        limiter_ceiling_dbtp=None,
        album_only=False,
    ),
    "youtube": PlatformRule(
        target_lufs=-14.0,
        direction="downward_only",
        applies_limiter=False,
        limiter_ceiling_dbtp=None,
        album_only=False,
    ),
    "tidal": PlatformRule(
        target_lufs=-14.0,
        direction="downward_only",
        applies_limiter=False,
        limiter_ceiling_dbtp=None,
        album_only=True,
    ),
    "amazon_music": PlatformRule(
        target_lufs=-14.0,
        direction="bidirectional",
        applies_limiter=False,
        limiter_ceiling_dbtp=None,
        album_only=False,
    ),
    "soundcloud": PlatformRule(
        target_lufs=-14.0,
        direction="downward_only",
        applies_limiter=False,
        limiter_ceiling_dbtp=None,
        album_only=False,
    ),
    "deezer": PlatformRule(
        target_lufs=-15.0,
        direction="bidirectional",
        applies_limiter=False,
        limiter_ceiling_dbtp=None,
        album_only=False,
    ),
}


class LoudnessPenaltyPredictor:
    """Predicts per-platform loudness normalization penalties."""

    def measure_lufs(self, samples: np.ndarray, sample_rate: int) -> float:
        """
        Measure integrated loudness (LUFS-I) using ITU-R BS.1770-4 K-weighting.

        Args:
            samples: float64 PCM samples. Shape (n,) mono or (n, channels).
            sample_rate: samples per second.

        Returns:
            Integrated loudness in LUFS.
        """
        import pyloudnorm as pyln

        if samples.ndim == 1:
            data = samples.astype(np.float64)
        else:
            data = samples.astype(np.float64)

        meter = pyln.Meter(sample_rate)  # BS.1770-4
        lufs = float(meter.integrated_loudness(data))
        logger.info(
            "loudness_penalty.measure_lufs",
            sample_rate=sample_rate,
            n_samples=int(samples.shape[0]),
            lufs=lufs,
        )
        return lufs

    def predict_penalty(self, measured_lufs: float, platform: str) -> dict:
        """
        Predict the dB penalty that `platform` will apply to a master at
        `measured_lufs` integrated loudness.

        Returns dict with keys:
            penalty_db, target_lufs, applies_limiter, direction, platform, warning
        """
        if platform not in PLATFORM_RULES:
            raise ValueError(
                f"Unknown platform: {platform!r}. "
                f"Valid: {sorted(PLATFORM_RULES.keys())}"
            )
        rule = PLATFORM_RULES[platform]

        penalty_db = rule.target_lufs - measured_lufs

        if rule.direction == "downward_only" and penalty_db > 0:
            penalty_db = 0.0

        if rule.applies_limiter and measured_lufs > -11.0:
            # Spotify Loud limiter attenuates to a -1 dBTP ceiling.
            penalty_db = min(penalty_db, -1.0)

        warning: Optional[str] = None
        if rule.applies_limiter and measured_lufs > -11.0:
            warning = (
                f"Limiter engagement likely on {platform}: master measures "
                f"{measured_lufs:.1f} LUFS, above {rule.target_lufs:.1f} LUFS target; "
                f"platform limiter (ceiling {rule.limiter_ceiling_dbtp} dBTP) will attenuate."
            )
        elif penalty_db < -3.0:
            warning = (
                f"Audible attenuation on {platform}: {penalty_db:.1f} dB down "
                f"from master loudness."
            )

        result = {
            "penalty_db": float(penalty_db),
            "target_lufs": float(rule.target_lufs),
            "applies_limiter": bool(rule.applies_limiter),
            "direction": rule.direction,
            "platform": platform,
            "warning": warning,
        }
        return result

    def predict_all_platforms(self, measured_lufs: float) -> list[dict]:
        """Predict penalty for every platform, sorted worst-first by |penalty_db|."""
        results = [
            self.predict_penalty(measured_lufs, platform)
            for platform in PLATFORM_RULES.keys()
        ]
        results.sort(key=lambda r: abs(r["penalty_db"]), reverse=True)
        return results


async def get_or_compute_penalty(
    db,
    input_hash: str,
    platform: str,
    samples: Optional[np.ndarray],
    sample_rate: Optional[int],
) -> dict:
    """
    Return a cached loudness penalty row for (input_hash, platform), or compute
    and store it from the provided samples.

    The cache table `loudness_penalty_cache` stores:
        input_hash, platform, measured_lufs, penalty_db, target_lufs,
        applies_limiter, computed_at
    """
    from sqlalchemy import text

    if platform not in PLATFORM_RULES:
        raise ValueError(
            f"Unknown platform: {platform!r}. Valid: {sorted(PLATFORM_RULES.keys())}"
        )

    select_sql = text(
        """
        SELECT measured_lufs, penalty_db, target_lufs, applies_limiter
        FROM loudness_penalty_cache
        WHERE input_hash = :input_hash AND platform = :platform
        """
    )
    row = (
        await db.execute(
            select_sql, {"input_hash": input_hash, "platform": platform}
        )
    ).first()

    if row is not None:
        logger.info(
            "loudness_penalty.cache_hit",
            input_hash=input_hash,
            platform=platform,
        )
        rule = PLATFORM_RULES[platform]
        measured_lufs = float(row[0])
        penalty_db = float(row[1])
        warning: Optional[str] = None
        if rule.applies_limiter and measured_lufs > -11.0:
            warning = (
                f"Limiter engagement likely on {platform}: master measures "
                f"{measured_lufs:.1f} LUFS, above {rule.target_lufs:.1f} LUFS target; "
                f"platform limiter (ceiling {rule.limiter_ceiling_dbtp} dBTP) will attenuate."
            )
        elif penalty_db < -3.0:
            warning = (
                f"Audible attenuation on {platform}: {penalty_db:.1f} dB down "
                f"from master loudness."
            )
        return {
            "penalty_db": penalty_db,
            "target_lufs": float(row[2]),
            "applies_limiter": bool(row[3]),
            "direction": rule.direction,
            "platform": platform,
            "warning": warning,
            "measured_lufs": measured_lufs,
            "cached": True,
        }

    if samples is None or sample_rate is None:
        raise ValueError(
            "Cache miss and no samples provided — cannot compute penalty."
        )

    predictor = LoudnessPenaltyPredictor()
    measured_lufs = predictor.measure_lufs(samples, sample_rate)
    prediction = predictor.predict_penalty(measured_lufs, platform)

    upsert_sql = text(
        """
        INSERT INTO loudness_penalty_cache
            (input_hash, platform, measured_lufs, penalty_db, target_lufs,
             applies_limiter, computed_at)
        VALUES
            (:input_hash, :platform, :measured_lufs, :penalty_db, :target_lufs,
             :applies_limiter, NOW())
        ON CONFLICT (input_hash, platform) DO UPDATE SET
            measured_lufs   = EXCLUDED.measured_lufs,
            penalty_db      = EXCLUDED.penalty_db,
            target_lufs     = EXCLUDED.target_lufs,
            applies_limiter = EXCLUDED.applies_limiter,
            computed_at     = EXCLUDED.computed_at
        """
    )
    await db.execute(
        upsert_sql,
        {
            "input_hash": input_hash,
            "platform": platform,
            "measured_lufs": measured_lufs,
            "penalty_db": prediction["penalty_db"],
            "target_lufs": prediction["target_lufs"],
            "applies_limiter": prediction["applies_limiter"],
        },
    )
    logger.info(
        "loudness_penalty.cache_store",
        input_hash=input_hash,
        platform=platform,
        measured_lufs=measured_lufs,
        penalty_db=prediction["penalty_db"],
    )

    prediction["measured_lufs"] = measured_lufs
    prediction["cached"] = False
    return prediction
