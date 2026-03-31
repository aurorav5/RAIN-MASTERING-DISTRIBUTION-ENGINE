#pragma once
// SAIL Limiter — Stem-Aware Intelligent Limiting
// Part of RainDSP v6.0.0
// All arithmetic in 64-bit double precision.

#include "../rain_dsp.h"
#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace rain {

// -------------------------------------------------------------------------
// Maximum number of stems supported (Demucs v4 htdemucs_6s multi-pass = 12)
// -------------------------------------------------------------------------
static constexpr size_t MAX_STEMS = 12;

// -------------------------------------------------------------------------
// Limiter operating mode
// -------------------------------------------------------------------------
enum class LimiterMode : uint8_t {
    Transparent,  // Minimal coloration, gentle GR
    Punchy,       // Fast attack on transients, aggressive recovery
    Dense,        // High sustained compression, wall-of-sound
    Broadcast,    // Strict EBU R128 compliance, moderate density
    Vinyl         // RIAA-aware ceiling, extra headroom (-3 dBTP)
};

// -------------------------------------------------------------------------
// Per-stem envelope data fed from the separation/analysis stage
// -------------------------------------------------------------------------
struct StemEnvelope {
    std::string stemType;         // e.g. "vocals", "drums", "bass", "guitar", "piano", "other"
    int         priority    = 5;  // 1 (highest) to 10 (lowest)
    double      weight      = 1.0; // 0.0 – 1.0, mix contribution weight
    double      confidence  = 0.0; // 0.0 – 1.0, separation confidence
    double      currentLevel = 0.0; // Current RMS level (linear)
    double      transientRatio = 0.0; // 0.0 – 1.0, ratio of transient energy
    bool        isVocal     = false; // True for vocal stems (enables protection)
};

// -------------------------------------------------------------------------
// SAIL configuration
// -------------------------------------------------------------------------
struct SAILConfig {
    LimiterMode mode                = LimiterMode::Transparent;
    double      ceilingDBTP         = -1.0;  // dBTP true-peak ceiling
    double      releaseMs           = 50.0;  // Release time in ms
    double      lookaheadMs         = 5.0;   // Lookahead in ms
    bool        stemAwareEnabled    = true;   // Enable stem-aware GR allocation
    bool        psychoacousticRelease = false; // Program-dependent release
};

// -------------------------------------------------------------------------
// Result of a processBlock() call
// -------------------------------------------------------------------------
struct ProcessResult {
    double      peakGR           = 0.0;  // Peak gain reduction in dB (negative)
    double      avgGR            = 0.0;  // Average gain reduction in dB (negative)
    bool        stemAwareActive  = false; // True if stem-aware allocation was used
    std::string fallbackReason;           // Non-empty if fell back to conventional
};

// -------------------------------------------------------------------------
// Per-stem gain allocation (returned by getStemGainAllocation)
// -------------------------------------------------------------------------
struct StemGainAllocation {
    std::string stemType;
    double      gainReductionDB = 0.0;   // GR assigned to this stem (negative)
    double      allocationScore = 0.0;   // Score used for sorting
};

// -------------------------------------------------------------------------
// SAILLimiter — Stem-Aware Intelligent Limiter
// -------------------------------------------------------------------------
class SAILLimiter {
public:
    SAILLimiter() = default;
    ~SAILLimiter() = default;

    // Non-copyable, movable
    SAILLimiter(const SAILLimiter&) = delete;
    SAILLimiter& operator=(const SAILLimiter&) = delete;
    SAILLimiter(SAILLimiter&&) = default;
    SAILLimiter& operator=(SAILLimiter&&) = default;

    // ---- Configuration ----

    /// Set the limiter configuration. Must be called before processBlock().
    void setConfig(const SAILConfig& config);

    /// Set stem envelopes from separation analysis. Up to MAX_STEMS envelopes.
    /// If empty or all confidences < 0.3, stem-aware mode is disabled.
    void setStemEnvelopes(const std::vector<StemEnvelope>& envelopes);

    // ---- Processing ----

    /// Process a block of interleaved stereo audio (in-place).
    /// left/right: pointers to sample buffers, numSamples each.
    /// sampleRate: in Hz.
    /// sailStemGains: the 6-element per-stem gain array from ProcessingParams.
    /// Returns a ProcessResult with GR statistics.
    ProcessResult processBlock(
        double* left,
        double* right,
        size_t numSamples,
        double sampleRate,
        const std::array<double, 6>& sailStemGains
    );

    // ---- Query ----

    /// Get the per-stem gain allocation from the last processBlock() call.
    [[nodiscard]] std::vector<StemGainAllocation> getStemGainAllocation() const;

    /// Get the output true peak in dBTP from the last processBlock() call.
    [[nodiscard]] double getOutputTruePeakDBTP() const;

private:
    // ---- Internal methods ----

    /// Allocate gain reduction across stems proportionally, with vocal protection.
    /// totalGR_dB: total required gain reduction in dB (negative).
    void allocateGainReduction(double totalGR_dB);

    /// Compute the required gain reduction for a single sample.
    /// envelope: current envelope level (linear).
    /// Returns required gain (linear, <= 1.0).
    [[nodiscard]] double computeGainReduction(double envelope) const;

    /// Enforce true-peak ceiling on the output buffer using oversampled peak detection.
    void enforceTruePeakCeiling(double* left, double* right, size_t numSamples, double sampleRate);

    /// Conventional wideband limiting (no stem awareness).
    ProcessResult processConventional(
        double* left,
        double* right,
        size_t numSamples,
        double sampleRate
    );

    // ---- Mode-dependent parameters ----
    struct ModeParams {
        double attackMs   = 1.0;
        double releaseMs  = 50.0;
        double kneeDB     = 0.0;  // Soft knee width
    };
    [[nodiscard]] ModeParams getModeParams() const;

    // ---- State ----
    SAILConfig                          m_config;
    std::vector<StemEnvelope>           m_stemEnvelopes;
    std::vector<StemGainAllocation>     m_lastAllocations;
    double                              m_outputTruePeakDBTP = -std::numeric_limits<double>::infinity();

    // Envelope follower state (persists across blocks)
    double m_envelope   = 0.0;
    double m_gainSmooth = 1.0;

    // Lookahead delay buffers
    std::vector<double> m_delayL;
    std::vector<double> m_delayR;
    int                 m_delayPos      = 0;
    int                 m_lookaheadSamples = 0;
    double              m_lastSampleRate = 0.0;

    // True-peak ceiling (linear)
    double m_ceilingLinear = 0.0;

    // Track whether stem-aware was active on last block
    bool m_stemAwareWasActive = false;
};

} // namespace rain
