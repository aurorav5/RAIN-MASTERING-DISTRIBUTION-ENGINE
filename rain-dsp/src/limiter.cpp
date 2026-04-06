// SAIL Limiter — Stem-Aware Intelligent Limiting
// Part of RainDSP v6.0.0
// All arithmetic in 64-bit double precision. No float32 anywhere.
//
// Architecture:
//   1. Lookahead envelope detection (configurable, default 5ms)
//   2. Gain reduction computation per mode (Transparent/Punchy/Dense/Broadcast/Vinyl)
//   3. Stem-aware GR allocation (vocal protection: max 30% of proportional share)
//   4. True-peak ceiling enforcement via oversampled peak detection
//   5. Fallback to conventional wideband limiting when stem confidence < 0.3

#include "rain/limiter.h"
#include "true_peak.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <numeric>

namespace rain {

// =========================================================================
// Configuration
// =========================================================================

void SAILLimiter::setConfig(const SAILConfig& config) {
    m_config = config;
    m_ceilingLinear = std::pow(10.0, m_config.ceilingDBTP / 20.0);
}

void SAILLimiter::setStemEnvelopes(const std::vector<StemEnvelope>& envelopes) {
    if (envelopes.size() > MAX_STEMS) {
        m_stemEnvelopes.assign(envelopes.begin(), envelopes.begin() + MAX_STEMS);
    } else {
        m_stemEnvelopes = envelopes;
    }
}

// =========================================================================
// Mode-dependent parameters
// =========================================================================

SAILLimiter::ModeParams SAILLimiter::getModeParams() const {
    ModeParams p;
    switch (m_config.mode) {
        case LimiterMode::Transparent:
            p.attackMs  = 2.0;
            p.releaseMs = m_config.releaseMs;  // default 50ms
            p.kneeDB    = 3.0;                 // gentle soft knee
            break;
        case LimiterMode::Punchy:
            p.attackMs  = 0.5;
            p.releaseMs = m_config.releaseMs * 0.6;  // faster recovery
            p.kneeDB    = 1.0;
            break;
        case LimiterMode::Dense:
            p.attackMs  = 0.1;
            p.releaseMs = m_config.releaseMs * 2.0;  // slow release for sustained density
            p.kneeDB    = 6.0;                       // wide soft knee
            break;
        case LimiterMode::Broadcast:
            p.attackMs  = 1.0;
            p.releaseMs = m_config.releaseMs;
            p.kneeDB    = 2.0;
            break;
        case LimiterMode::Vinyl:
            p.attackMs  = 1.5;
            p.releaseMs = m_config.releaseMs * 1.2;
            p.kneeDB    = 2.0;
            break;
    }
    return p;
}

// =========================================================================
// Gain reduction computation
// =========================================================================

double SAILLimiter::computeGainReduction(double envelope) const {
    if (envelope < 1e-30) {
        return 1.0;
    }

    const double envelopeDB = 20.0 * std::log10(envelope);
    const double ceilingDB  = m_config.ceilingDBTP;
    const ModeParams mp     = getModeParams();
    const double kneeDB     = mp.kneeDB;

    double overDB = envelopeDB - ceilingDB;

    if (overDB <= -kneeDB / 2.0) {
        // Below threshold: no gain reduction
        return 1.0;
    }

    double grDB = 0.0;
    if (kneeDB > 0.0 && overDB < kneeDB / 2.0) {
        // Soft knee region: quadratic interpolation
        double x = overDB + kneeDB / 2.0;
        grDB = -(x * x) / (2.0 * kneeDB);
    } else {
        // Above knee: full limiting (1:inf ratio)
        grDB = -overDB;
    }

    // Convert to linear gain
    double gainLinear = std::pow(10.0, grDB / 20.0);
    if (gainLinear > 1.0) gainLinear = 1.0;

    return gainLinear;
}

// =========================================================================
// Stem-aware gain reduction allocation
// =========================================================================

void SAILLimiter::allocateGainReduction(double totalGR_dB) {
    m_lastAllocations.clear();

    if (m_stemEnvelopes.empty() || totalGR_dB >= 0.0) {
        return;
    }

    // Compute allocation scores for each stem:
    // score = (1 - transientRatio) * (1 - priority/10) * confidence * weight
    // Higher score = absorbs more GR (less important / more expendable stems)
    struct ScoredStem {
        size_t index;
        double score;
        bool   isVocal;
    };

    std::vector<ScoredStem> scored;
    scored.reserve(m_stemEnvelopes.size());

    for (size_t i = 0; i < m_stemEnvelopes.size(); ++i) {
        const auto& env = m_stemEnvelopes[i];
        double score = (1.0 - env.transientRatio)
                     * (1.0 - static_cast<double>(env.priority) / 10.0)
                     * env.confidence
                     * env.weight;
        scored.push_back({i, std::max(score, 0.0), env.isVocal});
    }

    // Sort by score descending (highest score absorbs most GR)
    std::sort(scored.begin(), scored.end(),
              [](const ScoredStem& a, const ScoredStem& b) {
                  return a.score > b.score;
              });

    // Compute total score for proportional distribution
    double totalScore = 0.0;
    for (const auto& s : scored) {
        totalScore += s.score;
    }

    if (totalScore < 1e-30) {
        // All scores zero: distribute evenly
        double perStem = totalGR_dB / static_cast<double>(scored.size());
        for (const auto& s : scored) {
            StemGainAllocation alloc;
            alloc.stemType        = m_stemEnvelopes[s.index].stemType;
            alloc.allocationScore = s.score;
            alloc.gainReductionDB = perStem;
            m_lastAllocations.push_back(std::move(alloc));
        }
        return;
    }

    // Phase 1: Compute proportional shares
    // totalGR_dB is negative. Each stem gets a negative share proportional to its score.
    std::vector<double> grShares(scored.size(), 0.0);
    for (size_t i = 0; i < scored.size(); ++i) {
        grShares[i] = totalGR_dB * (scored[i].score / totalScore);
    }

    // Phase 2: Enforce vocal protection cap (max 30% of proportional share)
    // Vocal stems that would receive more than 30% of their proportional share
    // have their GR capped, and the excess is redistributed to non-vocal stems.
    double excessGR = 0.0;
    double nonVocalScore = 0.0;

    for (size_t i = 0; i < scored.size(); ++i) {
        if (scored[i].isVocal) {
            // Proportional share is grShares[i] (negative).
            // Cap at 30% of that share (i.e., less GR for vocals).
            double maxVocalGR = grShares[i] * 0.3;
            if (grShares[i] < maxVocalGR) {
                // grShares[i] is more negative than the cap
                excessGR += (grShares[i] - maxVocalGR);  // negative excess
                grShares[i] = maxVocalGR;
            }
        } else {
            nonVocalScore += scored[i].score;
        }
    }

    // Redistribute excess GR to non-vocal stems proportionally
    if (excessGR < -1e-30 && nonVocalScore > 1e-30) {
        for (size_t i = 0; i < scored.size(); ++i) {
            if (!scored[i].isVocal) {
                grShares[i] += excessGR * (scored[i].score / nonVocalScore);
            }
        }
    } else if (excessGR < -1e-30) {
        // No non-vocal stems: distribute excess evenly across all stems
        double perStem = excessGR / static_cast<double>(scored.size());
        for (size_t i = 0; i < scored.size(); ++i) {
            grShares[i] += perStem;
        }
    }

    // Build allocation results
    for (size_t i = 0; i < scored.size(); ++i) {
        StemGainAllocation alloc;
        alloc.stemType        = m_stemEnvelopes[scored[i].index].stemType;
        alloc.allocationScore = scored[i].score;
        alloc.gainReductionDB = grShares[i];
        m_lastAllocations.push_back(std::move(alloc));
    }
}

// =========================================================================
// True-peak ceiling enforcement
// =========================================================================

void SAILLimiter::enforceTruePeakCeiling(
    double* left, double* right, size_t numSamples, double sampleRate)
{
    // Measure the current true peak
    double tpDBTP = rain_measure_true_peak(left, right, numSamples, sampleRate);

    if (tpDBTP > m_config.ceilingDBTP) {
        // Need to attenuate to bring true peak under ceiling
        double overshootDB = tpDBTP - m_config.ceilingDBTP;
        // Add a small safety margin (0.1 dB) to ensure we stay under
        double attenuationDB = overshootDB + 0.1;
        double attenuationLinear = std::pow(10.0, -attenuationDB / 20.0);

        for (size_t i = 0; i < numSamples; ++i) {
            left[i]  *= attenuationLinear;
            right[i] *= attenuationLinear;
        }
    }

    // Update stored true peak
    m_outputTruePeakDBTP = rain_measure_true_peak(left, right, numSamples, sampleRate);
}

// =========================================================================
// Conventional wideband limiting (no stem awareness)
// =========================================================================

ProcessResult SAILLimiter::processConventional(
    double* left, double* right, size_t numSamples, double sampleRate)
{
    if (numSamples == 0) {
        return {0.0, 0.0, false, "empty block"};
    }

    const ModeParams mp = getModeParams();
    const double attackCoeff  = std::exp(-1.0 / (sampleRate * mp.attackMs * 0.001));
    const double releaseCoeff = std::exp(-1.0 / (sampleRate * mp.releaseMs * 0.001));

    // Recalculate lookahead if sample rate changed
    int lookaheadSamples = static_cast<int>(m_config.lookaheadMs * 0.001 * sampleRate);
    if (lookaheadSamples < 1) lookaheadSamples = 1;

    if (sampleRate != m_lastSampleRate || lookaheadSamples != m_lookaheadSamples) {
        m_delayL.assign(static_cast<size_t>(lookaheadSamples), 0.0);
        m_delayR.assign(static_cast<size_t>(lookaheadSamples), 0.0);
        m_delayPos = 0;
        m_lookaheadSamples = lookaheadSamples;
        m_lastSampleRate = sampleRate;
        m_envelope = 0.0;
        m_gainSmooth = 1.0;
    }

    double peakGR_dB = 0.0;
    double sumGR_dB  = 0.0;

    for (size_t i = 0; i < numSamples; ++i) {
        // Look ahead to detect upcoming peaks
        size_t aheadIdx = i + static_cast<size_t>(m_lookaheadSamples);
        double aheadL = (aheadIdx < numSamples) ? left[aheadIdx]  : 0.0;
        double aheadR = (aheadIdx < numSamples) ? right[aheadIdx] : 0.0;
        double instPeak = std::max(std::abs(aheadL), std::abs(aheadR));

        // Envelope follower
        if (instPeak > m_envelope) {
            m_envelope = attackCoeff * m_envelope + (1.0 - attackCoeff) * instPeak;
        } else {
            m_envelope = releaseCoeff * m_envelope + (1.0 - releaseCoeff) * instPeak;
        }

        // Compute required gain
        double targetGain = computeGainReduction(m_envelope);

        // Smooth gain transitions
        if (targetGain < m_gainSmooth) {
            // Gain decreasing (more limiting): use attack
            m_gainSmooth = attackCoeff * m_gainSmooth + (1.0 - attackCoeff) * targetGain;
        } else {
            // Gain increasing (releasing): use release
            m_gainSmooth = releaseCoeff * m_gainSmooth + (1.0 - releaseCoeff) * targetGain;
        }

        // Clamp: never amplify
        if (m_gainSmooth > 1.0) m_gainSmooth = 1.0;

        // Track GR statistics
        double gr_dB = 20.0 * std::log10(std::max(m_gainSmooth, 1e-30));
        if (gr_dB < peakGR_dB) peakGR_dB = gr_dB;
        sumGR_dB += gr_dB;

        // Read delayed sample
        double delayedL = m_delayL[static_cast<size_t>(m_delayPos)];
        double delayedR = m_delayR[static_cast<size_t>(m_delayPos)];

        // Write current sample into delay buffer
        m_delayL[static_cast<size_t>(m_delayPos)] = left[i];
        m_delayR[static_cast<size_t>(m_delayPos)] = right[i];
        m_delayPos = (m_delayPos + 1) % m_lookaheadSamples;

        // Apply gain to delayed signal
        left[i]  = delayedL * m_gainSmooth;
        right[i] = delayedR * m_gainSmooth;
    }

    // Enforce true-peak ceiling
    enforceTruePeakCeiling(left, right, numSamples, sampleRate);

    ProcessResult result;
    result.peakGR          = peakGR_dB;
    result.avgGR           = sumGR_dB / static_cast<double>(numSamples);
    result.stemAwareActive = false;
    result.fallbackReason  = "";
    return result;
}

// =========================================================================
// Main processing: stem-aware block processing
// =========================================================================

ProcessResult SAILLimiter::processBlock(
    double* left,
    double* right,
    size_t numSamples,
    double sampleRate,
    const std::array<double, 6>& sailStemGains)
{
    if (numSamples == 0) {
        return {0.0, 0.0, false, "empty block"};
    }

    // Apply per-stem gain adjustments before limiting.
    // sail_stem_gains[12] maps to the 12 stems in the envelope list.
    // These are additive dB gains applied to the mix contribution weights.
    // (In a full stem-aware pipeline, these would be applied to individual
    // stem buffers before summing. Here we adjust the stem envelope weights
    // so the GR allocation reflects the user's stem gain preferences.)
    for (size_t i = 0; i < std::min(m_stemEnvelopes.size(), static_cast<size_t>(6)); ++i) {
        // Convert dB gain to linear multiplier and adjust the stem weight
        double gainLinear = std::pow(10.0, sailStemGains[i] / 20.0);
        m_stemEnvelopes[i].weight *= gainLinear;
        // Clamp weight to [0, 1]
        m_stemEnvelopes[i].weight = std::clamp(m_stemEnvelopes[i].weight, 0.0, 1.0);
    }

    // Check if stem-aware processing is possible
    if (!m_config.stemAwareEnabled) {
        return processConventional(left, right, numSamples, sampleRate);
    }

    // Check stem confidence threshold: if ALL confidences < 0.3, fallback
    bool anyConfident = false;
    for (const auto& env : m_stemEnvelopes) {
        if (env.confidence >= 0.3) {
            anyConfident = true;
            break;
        }
    }

    if (!anyConfident || m_stemEnvelopes.empty()) {
        ProcessResult result = processConventional(left, right, numSamples, sampleRate);
        result.fallbackReason = m_stemEnvelopes.empty()
            ? "no stem envelopes provided"
            : "all stem confidences below 0.3 threshold";
        return result;
    }

    // ---- Stem-aware limiting ----

    const ModeParams mp = getModeParams();
    const double attackCoeff  = std::exp(-1.0 / (sampleRate * mp.attackMs * 0.001));
    const double releaseCoeff = std::exp(-1.0 / (sampleRate * mp.releaseMs * 0.001));

    // Psychoacoustic release: program-dependent release time
    // When enabled, transient-heavy passages get faster release
    double effectiveReleaseCoeff = releaseCoeff;

    // Recalculate lookahead if sample rate changed
    int lookaheadSamples = static_cast<int>(m_config.lookaheadMs * 0.001 * sampleRate);
    if (lookaheadSamples < 1) lookaheadSamples = 1;

    if (sampleRate != m_lastSampleRate || lookaheadSamples != m_lookaheadSamples) {
        m_delayL.assign(static_cast<size_t>(lookaheadSamples), 0.0);
        m_delayR.assign(static_cast<size_t>(lookaheadSamples), 0.0);
        m_delayPos = 0;
        m_lookaheadSamples = lookaheadSamples;
        m_lastSampleRate = sampleRate;
        m_envelope = 0.0;
        m_gainSmooth = 1.0;
    }

    double peakGR_dB = 0.0;
    double sumGR_dB  = 0.0;

    // Compute average transient ratio across stems for psychoacoustic release
    double avgTransientRatio = 0.0;
    if (m_config.psychoacousticRelease && !m_stemEnvelopes.empty()) {
        for (const auto& env : m_stemEnvelopes) {
            avgTransientRatio += env.transientRatio;
        }
        avgTransientRatio /= static_cast<double>(m_stemEnvelopes.size());
    }

    for (size_t i = 0; i < numSamples; ++i) {
        // Lookahead peak detection
        size_t aheadIdx = i + static_cast<size_t>(m_lookaheadSamples);
        double aheadL = (aheadIdx < numSamples) ? left[aheadIdx]  : 0.0;
        double aheadR = (aheadIdx < numSamples) ? right[aheadIdx] : 0.0;
        double instPeak = std::max(std::abs(aheadL), std::abs(aheadR));

        // Envelope follower
        if (instPeak > m_envelope) {
            m_envelope = attackCoeff * m_envelope + (1.0 - attackCoeff) * instPeak;
        } else {
            // Psychoacoustic release: faster release for transient-heavy content
            if (m_config.psychoacousticRelease) {
                // Blend between normal release and faster release based on transient ratio
                // Higher transient ratio => faster release (shorter time constant)
                double fastReleaseMs = mp.releaseMs * 0.3;
                double fastReleaseCoeff = std::exp(-1.0 / (sampleRate * fastReleaseMs * 0.001));
                effectiveReleaseCoeff = releaseCoeff
                    + avgTransientRatio * (fastReleaseCoeff - releaseCoeff);
            } else {
                effectiveReleaseCoeff = releaseCoeff;
            }
            m_envelope = effectiveReleaseCoeff * m_envelope
                       + (1.0 - effectiveReleaseCoeff) * instPeak;
        }

        // Compute required gain
        double targetGain = computeGainReduction(m_envelope);

        // Smooth gain transitions
        if (targetGain < m_gainSmooth) {
            m_gainSmooth = attackCoeff * m_gainSmooth + (1.0 - attackCoeff) * targetGain;
        } else {
            m_gainSmooth = effectiveReleaseCoeff * m_gainSmooth
                         + (1.0 - effectiveReleaseCoeff) * targetGain;
        }

        if (m_gainSmooth > 1.0) m_gainSmooth = 1.0;

        // Track GR statistics
        double gr_dB = 20.0 * std::log10(std::max(m_gainSmooth, 1e-30));
        if (gr_dB < peakGR_dB) peakGR_dB = gr_dB;
        sumGR_dB += gr_dB;

        // Read from delay buffer
        double delayedL = m_delayL[static_cast<size_t>(m_delayPos)];
        double delayedR = m_delayR[static_cast<size_t>(m_delayPos)];

        // Write current sample into delay buffer
        m_delayL[static_cast<size_t>(m_delayPos)] = left[i];
        m_delayR[static_cast<size_t>(m_delayPos)] = right[i];
        m_delayPos = (m_delayPos + 1) % m_lookaheadSamples;

        // Apply gain to delayed signal
        left[i]  = delayedL * m_gainSmooth;
        right[i] = delayedR * m_gainSmooth;
    }

    // Compute the total GR applied and allocate across stems
    double avgGR_dB = sumGR_dB / static_cast<double>(numSamples);
    allocateGainReduction(avgGR_dB);

    // Enforce true-peak ceiling
    enforceTruePeakCeiling(left, right, numSamples, sampleRate);

    m_stemAwareWasActive = true;

    ProcessResult result;
    result.peakGR          = peakGR_dB;
    result.avgGR           = avgGR_dB;
    result.stemAwareActive = true;
    result.fallbackReason  = "";
    return result;
}

// =========================================================================
// Query methods
// =========================================================================

std::vector<StemGainAllocation> SAILLimiter::getStemGainAllocation() const {
    return m_lastAllocations;
}

double SAILLimiter::getOutputTruePeakDBTP() const {
    return m_outputTruePeakDBTP;
}

} // namespace rain
