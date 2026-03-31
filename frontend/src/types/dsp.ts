/**
 * Canonical ProcessingParams — 1:1 mapping of CLAUDE.md §Canonical ProcessingParams Schema.
 *
 * ENFORCEMENT RULES:
 * - Field name `eq_gains` is canonical. NEVER use eq_bands, eq_curve, or eq.
 * - Field name `target_lufs` is canonical. NEVER use lufs_target, loudness, or lufs.
 * - ALL fields MUST be present. No optional fields. No extra fields.
 * - `eq_gains` is exactly 8 elements.
 * - `sail_stem_gains` is exactly 6 elements.
 */
export interface ProcessingParams {
  // Loudness target
  target_lufs: number;         // Platform-dependent. Default: -14.0. Range: [-24.0, -8.0]
  true_peak_ceiling: number;   // dBTP. Default: -1.0. Vinyl: -3.0. Range: [-6.0, 0.0]

  // Multiband dynamics (3-band: low/mid/high)
  mb_threshold_low: number;    // dB. Range: [-40.0, 0.0]
  mb_threshold_mid: number;    // dB. Range: [-40.0, 0.0]
  mb_threshold_high: number;   // dB. Range: [-40.0, 0.0]
  mb_ratio_low: number;        // Compression ratio. Default: 2.5. Range: [1.0, 20.0]
  mb_ratio_mid: number;        // Default: 2.0. Range: [1.0, 20.0]
  mb_ratio_high: number;       // Default: 2.0. Range: [1.0, 20.0]
  mb_attack_low: number;       // ms. Default: 10.0
  mb_attack_mid: number;       // ms. Default: 5.0
  mb_attack_high: number;      // ms. Default: 2.0
  mb_release_low: number;      // ms. Default: 150.0
  mb_release_mid: number;      // ms. Default: 80.0
  mb_release_high: number;     // ms. Default: 40.0

  // EQ (8-band parametric)
  eq_gains: [number, number, number, number, number, number, number, number]; // dB per band. Default: [0]*8. Range per band: [-12.0, +12.0]

  // Analog saturation
  analog_saturation: boolean;  // Enable/disable. Default: false
  saturation_drive: number;    // 0.0–1.0. Default: 0.0 (bypass)
  saturation_mode: 'tape' | 'tube' | 'transistor'; // Default: "tape"

  // Mid/Side processing
  ms_enabled: boolean;         // Default: false
  mid_gain: number;            // dB. Default: 0.0. Range: [-6.0, +6.0]
  side_gain: number;           // dB. Default: 0.0. Range: [-6.0, +6.0]
  stereo_width: number;        // 0.0–2.0. Default: 1.0 (no change)

  // SAIL (Stem-Aware Intelligent Limiting)
  sail_enabled: boolean;       // Default: false
  sail_stem_gains: [number, number, number, number, number, number]; // Per-stem gain adjustments. Default: [0]*6

  // Vinyl mode
  vinyl_mode: boolean;         // Default: false. Enables RIAA + SAIL vinyl chain
}

/**
 * Default ProcessingParams with all fields set to their canonical defaults.
 * Use this as the starting point for any new session or heuristic fallback.
 */
export const DEFAULT_PROCESSING_PARAMS: Readonly<ProcessingParams> = {
  // Loudness target
  target_lufs: -14.0,
  true_peak_ceiling: -1.0,

  // Multiband dynamics
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

  // SAIL
  sail_enabled: false,
  sail_stem_gains: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],

  // Vinyl mode
  vinyl_mode: false,
} as const;

/** Saturation mode string union extracted from ProcessingParams. */
export type SaturationMode = ProcessingParams['saturation_mode'];
