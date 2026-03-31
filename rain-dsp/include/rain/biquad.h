#pragma once
// rain/biquad.h — Standalone biquad filter (Direct Form II Transposed)
// All arithmetic in 64-bit double. No float32 anywhere.
//
// Sign convention (IMMUTABLE — from CLAUDE.md):
//   y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] − a1*y[n-1] − a2*y[n-2]
//   a1, a2 are stored NEGATIVE and SUBTRACTED in the recurrence.
//
// DF2T form:
//   output = b0 * input + s1
//   s1     = b1 * input - a1 * output + s2
//   s2     = b2 * input - a2 * output

#include <cmath>
#include <cstddef>

namespace rain {

class Biquad {
public:
    struct Coefficients {
        double b0{0.0};
        double b1{0.0};
        double b2{0.0};
        double a1{0.0};  // Stored NEGATIVE, SUBTRACTED in recurrence
        double a2{0.0};  // Stored NEGATIVE, SUBTRACTED in recurrence
    };

    /// Set filter coefficients. Resets internal state.
    void setCoefficients(const Coefficients& coeffs);

    /// Process a single sample through the filter.
    [[nodiscard]] double process(double input) noexcept;

    /// Process a contiguous block of samples in-place.
    void processBlock(double* buffer, size_t numSamples) noexcept;

    /// Reset filter state (delay elements) to zero.
    void reset() noexcept;

    /// Read-only access to current coefficients.
    [[nodiscard]] const Coefficients& coefficients() const noexcept { return coeffs_; }

private:
    Coefficients coeffs_{};
    double s1_{0.0};  // DF2T state variable 1
    double s2_{0.0};  // DF2T state variable 2
};

} // namespace rain
