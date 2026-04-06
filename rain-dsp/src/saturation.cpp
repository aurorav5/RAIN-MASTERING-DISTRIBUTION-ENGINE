// Analog saturation with 4x oversampling
// Models: tape, transistor, tube
// 4x oversampling with 48-tap Kaiser FIR anti-aliasing filter
// FIR: β=6.0, fc=0.25 (= 0.5/L, L=4 — passband up to original Nyquist)
// All arithmetic in 64-bit double.

#include "rain_dsp.h"
#include "saturation.h"
#include <cmath>
#include <vector>
#include <cstring>
#include <algorithm>

namespace rain {

namespace {

// 48-tap Kaiser-windowed FIR for anti-aliasing in 4x oversampling.
// Design: β=6.0, fc=0.25 (= original Nyquist / upsampled Nyquist), sum=1.
// These same coefficients are used in true_peak.cpp.
// For saturation upsampling: multiply output by L=4 to compensate for zero insertion gain.
// For saturation downsampling: apply FIR, take every 4th sample (no *L needed).
constexpr int SAT_FIR_LEN = 48;
constexpr int SAT_OVERSAMPLE = 4;

constexpr double SAT_FIR[SAT_FIR_LEN] = {
    -0.0000771038953, -0.0003698666331, -0.0006308766877, -0.0004088112424,
    +0.0006039221411, +0.0020661579336, +0.0028361620288, +0.0015722527929,
    -0.0020613128811, -0.0064147201433, -0.0081538555294, -0.0042444002233,
    +0.0052858750631, +0.0157861521765, +0.0194451702151, +0.0099069034299,
    -0.0122093604085, -0.0365626384544, -0.0459425865717, -0.0244664503790,
    +0.0327466900364, +0.1140470851401, +0.1938977220016, +0.2433478900902,
    +0.2433478900902, +0.1938977220016, +0.1140470851401, +0.0327466900364,
    -0.0244664503790, -0.0459425865717, -0.0365626384544, -0.0122093604085,
    +0.0099069034299, +0.0194451702151, +0.0157861521765, +0.0052858750631,
    -0.0042444002233, -0.0081538555294, -0.0064147201433, -0.0020613128811,
    +0.0015722527929, +0.0028361620288, +0.0020661579336, +0.0006039221411,
    -0.0004088112424, -0.0006308766877, -0.0003698666331, -0.0000771038953
};

// Apply FIR to a single sample given a running history buffer.
// history[0] = most recent sample, history[SAT_FIR_LEN-1] = oldest.
// Updates history in-place.
inline double apply_fir_with_history(double* history, double new_sample) {
    // Shift history
    for (int i = SAT_FIR_LEN - 1; i > 0; --i) {
        history[i] = history[i - 1];
    }
    history[0] = new_sample;

    double sum = 0.0;
    for (int i = 0; i < SAT_FIR_LEN; ++i) {
        sum += SAT_FIR[i] * history[i];
    }
    return sum;
}

// Tape saturation: y = tanh(drive * 2 * x) / tanh(drive * 2)
inline double sat_tape(double x, double drive) {
    if (drive < 1e-9) return x;
    double d = drive * 2.0;
    double denom = std::tanh(d);
    if (std::abs(denom) < 1e-30) return x;
    return std::tanh(d * x) / denom;
}

// Transistor saturation: asymmetric
// positive: tanh(drive * 3 * x)
// negative: -atan(drive * 2 * (-x)) * (2/pi)
inline double sat_transistor(double x, double drive) {
    if (drive < 1e-9) return x;
    if (x >= 0.0) {
        return std::tanh(drive * 3.0 * x);
    } else {
        return -(std::atan(drive * 2.0 * (-x)) * (2.0 / M_PI));
    }
}

// Tube saturation: y = x / (1 + drive * |x|)
inline double sat_tube(double x, double drive) {
    if (drive < 1e-9) return x;
    return x / (1.0 + drive * std::abs(x));
}

// Process one channel with 4x oversampling saturation
void saturate_channel(
    double* samples,
    size_t n,
    double drive,
    const std::string& mode)
{
    if (drive < 1e-9) return;

    // Upsampling FIR history (for interpolation)
    double up_hist[SAT_FIR_LEN] = {};
    // Downsampling FIR history (for anti-aliasing)
    double dn_hist[SAT_FIR_LEN] = {};

    for (size_t i = 0; i < n; ++i) {
        double xin = samples[i];

        // Upsample by SAT_OVERSAMPLE: insert L-1 zeros between samples.
        // Each upsampled sample passes through the anti-imaging FIR.
        // Multiply input by L to maintain amplitude (compensate for energy spread).
        double sat_out[SAT_OVERSAMPLE];

        for (int p = 0; p < SAT_OVERSAMPLE; ++p) {
            // p=0: original sample (scaled by L for interpolation gain)
            // p>0: zero inserted between samples
            double x_up = (p == 0) ? xin * static_cast<double>(SAT_OVERSAMPLE) : 0.0;

            // Apply interpolation FIR
            double filtered = apply_fir_with_history(up_hist, x_up);

            // Apply nonlinear saturation
            double saturated;
            if (mode == "tape") {
                saturated = sat_tape(filtered, drive);
            } else if (mode == "transistor") {
                saturated = sat_transistor(filtered, drive);
            } else if (mode == "tube") {
                saturated = sat_tube(filtered, drive);
            } else {
                // Default: tape
                saturated = sat_tape(filtered, drive);
            }

            sat_out[p] = saturated;
        }

        // Downsample by SAT_OVERSAMPLE:
        // Apply anti-aliasing FIR to all upsampled samples.
        // Take the output at the last phase (p = SAT_OVERSAMPLE - 1) as the output sample.
        double y = 0.0;
        for (int p = 0; p < SAT_OVERSAMPLE; ++p) {
            double filtered = apply_fir_with_history(dn_hist, sat_out[p]);
            if (p == SAT_OVERSAMPLE - 1) {
                y = filtered;
            }
        }

        samples[i] = y;
    }
}

} // anonymous namespace

void apply_saturation(
    double* left,
    double* right,
    size_t num_samples,
    const ProcessingParams& params)
{
    if (!params.analog_saturation) return;
    if (num_samples == 0) return;

    double drive = params.saturation_drive;
    if (drive < 1e-9) return;  // drive=0 → bypass

    const std::string& mode = params.saturation_mode;

    saturate_channel(left,  num_samples, drive, mode);
    saturate_channel(right, num_samples, drive, mode);
}

} // namespace rain
