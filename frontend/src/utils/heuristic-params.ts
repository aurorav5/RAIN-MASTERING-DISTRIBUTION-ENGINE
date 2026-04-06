import type { ProcessingParams } from '../types/dsp'

/**
 * RAIN Heuristic Fallback — Canonical ProcessingParams per CLAUDE.md
 *
 * When RAIN_NORMALIZATION_VALIDATED=false, this module produces a deterministic
 * ProcessingParams from (genre, platform) pairs.
 *
 * AUTHORITATIVE SOURCE: backend/app/services/heuristic_params.py (PART-4 Task 4.2)
 * Values MUST be identical for the same (genre, platform) pair.
 * If the backend values change, update here to match.
 *
 * Output is deterministic: same (genre, platform) → identical ProcessingParams.
 */

/**
 * Canonical ProcessingParams with all defaults per CLAUDE.md.
 * Must match backend default_params() exactly.
 */
function defaultParams(): ProcessingParams {
  return {
    // Loudness target
    target_lufs: -14.0,
    true_peak_ceiling: -1.0,

    // Multiband dynamics (3-band: low/mid/high)
    mb_threshold_low: -18.0,
    mb_threshold_mid: -15.0,
    mb_threshold_high: -12.0,
    mb_ratio_low: 2.5,
    mb_ratio_mid: 2.0,
    mb_ratio_high: 2.0,
    mb_attack_low: 10.0,
    mb_attack_mid: 5.0,
    mb_attack_high: 2.0,
    mb_release_low: 150.0,
    mb_release_mid: 80.0,
    mb_release_high: 40.0,

    // EQ (8-band parametric)
    eq_gains: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],

    // Analog saturation
    analog_saturation: false,
    saturation_drive: 0.0,
    saturation_mode: 'tape',

    // Mid/Side processing
    ms_enabled: false,
    mid_gain: 0.0,
    side_gain: 0.0,
    stereo_width: 1.0,

    // SAIL (Stem-Aware Intelligent Limiting)
    sail_enabled: false,
    sail_stem_gains: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], // float[12] SAIL v2

    // Vinyl mode
    vinyl_mode: false,

    // Macro controls (defaults — overridden per genre below)
    macro_brighten: 5.0,
    macro_glue: 5.0,
    macro_width: 5.0,
    macro_punch: 5.0,
    macro_warmth: 5.0,
    macro_space: 5.0,
    macro_repair: 0.0,
  }
}

/**
 * Genre-specific overrides. Must match backend GENRE_OVERRIDES exactly.
 * Keys and values are 1:1 with backend/app/services/heuristic_params.py.
 */
const GENRE_OVERRIDES: Record<string, Partial<ProcessingParams>> = {
  electronic: {
    mb_ratio_low: 3.5,
    mb_ratio_mid: 2.5,
    mb_ratio_high: 2.5,
    mb_attack_low: 5.0,
    mb_attack_mid: 3.0,
    mb_release_low: 120.0,
    eq_gains: [0.0, 1.0, 0.0, -0.5, 0.0, 1.0, 1.5, 2.0],
    ms_enabled: true,
    side_gain: 1.5,
    stereo_width: 1.3,
    analog_saturation: true,
    saturation_drive: 0.2,
  },
  hiphop: {
    mb_ratio_low: 4.0,
    mb_ratio_mid: 2.5,
    mb_threshold_low: -15.0,
    mb_attack_low: 3.0,
    mb_release_low: 100.0,
    eq_gains: [1.5, 1.0, 0.0, 0.0, -0.5, 0.5, 1.0, 1.5],
    ms_enabled: true,
    side_gain: 1.0,
    stereo_width: 1.2,
  },
  rock: {
    mb_ratio_low: 3.0,
    mb_ratio_mid: 2.5,
    mb_ratio_high: 2.5,
    mb_attack_mid: 4.0,
    eq_gains: [0.5, 0.0, 0.5, 1.0, 0.0, 0.5, 1.0, 1.5],
    ms_enabled: true,
    side_gain: 2.0,
    stereo_width: 1.2,
    analog_saturation: true,
    saturation_drive: 0.3,
    saturation_mode: 'tube',
  },
  pop: {
    mb_ratio_low: 2.5,
    mb_ratio_mid: 2.0,
    mb_ratio_high: 2.0,
    eq_gains: [0.0, 0.0, 0.5, 0.5, 0.5, 1.0, 1.5, 2.0],
    ms_enabled: true,
    side_gain: 1.5,
    stereo_width: 1.2,
  },
  classical: {
    mb_ratio_low: 1.5,
    mb_ratio_mid: 1.3,
    mb_ratio_high: 1.3,
    mb_threshold_low: -24.0,
    mb_threshold_mid: -22.0,
    mb_threshold_high: -20.0,
    mb_attack_low: 20.0,
    mb_attack_mid: 15.0,
    mb_attack_high: 10.0,
    mb_release_low: 300.0,
    mb_release_mid: 200.0,
    mb_release_high: 150.0,
    eq_gains: [0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.5, 1.0],
    stereo_width: 1.1,
  },
  jazz: {
    mb_ratio_low: 2.0,
    mb_ratio_mid: 1.5,
    mb_ratio_high: 1.5,
    mb_threshold_low: -22.0,
    mb_threshold_mid: -20.0,
    mb_threshold_high: -18.0,
    mb_attack_low: 15.0,
    mb_attack_mid: 10.0,
    mb_release_low: 250.0,
    eq_gains: [0.0, 0.5, 0.0, 0.0, 0.0, 0.5, 1.0, 1.0],
    analog_saturation: true,
    saturation_drive: 0.15,
    saturation_mode: 'tube',
    stereo_width: 1.1,
  },
  default: {}, // Uses base defaults — matches backend exactly
}

