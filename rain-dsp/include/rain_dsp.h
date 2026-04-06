#pragma once
#include <cstdint>
#include <cstddef>
#include <array>
#include <vector>
#include <span>
#include <string>

namespace rain {

// Version
constexpr const char* VERSION = "6.0.0";
constexpr int VERSION_MAJOR = 6;
constexpr int VERSION_MINOR = 0;
constexpr int VERSION_PATCH = 0;

// Constants
constexpr double LUFS_TARGET_SPOTIFY   = -14.0;
constexpr double LUFS_TARGET_APPLE     = -16.0;
constexpr double LUFS_TARGET_YOUTUBE   = -14.0;
constexpr double LUFS_TARGET_TIDAL     = -14.0;
constexpr double LUFS_TARGET_DEFAULT   = -14.0;
constexpr double TRUE_PEAK_MAX         = -1.0;   // dBTP
constexpr double TRUE_PEAK_VINYL       = -3.0;   // dBTP for vinyl cut

// Biquad filter (canonical sign convention — IMMUTABLE)
// y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]
// a1 is stored as given and SUBTRACTED. Never change this sign.
struct BiquadCoefficients {
    double b0, b1, b2;
    double a1, a2;  // subtracted in filter loop
};

struct BiquadState {
    double x1 = 0.0, x2 = 0.0;
    double y1 = 0.0, y2 = 0.0;
};

// K-weighting filter coefficients at 48 kHz (ITU-R BS.1770-4)
// Stage 1a: high-shelf pre-filter
constexpr BiquadCoefficients K_WEIGHT_STAGE1A_48K = {
     1.53512485958697,
    -2.69169618940638,
     1.19839281085285,
    -1.69065929318241,  // subtracted
     0.73248077421585
};

// Stage 1b: high-pass filter
constexpr BiquadCoefficients K_WEIGHT_STAGE1B_48K = {
     1.0,
    -2.0,
     1.0,
    -1.99004745483398,  // subtracted
     0.99007225036289
};

// Processing parameters (output of RainNet inference)
struct ProcessingParams {
    // Multiband dynamics
    double mb_threshold_low  = -18.0;
    double mb_threshold_mid  = -18.0;
    double mb_threshold_high = -18.0;
    double mb_ratio_low      = 2.5;
    double mb_ratio_mid      = 2.0;
    double mb_ratio_high     = 2.0;
    double mb_attack_low     = 10.0;   // ms
    double mb_attack_mid     = 5.0;
    double mb_attack_high    = 2.0;
    double mb_release_low    = 150.0;  // ms
    double mb_release_mid    = 80.0;
    double mb_release_high   = 40.0;

    // Linear-phase EQ (8 bands)
    std::array<double, 8> eq_frequencies = {60,120,250,500,1000,4000,8000,16000};
    std::array<double, 8> eq_gains       = {0,0,0,0,0,0,0,0};  // dB

    // Saturation
    bool analog_saturation  = false;
    double saturation_drive = 0.0;               // 0.0 - 1.0
    std::string saturation_mode = "tape";        // "tape" | "transistor" | "tube"

    // M/S
    bool ms_enabled       = false;
    double mid_gain       = 0.0;    // dB
    double side_gain      = 0.0;    // dB
    double stereo_width   = 1.0;    // 0.0-2.0

    // Output
    double target_lufs       = -14.0;
    double true_peak_ceiling = -1.0;  // dBTP
    bool vinyl_mode          = false;

    // SAIL
    bool sail_enabled = false;
    std::array<double, 12> sail_stem_gains = {0,0,0,0,0,0,0,0,0,0,0,0};  // 12-stem SAIL v2
};

// LUFS measurement result (ITU-R BS.1770-4)
struct LufsResult {
    double integrated;       // LUFS-I
    double short_term;       // LUFS-S (last 3s)
    double momentary;        // LUFS-M (last 400ms)
    double loudness_range;   // LRA (dB)
    double true_peak_dbtp;   // dBTP
};

// Main processing entry point
// Returns 0 on success, non-zero RAIN-E* code on error
int rain_process(
    const double* input_left,
    const double* input_right,
    double* output_left,
    double* output_right,
    size_t num_samples,
    double sample_rate,
    const ProcessingParams& params,
    LufsResult* result_out
);

// Measurement only (no processing)
LufsResult rain_measure_lufs(
    const double* left,
    const double* right,
    size_t num_samples,
    double sample_rate
);

// Inline biquad computation (hot path)
[[nodiscard]] inline double biquad_tick(
    const BiquadCoefficients& c,
    BiquadState& s,
    double x) noexcept
{
    const double y = c.b0 * x
                   + c.b1 * s.x1
                   + c.b2 * s.x2
                   - c.a1 * s.y1
                   - c.a2 * s.y2;
    s.x2 = s.x1; s.x1 = x;
    s.y2 = s.y1; s.y1 = y;
    return y;
}

} // namespace rain
