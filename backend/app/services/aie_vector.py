"""RAIN Artist Identity Engine (AIE) — 64-dimensional preference vector.

64-Dim Vector Decomposition (FROM BLUEPRINT — EXACT):

Indices [0:16) — EQ (16 dims)
  [0:8)   8 frequency band preferences
          (sub, low, low-mid, mid, mid-hi, hi, presence, air)
  [8:12)  4 Q/bandwidth preferences
  [12]    tonal balance target
  [13]    mid-side tendency
  [14:16) reserved EQ extension

Indices [16:28) — Dynamics (12 dims)
  [16]    ratio preference                       (maps from [1.0, 20.0])
  [17]    attack preference                      (maps from [0.0, 100.0] ms)
  [18]    release preference                     (maps from [0.0, 500.0] ms)
  [19]    loudness target                        (maps from [-24.0, -8.0] LUFS)
  [20:24) multiband band weights (4 dims)
  [24:28) transient handling (4 dims)

Indices [28:34) — Stereo/Spatial (6 dims)
  [28]    stereo width preference                (maps from [0.0, 2.0])
  [29]    mono bass tendency
  [30]    side energy
  [31]    depth/reverb preference
  [32:34) stereo reserved

Indices [34:42) — Coloring/Saturation (8 dims)
  [34]    tape saturation
  [35]    tube warmth
  [36]    console character
  [37]    transformer color
  [38:42) saturation reserved

Indices [42:52) — Genre/Context (10 dims)
  [42:48) genre embedding (6-dim compressed from MERT)
  [48]    era preference                         (maps from [1970, 2025])
  [49:52) reference track cluster centroid (3 dims)

Indices [52:64) — Meta-preferences (12 dims)
  [52]    aggressive vs conservative
  [53]    platform optimization priority
  [54]    revision behavior
  [55]    reference match weight
  [56]    analog vs clean preference
  [57]    loudness push tendency
  [58:64) meta reserved

All values normalized to [-1.0, 1.0].
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any
from uuid import UUID

import structlog
from sqlalchemy import text

logger = structlog.get_logger()

# --------------------------------------------------------------------------- #
# Constants — vector layout
# --------------------------------------------------------------------------- #
VECTOR_DIM: int = 64

EQ_BANDS = slice(0, 8)
EQ_Q = slice(8, 12)
EQ_TONAL_BALANCE = 12
EQ_MID_SIDE_TENDENCY = 13
EQ_RESERVED = slice(14, 16)

DYN_RATIO = 16
DYN_ATTACK = 17
DYN_RELEASE = 18
DYN_LOUDNESS = 19
DYN_MB_WEIGHTS = slice(20, 24)
DYN_TRANSIENT = slice(24, 28)

STEREO_WIDTH = 28
STEREO_MONO_BASS = 29
STEREO_SIDE_ENERGY = 30
STEREO_DEPTH = 31
STEREO_RESERVED = slice(32, 34)

SAT_TAPE = 34
SAT_TUBE = 35
SAT_CONSOLE = 36
SAT_TRANSFORMER = 37
SAT_RESERVED = slice(38, 42)

GENRE_EMBEDDING = slice(42, 48)
GENRE_ERA = 48
GENRE_REF_CENTROID = slice(49, 52)

META_AGGRESSIVE = 52
META_PLATFORM_PRIO = 53
META_REVISION = 54
META_REF_MATCH_WEIGHT = 55
META_ANALOG_VS_CLEAN = 56
META_LOUDNESS_PUSH = 57
META_RESERVED = slice(58, 64)

# EMA hyperparameters
ALPHA_STABLE: float = 0.90
ALPHA_COLD_START: float = 0.60
COLD_START_SESSIONS: int = 5


@dataclass(frozen=True)
class ObservationSource:
    """Observation weight constants for EMA blending."""
    EXPLICIT: float = 1.0          # user-entered adjustment
    AI_ACCEPTED: float = 0.6       # accepted AI suggestion
    IMPLICIT: float = 0.3          # user did not re-master


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _norm_linear(v: float, lo: float, hi: float) -> float:
    """Linearly map [lo, hi] to [-1.0, 1.0]. Clamps out-of-range."""
    if hi == lo:
        return 0.0
    t = (v - lo) / (hi - lo)          # 0..1
    return _clamp(2.0 * t - 1.0)


# --------------------------------------------------------------------------- #
# Factories
# --------------------------------------------------------------------------- #
def new_zero_vector() -> list[float]:
    """Return a fresh 64-dim zero vector."""
    return [0.0] * VECTOR_DIM


def genre_centroid_vector(genre: str) -> list[float]:
    """Return hardcoded genre centroid for a given genre.

    If genre is unknown, returns a zero vector (NO random defaults).
    Per-genre design choices are documented inline.
    """
    g = (genre or "").strip().lower()
    vec = new_zero_vector()

    if g == "rock":
        # Rock: moderate loudness push, moderate analog, mid-forward EQ.
        vec[DYN_LOUDNESS] = _norm_linear(-10.0, -24.0, -8.0)     # ~-10 LUFS
        vec[META_AGGRESSIVE] = 0.4
        vec[META_LOUDNESS_PUSH] = 0.5
        vec[META_ANALOG_VS_CLEAN] = 0.3
        vec[SAT_TAPE] = 0.4
        vec[SAT_CONSOLE] = 0.3
        vec[STEREO_WIDTH] = _norm_linear(1.1, 0.0, 2.0)
        vec[DYN_RATIO] = _norm_linear(3.0, 1.0, 20.0)

    elif g == "pop":
        # Pop: bright, wide, heavily loudness-pushed, mostly clean.
        vec[DYN_LOUDNESS] = _norm_linear(-9.0, -24.0, -8.0)
        vec[META_AGGRESSIVE] = 0.5
        vec[META_LOUDNESS_PUSH] = 0.7
        vec[META_ANALOG_VS_CLEAN] = -0.2
        vec[STEREO_WIDTH] = _norm_linear(1.2, 0.0, 2.0)
        vec[EQ_BANDS.start + 7] = 0.3    # air boost
        vec[EQ_BANDS.start + 6] = 0.2    # presence
        vec[DYN_RATIO] = _norm_linear(3.5, 1.0, 20.0)

    elif g in ("hiphop", "hip-hop", "rap"):
        # Hip-hop: sub-heavy, mono bass, high loudness, punchy dynamics.
        vec[DYN_LOUDNESS] = _norm_linear(-8.5, -24.0, -8.0)
        vec[META_AGGRESSIVE] = 0.6
        vec[META_LOUDNESS_PUSH] = 0.8
        vec[EQ_BANDS.start + 0] = 0.5    # sub
        vec[EQ_BANDS.start + 1] = 0.3    # low
        vec[STEREO_MONO_BASS] = 0.7
        vec[DYN_TRANSIENT.start] = 0.4
        vec[DYN_RATIO] = _norm_linear(4.0, 1.0, 20.0)

    elif g == "electronic":
        # Electronic: wide, clean, very loud, bright air.
        vec[DYN_LOUDNESS] = _norm_linear(-8.0, -24.0, -8.0)
        vec[META_AGGRESSIVE] = 0.5
        vec[META_LOUDNESS_PUSH] = 0.75
        vec[META_ANALOG_VS_CLEAN] = -0.5
        vec[STEREO_WIDTH] = _norm_linear(1.4, 0.0, 2.0)
        vec[EQ_BANDS.start + 7] = 0.4    # air
        vec[EQ_BANDS.start + 0] = 0.4    # sub
        vec[DYN_RATIO] = _norm_linear(4.0, 1.0, 20.0)

    elif g == "jazz":
        # Jazz: preserve dynamics, warm, natural stereo.
        vec[DYN_LOUDNESS] = _norm_linear(-16.0, -24.0, -8.0)
        vec[META_AGGRESSIVE] = -0.4
        vec[META_LOUDNESS_PUSH] = -0.5
        vec[META_ANALOG_VS_CLEAN] = 0.6
        vec[SAT_TUBE] = 0.5
        vec[SAT_TAPE] = 0.3
        vec[STEREO_WIDTH] = _norm_linear(1.0, 0.0, 2.0)
        vec[DYN_RATIO] = _norm_linear(1.8, 1.0, 20.0)

    elif g == "classical":
        # Classical: dynamic range preserved, clean, natural, low loudness push.
        vec[DYN_LOUDNESS] = _norm_linear(-18.0, -24.0, -8.0)
        vec[META_AGGRESSIVE] = -0.7
        vec[META_LOUDNESS_PUSH] = -0.8
        vec[META_ANALOG_VS_CLEAN] = -0.4
        vec[STEREO_WIDTH] = _norm_linear(1.0, 0.0, 2.0)
        vec[DYN_MB_WEIGHTS.start] = -0.3
        vec[DYN_RATIO] = _norm_linear(1.5, 1.0, 20.0)

    elif g == "metal":
        # Metal: aggressive, loud, analog-colored, mid-forward.
        vec[DYN_LOUDNESS] = _norm_linear(-8.5, -24.0, -8.0)
        vec[META_AGGRESSIVE] = 0.85
        vec[META_LOUDNESS_PUSH] = 0.85
        vec[META_ANALOG_VS_CLEAN] = 0.4
        vec[SAT_TAPE] = 0.5
        vec[SAT_TUBE] = 0.4
        vec[SAT_CONSOLE] = 0.5
        vec[EQ_BANDS.start + 3] = 0.3    # mid
        vec[EQ_BANDS.start + 4] = 0.35   # mid-hi
        vec[STEREO_WIDTH] = _norm_linear(1.15, 0.0, 2.0)
        vec[DYN_RATIO] = _norm_linear(5.0, 1.0, 20.0)

    elif g == "country":
        # Country: natural, warm, mid-range clarity.
        vec[DYN_LOUDNESS] = _norm_linear(-12.0, -24.0, -8.0)
        vec[META_AGGRESSIVE] = 0.0
        vec[META_LOUDNESS_PUSH] = 0.1
        vec[META_ANALOG_VS_CLEAN] = 0.5
        vec[SAT_TAPE] = 0.4
        vec[EQ_BANDS.start + 3] = 0.2
        vec[EQ_BANDS.start + 6] = 0.2
        vec[STEREO_WIDTH] = _norm_linear(1.05, 0.0, 2.0)
        vec[DYN_RATIO] = _norm_linear(2.5, 1.0, 20.0)

    elif g in ("rnb", "r&b", "randb"):
        # R&B: warm low-end, smooth highs, moderate loudness.
        vec[DYN_LOUDNESS] = _norm_linear(-11.0, -24.0, -8.0)
        vec[META_AGGRESSIVE] = 0.1
        vec[META_LOUDNESS_PUSH] = 0.4
        vec[META_ANALOG_VS_CLEAN] = 0.4
        vec[SAT_TUBE] = 0.4
        vec[SAT_TAPE] = 0.3
        vec[EQ_BANDS.start + 0] = 0.3
        vec[EQ_BANDS.start + 6] = 0.25
        vec[STEREO_WIDTH] = _norm_linear(1.15, 0.0, 2.0)
        vec[DYN_RATIO] = _norm_linear(2.8, 1.0, 20.0)

    elif g == "folk":
        # Folk: minimal processing, natural dynamics, warm acoustic character.
        vec[DYN_LOUDNESS] = _norm_linear(-15.0, -24.0, -8.0)
        vec[META_AGGRESSIVE] = -0.5
        vec[META_LOUDNESS_PUSH] = -0.4
        vec[META_ANALOG_VS_CLEAN] = 0.5
        vec[SAT_TAPE] = 0.3
        vec[SAT_TUBE] = 0.3
        vec[STEREO_WIDTH] = _norm_linear(1.0, 0.0, 2.0)
        vec[DYN_RATIO] = _norm_linear(1.8, 1.0, 20.0)

    else:
        # Unknown genre — strict zero (no fake data).
        return new_zero_vector()

    # Safety clamp
    return [_clamp(x) for x in vec]


# --------------------------------------------------------------------------- #
# Observation extraction from ProcessingParams
# --------------------------------------------------------------------------- #
def extract_observation_from_params(processing_params: dict) -> list[float]:
    """Convert a canonical ProcessingParams dict into a 64-dim observation vector.

    Field mapping (keys must match the canonical schema exactly):
      target_lufs        -> [19]       via [-24, -8]  normalization
      mb_ratio_low       -> [16]       via [1, 20]
      mb_ratio_mid       -> [20]       (multiband band weight — mid)
      mb_ratio_high      -> [21]       (multiband band weight — high)
      mb_attack_low      -> [17]       via [0, 100] ms
      mb_release_low     -> [18]       via [0, 500] ms
      stereo_width       -> [28]       via [0, 2]
      analog_saturation  -> [34] sign bit; combined with saturation_drive
      saturation_drive   -> [34]       via [0, 1]
      saturation_mode    -> [35] tube / [36] console / [37] transformer
      ms_enabled         -> [13]       mid-side tendency
      mid_gain           -> [12]       tonal balance (dB / 6)
      side_gain          -> [30]       side energy (dB / 6)
      eq_gains[0..7]     -> [0..7]     via [-12, +12] dB
      mb_threshold_low   -> [20] weight component (combined with ratio)
      mb_threshold_mid   -> [22]
      mb_threshold_high  -> [23]

    Fields with no direct mapping (true_peak_ceiling, sail_*, vinyl_mode,
    mb_attack_mid, mb_attack_high, mb_release_mid, mb_release_high) remain 0.
    """
    vec = new_zero_vector()
    p = processing_params or {}

    # EQ (8 band gains) — [-12, +12] dB
    eq_gains = p.get("eq_gains") or [0.0] * 8
    for i in range(min(8, len(eq_gains))):
        vec[EQ_BANDS.start + i] = _norm_linear(float(eq_gains[i]), -12.0, 12.0)

    # Tonal balance via mid_gain
    if "mid_gain" in p:
        vec[EQ_TONAL_BALANCE] = _clamp(float(p["mid_gain"]) / 6.0)

    # Mid-side tendency (binary bool mapped to +1 / 0)
    if "ms_enabled" in p:
        vec[EQ_MID_SIDE_TENDENCY] = 1.0 if bool(p["ms_enabled"]) else 0.0

    # Dynamics
    if "mb_ratio_low" in p:
        vec[DYN_RATIO] = _norm_linear(float(p["mb_ratio_low"]), 1.0, 20.0)
    if "mb_attack_low" in p:
        vec[DYN_ATTACK] = _norm_linear(float(p["mb_attack_low"]), 0.0, 100.0)
    if "mb_release_low" in p:
        vec[DYN_RELEASE] = _norm_linear(float(p["mb_release_low"]), 0.0, 500.0)
    if "target_lufs" in p:
        vec[DYN_LOUDNESS] = _norm_linear(float(p["target_lufs"]), -24.0, -8.0)

    # Multiband band weights: use ratios and thresholds
    if "mb_ratio_mid" in p:
        vec[DYN_MB_WEIGHTS.start + 0] = _norm_linear(float(p["mb_ratio_mid"]), 1.0, 20.0)
    if "mb_ratio_high" in p:
        vec[DYN_MB_WEIGHTS.start + 1] = _norm_linear(float(p["mb_ratio_high"]), 1.0, 20.0)
    if "mb_threshold_mid" in p:
        vec[DYN_MB_WEIGHTS.start + 2] = _norm_linear(float(p["mb_threshold_mid"]), -40.0, 0.0)
    if "mb_threshold_high" in p:
        vec[DYN_MB_WEIGHTS.start + 3] = _norm_linear(float(p["mb_threshold_high"]), -40.0, 0.0)

    # Stereo / spatial
    if "stereo_width" in p:
        vec[STEREO_WIDTH] = _norm_linear(float(p["stereo_width"]), 0.0, 2.0)
    if "side_gain" in p:
        vec[STEREO_SIDE_ENERGY] = _clamp(float(p["side_gain"]) / 6.0)

    # Saturation / coloring
    sat_enabled = bool(p.get("analog_saturation", False))
    drive = float(p.get("saturation_drive", 0.0))
    mode = str(p.get("saturation_mode", "tape")).lower()
    # Convert [0,1] drive to [-1,+1]; if not enabled, keep 0.
    drive_normed = _norm_linear(drive, 0.0, 1.0) if sat_enabled else 0.0
    if mode == "tape":
        vec[SAT_TAPE] = drive_normed
    elif mode == "tube":
        vec[SAT_TUBE] = drive_normed
    elif mode == "transistor":
        # "transistor" in ProcessingParams maps to console character
        vec[SAT_CONSOLE] = drive_normed
    # transformer channel reserved for explicit future mode
    # Meta analog vs clean is driven by saturation enablement
    vec[META_ANALOG_VS_CLEAN] = drive_normed

    # Meta: loudness push derived from target_lufs
    if "target_lufs" in p:
        # target_lufs near -8 = high push; near -24 = low push.
        vec[META_LOUDNESS_PUSH] = _norm_linear(float(p["target_lufs"]), -24.0, -8.0)

    return [_clamp(x) for x in vec]


# --------------------------------------------------------------------------- #
# EMA update rule
# --------------------------------------------------------------------------- #
def apply_ema_update(
    old_vec: list[float],
    obs_vec: list[float],
    weight: float,
    alpha: float,
) -> list[float]:
    """Apply blended EMA update rule:

        new_vec = alpha * old_vec + (1 - alpha) * (weight * obs_vec + (1 - weight) * old_vec)

    Deterministic, no RNG.
    """
    if len(old_vec) != VECTOR_DIM or len(obs_vec) != VECTOR_DIM:
        raise ValueError(
            f"Both vectors must be length {VECTOR_DIM} "
            f"(got old={len(old_vec)}, obs={len(obs_vec)})"
        )
    one_minus_alpha = 1.0 - alpha
    one_minus_weight = 1.0 - weight
    out: list[float] = [0.0] * VECTOR_DIM
    for i in range(VECTOR_DIM):
        blended = weight * obs_vec[i] + one_minus_weight * old_vec[i]
        out[i] = _clamp(alpha * old_vec[i] + one_minus_alpha * blended)
    return out


# --------------------------------------------------------------------------- #
# DB I/O
# --------------------------------------------------------------------------- #
async def load_or_init_vector(
    db: Any,
    user_id: str | UUID,
    genre_hint: Optional[str],
) -> tuple[list[float], dict]:
    """Load the aie_vectors row for user_id, or initialize from genre centroid / zeros.

    Returns (vector, meta) where meta = {
        obs_count: int,
        cold_start_remaining: int,
        genre_centroid: list[float] | None,
    }.

    Never writes. Caller is responsible for persistence.
    """
    uid_str = str(user_id)
    await db.execute(text(f"SELECT set_app_user_id('{uid_str}'::uuid)"))

    row = (await db.execute(
        text(
            "SELECT vector, observation_count, cold_start_sessions_remaining, "
            "genre_centroid FROM aie_vectors WHERE user_id = :uid"
        ),
        {"uid": uid_str},
    )).first()

    if row is not None:
        vector = list(row[0]) if row[0] is not None else new_zero_vector()
        obs_count = int(row[1] or 0)
        cold_remaining = int(row[2] or 0)
        centroid = list(row[3]) if row[3] is not None else None
        return vector, {
            "obs_count": obs_count,
            "cold_start_remaining": cold_remaining,
            "genre_centroid": centroid,
        }

    # Cold init
    if genre_hint:
        centroid = genre_centroid_vector(genre_hint)
        # If centroid is all zeros (unknown genre), treat as no centroid.
        has_signal = any(abs(x) > 1e-9 for x in centroid)
        initial_vec = centroid if has_signal else new_zero_vector()
        stored_centroid = centroid if has_signal else None
    else:
        initial_vec = new_zero_vector()
        stored_centroid = None

    return initial_vec, {
        "obs_count": 0,
        "cold_start_remaining": COLD_START_SESSIONS,
        "genre_centroid": stored_centroid,
    }


async def record_observation(
    db: Any,
    user_id: str | UUID,
    processing_params: dict,
    source: float,
) -> None:
    """Full EMA record flow: load, extract, update, persist.

    Uses INSERT ON CONFLICT DO UPDATE on aie_vectors(user_id).
    RLS is enforced via set_app_user_id.
    """
    uid_str = str(user_id)
    genre_hint = processing_params.get("_genre") if isinstance(processing_params, dict) else None

    old_vec, meta = await load_or_init_vector(db, uid_str, genre_hint)
    obs_vec = extract_observation_from_params(processing_params)

    cold_remaining = int(meta["cold_start_remaining"])
    alpha = ALPHA_COLD_START if cold_remaining > 0 else ALPHA_STABLE
    weight = float(source)

    new_vec = apply_ema_update(old_vec, obs_vec, weight=weight, alpha=alpha)

    new_obs_count = int(meta["obs_count"]) + 1
    new_cold_remaining = max(0, cold_remaining - 1)
    centroid = meta.get("genre_centroid")

    await db.execute(text(f"SELECT set_app_user_id('{uid_str}'::uuid)"))
    await db.execute(
        text(
            "INSERT INTO aie_vectors "
            "(user_id, vector, observation_count, cold_start_sessions_remaining, "
            " genre_centroid, updated_at) "
            "VALUES (:uid, :vec, :oc, :cr, :gc, NOW()) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "  vector = EXCLUDED.vector, "
            "  observation_count = EXCLUDED.observation_count, "
            "  cold_start_sessions_remaining = EXCLUDED.cold_start_sessions_remaining, "
            "  genre_centroid = COALESCE(aie_vectors.genre_centroid, EXCLUDED.genre_centroid), "
            "  updated_at = NOW()"
        ),
        {
            "uid": uid_str,
            "vec": new_vec,
            "oc": new_obs_count,
            "cr": new_cold_remaining,
            "gc": centroid,
        },
    )
    await db.commit()

    logger.info(
        "aie_vector_updated",
        user_id=uid_str,
        observation_count=new_obs_count,
        cold_start_remaining=new_cold_remaining,
        alpha=alpha,
        weight=weight,
        stage="aie",
    )


# --------------------------------------------------------------------------- #
# Inverse mapping: 64-dim vector -> ProcessingParams delta
# --------------------------------------------------------------------------- #
def _denorm_linear(x: float, lo: float, hi: float) -> float:
    """Inverse of _norm_linear — maps [-1, 1] back to [lo, hi]."""
    t = (_clamp(x) + 1.0) / 2.0
    return lo + t * (hi - lo)


async def vector_to_params_delta(vector: list[float]) -> dict:
    """Convert a 64-dim AIE vector into a ProcessingParams delta dict.

    Output keys match the canonical ProcessingParams schema EXACTLY.
    Used at mastering start to bias inference/heuristic fallback toward user
    preferences. Merges into baseline defaults — not an authoritative full
    params dict.
    """
    if len(vector) != VECTOR_DIM:
        raise ValueError(f"Vector must be length {VECTOR_DIM}")

    delta: dict = {}

    # Loudness / target
    delta["target_lufs"] = _denorm_linear(vector[DYN_LOUDNESS], -24.0, -8.0)

    # Multiband ratios
    delta["mb_ratio_low"] = _denorm_linear(vector[DYN_RATIO], 1.0, 20.0)
    delta["mb_ratio_mid"] = _denorm_linear(vector[DYN_MB_WEIGHTS.start + 0], 1.0, 20.0)
    delta["mb_ratio_high"] = _denorm_linear(vector[DYN_MB_WEIGHTS.start + 1], 1.0, 20.0)

    # Multiband thresholds
    delta["mb_threshold_mid"] = _denorm_linear(vector[DYN_MB_WEIGHTS.start + 2], -40.0, 0.0)
    delta["mb_threshold_high"] = _denorm_linear(vector[DYN_MB_WEIGHTS.start + 3], -40.0, 0.0)

    # Attack / release (low band)
    delta["mb_attack_low"] = _denorm_linear(vector[DYN_ATTACK], 0.0, 100.0)
    delta["mb_release_low"] = _denorm_linear(vector[DYN_RELEASE], 0.0, 500.0)

    # EQ gains (8 bands)
    delta["eq_gains"] = [
        _denorm_linear(vector[EQ_BANDS.start + i], -12.0, 12.0) for i in range(8)
    ]

    # Stereo
    delta["stereo_width"] = _denorm_linear(vector[STEREO_WIDTH], 0.0, 2.0)
    delta["side_gain"] = _clamp(vector[STEREO_SIDE_ENERGY]) * 6.0
    delta["mid_gain"] = _clamp(vector[EQ_TONAL_BALANCE]) * 6.0
    delta["ms_enabled"] = vector[EQ_MID_SIDE_TENDENCY] > 0.5

    # Saturation
    sat_channels = {
        "tape": vector[SAT_TAPE],
        "tube": vector[SAT_TUBE],
        "transistor": vector[SAT_CONSOLE],
    }
    dominant_mode = max(sat_channels.items(), key=lambda kv: kv[1])
    dominant_value = dominant_mode[1]
    delta["analog_saturation"] = dominant_value > 0.0
    delta["saturation_drive"] = _denorm_linear(max(0.0, dominant_value), 0.0, 1.0) if dominant_value > 0.0 else 0.0
    delta["saturation_mode"] = dominant_mode[0] if dominant_value > 0.0 else "tape"

    return delta
