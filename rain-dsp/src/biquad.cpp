// biquad.cpp — Biquad filter implementation (Direct Form II Transposed)
// 64-bit double precision throughout. No float32.
//
// Sign convention (IMMUTABLE — from CLAUDE.md):
//   y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] − a1*y[n-1] − a2*y[n-2]
//   a1 is stored NEGATIVE and SUBTRACTED. Using +a1*y1 is WRONG.
//
// DF2T recurrence:
//   output = b0 * input + s1
//   s1     = b1 * input - a1 * output + s2
//   s2     = b2 * input - a2 * output

#include "rain/biquad.h"

namespace rain {

void Biquad::setCoefficients(const Coefficients& coeffs) {
    coeffs_ = coeffs;
    reset();
}

double Biquad::process(double input) noexcept {
    const double output = coeffs_.b0 * input + s1_;
    s1_ = coeffs_.b1 * input - coeffs_.a1 * output + s2_;
    s2_ = coeffs_.b2 * input - coeffs_.a2 * output;
    return output;
}

void Biquad::processBlock(double* buffer, size_t numSamples) noexcept {
    // Local copies of state for the hot loop — avoids repeated member access
    double s1 = s1_;
    double s2 = s2_;
    const double b0 = coeffs_.b0;
    const double b1 = coeffs_.b1;
    const double b2 = coeffs_.b2;
    const double a1 = coeffs_.a1;
    const double a2 = coeffs_.a2;

    for (size_t i = 0; i < numSamples; ++i) {
        const double input  = buffer[i];
        const double output = b0 * input + s1;
        s1 = b1 * input - a1 * output + s2;
        s2 = b2 * input - a2 * output;
        buffer[i] = output;
    }

    // Write state back
    s1_ = s1;
    s2_ = s2;
}

void Biquad::reset() noexcept {
    s1_ = 0.0;
    s2_ = 0.0;
}

} // namespace rain
