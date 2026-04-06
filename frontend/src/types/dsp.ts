/**
 * Canonical ProcessingParams — 46-field schema per RAIN-BUILD-SPEC-v6.0.
 *
 * RainNet v2 outputs 46 values:
 *   Indices 0-38  = DSP parameters (loudness, dynamics, EQ, saturation, M/S, SAIL, vinyl)
 *   Indices 39-45 = 7 macro controls (sigmoid×10 → [0.0, 10.0])
 *
 * ENFORCEMENT RULES:
 * - Field name `eq_gains` is canonical. NEVER use eq_bands, eq_curve, or eq.
 * - Field name `target_lufs` is canonical. NEVER use lufs_target, loudness, or lufs.
 * - ALL fields MUST be present. No optional fields. No extra fields.
 * - `eq_gains` is exactly 8 elements.
 * - `sail_stem_gains` is exactly 12 elements (12-stem era — SAIL v2).
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
  eq_gains: [number, number, number, number, number, number, number, number];

  // Analog saturation
  analog_saturation: boolean;  // Enable/disable. Default: false
  saturation_drive: number;    // 0.0–1.0. Default: 0.0 (bypass)
  saturation_mode: 'tape' | 'tube' | 'transistor'; // Default: "tape"

  // Mid/Side processing
  ms_enabled: boolean;         // Default: false
  mid_gain: number;            // dB. Default: 0.0. Range: [-6.0, +6.0]
  side_gain: number;           // dB. Default: 0.0. Range: [-6.0, +6.0]
  stereo_width: number;        // 0.0–2.0. Default: 1.0 (no change)

  // SAIL v2 (Stem-Aware Intelligent Limiting — 12-stem)
  sail_enabled: boolean;       // Default: false
  sail_stem_gains: [number, number, number, number, number, number, number, number, number, number, number, number]; // 12-stem dB

  // Vinyl mode
  vinyl_mode: boolean;         // Default: false. Enables RIAA + SAIL vinyl chain

  // 7 Macro controls (RainNet v2 indices 39-45, sigmoid×10 → [0.0, 10.0])
  macro_brighten: number;      // 0.0-10.0 — high-frequency presence, air, sparkle
  macro_glue: number;          // 0.0-10.0 — bus compression, cohesion
  macro_width: number;         // 0.0-10.0 — stereo width, spatial spread
  macro_punch: number;         // 0.0-10.0 — transient emphasis, impact
  macro_warmth: number;        // 0.0-10.0 — harmonic saturation, analog tone
  macro_space: number;         // 0.0-10.0 — spatial depth, immersive quality
  macro_repair: number;        // 0.0-10.0 — spectral repair intensity
}

/**
 * Default ProcessingParams with all 46 fields set to their canonical defaults.
 */
export const DEFAULT_PROCESSING_PARAMS: Readonly<ProcessingParams> = {
  target_lufs: -14.0,
  true_peak_ceiling: -1.0,
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
  eq_gains: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
  analog_saturation: false,
  saturation_drive: 0.0,
  saturation_mode: 'tape',
  ms_enabled: false,
  mid_gain: 0.0,
  side_gain: 0.0,
  stereo_width: 1.0,
  sail_enabled: false,
  sail_stem_gains: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
  vinyl_mode: false,
  macro_brighten: 5.0,
  macro_glue: 4.2,
  macro_width: 3.8,
  macro_punch: 6.1,
  macro_warmth: 5.5,
  macro_space: 3.0,
  macro_repair: 0.0,
} as const;

/** Saturation mode string union extracted from ProcessingParams. */
export type SaturationMode = ProcessingParams['saturation_mode'];

/** Names of the 7 macros for iteration. */
export const MACRO_NAMES = [
  'macro_brighten', 'macro_glue', 'macro_width', 'macro_punch',
  'macro_warmth', 'macro_space', 'macro_repair',
] as const;
export type MacroName = typeof MACRO_NAMES[number];