/**
 * Platform loudness targets. Must match backend/app/services/platform_targets.py exactly.
 * Maps platform slug to { target_lufs, true_peak_ceiling }.
 *
 * Falls back to spotify defaults (same as backend get_platform_target fallback).
 */
const PLATFORM_TARGETS: Record<string, { target_lufs: number; true_peak_ceiling: number }> = {
  // Tier 1 — Major streaming
  spotify: { target_lufs: -14.0, true_peak_ceiling: -1.0 },
  spotify_loud: { target_lufs: -11.0, true_peak_ceiling: -1.0 },
  apple_music: { target_lufs: -16.0, true_peak_ceiling: -1.0 },
  apple_music_spatial: { target_lufs: -16.0, true_peak_ceiling: -1.0 },
  dolby_atmos: { target_lufs: -18.0, true_peak_ceiling: -1.0 },
  youtube: { target_lufs: -14.0, true_peak_ceiling: -1.0 },
  youtube_music: { target_lufs: -14.0, true_peak_ceiling: -1.0 },
  tidal: { target_lufs: -14.0, true_peak_ceiling: -1.0 },
  amazon_music: { target_lufs: -14.0, true_peak_ceiling: -2.0 },
  amazon_ultra_hd: { target_lufs: -14.0, true_peak_ceiling: -1.0 },

  // Tier 2 — Secondary streaming
  deezer: { target_lufs: -15.0, true_peak_ceiling: -1.0 },
  soundcloud: { target_lufs: -14.0, true_peak_ceiling: -1.0 },
  pandora: { target_lufs: -14.0, true_peak_ceiling: -1.0 },
  tiktok: { target_lufs: -14.0, true_peak_ceiling: -1.0 },
  instagram: { target_lufs: -14.0, true_peak_ceiling: -1.0 },

  // Tier 3 — Physical & broadcast
  cd: { target_lufs: -9.0, true_peak_ceiling: -0.3 },
  vinyl: { target_lufs: -14.0, true_peak_ceiling: -1.0 },
  broadcast_ebu: { target_lufs: -23.0, true_peak_ceiling: -1.0 },
  broadcast_atsc: { target_lufs: -24.0, true_peak_ceiling: -2.0 },

  // Tier 4 — Specialty
  audiobook_acx: { target_lufs: -20.0, true_peak_ceiling: -3.0 },
  podcast: { target_lufs: -16.0, true_peak_ceiling: -1.0 },
  game_audio: { target_lufs: -18.0, true_peak_ceiling: -1.0 },

  // Tier 5 — Niche/regional
  qobuz: { target_lufs: -14.0, true_peak_ceiling: -1.0 },
  anghami: { target_lufs: -14.0, true_peak_ceiling: -1.0 },
  jiosaavn: { target_lufs: -14.0, true_peak_ceiling: -1.0 },
  boomplay: { target_lufs: -14.0, true_peak_ceiling: -1.0 },
  netease: { target_lufs: -14.0, true_peak_ceiling: -1.0 },
}

/** Fallback platform target (spotify) — matches backend get_platform_target fallback. */
const DEFAULT_PLATFORM = PLATFORM_TARGETS.spotify ?? { target_lufs: -14.0, true_peak_ceiling: -1.0 }

/**
 * Generate a deterministic ProcessingParams from (genre, platform).
 *
 * This is the MANDATORY fallback when RAIN_NORMALIZATION_VALIDATED=false.
 * Output is deterministic: same inputs always produce identical output.
 *
 * Logic order (matches backend generate_heuristic_params exactly):
 *   1. Start with default params
 *   2. Apply platform target (target_lufs + true_peak_ceiling)
 *   3. Apply vinyl override if platform === 'vinyl'
 *   4. Apply genre overrides (can overwrite any field)
 */
export function generateHeuristicParams(
  genre: string,
  platform: string,
): ProcessingParams {
  const params = defaultParams()

  // Apply platform target
  const target = PLATFORM_TARGETS[platform] ?? DEFAULT_PLATFORM
  params.target_lufs = target.target_lufs
  params.true_peak_ceiling = target.true_peak_ceiling

  // Vinyl mode
  if (platform === 'vinyl') {
    params.vinyl_mode = true
    params.true_peak_ceiling = -3.0
  }

  // Apply genre overrides
  const overrides = GENRE_OVERRIDES[genre] ?? GENRE_OVERRIDES.default
  Object.assign(params, overrides)

  return params
}
