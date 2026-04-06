// WASM/native entry point for RainDSP
// All extern "C" exports for JavaScript/WASM interop.

#include "rain_dsp.h"
#include "multiband.h"
#include "linear_phase_eq.h"
#include "ms_processing.h"
#include "saturation.h"
#include "sail.h"
#include "riaa.h"
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <string>
#include <vector>
#include <algorithm>

// ---------------------------------------------------------------------------
// Minimal JSON field extraction — no external dependencies
// ---------------------------------------------------------------------------

static double json_get_double(const char* json, const char* key, double def) {
    if (!json || !key) return def;
    // Look for "key": value
    // Build search pattern: "key":
    char pattern[256];
    std::snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    const char* pos = std::strstr(json, pattern);
    if (!pos) return def;
    pos += std::strlen(pattern);
    // Skip whitespace and colon
    while (*pos == ' ' || *pos == '\t' || *pos == '\n' || *pos == '\r') ++pos;
    if (*pos != ':') return def;
    ++pos;
    while (*pos == ' ' || *pos == '\t' || *pos == '\n' || *pos == '\r') ++pos;
    // Parse number
    char* endptr = nullptr;
    double val = std::strtod(pos, &endptr);
    if (endptr == pos) return def;
    return val;
}

static bool json_get_bool(const char* json, const char* key, bool def) {
    if (!json || !key) return def;
    char pattern[256];
    std::snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    const char* pos = std::strstr(json, pattern);
    if (!pos) return def;
    pos += std::strlen(pattern);
    while (*pos == ' ' || *pos == '\t' || *pos == '\n' || *pos == '\r') ++pos;
    if (*pos != ':') return def;
    ++pos;
    while (*pos == ' ' || *pos == '\t' || *pos == '\n' || *pos == '\r') ++pos;
    if (std::strncmp(pos, "true", 4) == 0)  return true;
    if (std::strncmp(pos, "false", 5) == 0) return false;
    return def;
}

static std::string json_get_string(const char* json, const char* key, const char* def) {
    if (!json || !key) return def ? def : "";
    char pattern[256];
    std::snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    const char* pos = std::strstr(json, pattern);
    if (!pos) return def ? def : "";
    pos += std::strlen(pattern);
    while (*pos == ' ' || *pos == '\t' || *pos == '\n' || *pos == '\r') ++pos;
    if (*pos != ':') return def ? def : "";
    ++pos;
    while (*pos == ' ' || *pos == '\t' || *pos == '\n' || *pos == '\r') ++pos;
    if (*pos != '"') return def ? def : "";
    ++pos;
    const char* end = std::strchr(pos, '"');
    if (!end) return def ? def : "";
    return std::string(pos, end - pos);
}

// Parse a JSON array of doubles: "[v0, v1, ...]"
// Finds the array for the given key and reads up to max_count values
static void json_get_double_array(const char* json, const char* key,
                                   double* out, int max_count, double def) {
    for (int i = 0; i < max_count; ++i) out[i] = def;
    if (!json || !key) return;
    char pattern[256];
    std::snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    const char* pos = std::strstr(json, pattern);
    if (!pos) return;
    pos += std::strlen(pattern);
    while (*pos == ' ' || *pos == '\t' || *pos == '\n' || *pos == '\r') ++pos;
    if (*pos != ':') return;
    ++pos;
    while (*pos == ' ' || *pos == '\t' || *pos == '\n' || *pos == '\r') ++pos;
    if (*pos != '[') return;
    ++pos;
    int count = 0;
    while (count < max_count) {
        while (*pos == ' ' || *pos == '\t' || *pos == '\n' || *pos == '\r' || *pos == ',') ++pos;
        if (*pos == ']' || *pos == '\0') break;
        char* endptr = nullptr;
        double val = std::strtod(pos, &endptr);
        if (endptr == pos) break;
        out[count++] = val;
        pos = endptr;
    }
}

// ---------------------------------------------------------------------------
// Parse JSON into ProcessingParams
// ---------------------------------------------------------------------------

static rain::ProcessingParams parse_params(const char* json) {
    rain::ProcessingParams p;
    if (!json) return p;

    p.mb_threshold_low   = json_get_double(json, "mb_threshold_low",   p.mb_threshold_low);
    p.mb_threshold_mid   = json_get_double(json, "mb_threshold_mid",   p.mb_threshold_mid);
    p.mb_threshold_high  = json_get_double(json, "mb_threshold_high",  p.mb_threshold_high);
    p.mb_ratio_low       = json_get_double(json, "mb_ratio_low",       p.mb_ratio_low);
    p.mb_ratio_mid       = json_get_double(json, "mb_ratio_mid",       p.mb_ratio_mid);
    p.mb_ratio_high      = json_get_double(json, "mb_ratio_high",      p.mb_ratio_high);
    p.mb_attack_low      = json_get_double(json, "mb_attack_low",      p.mb_attack_low);
    p.mb_attack_mid      = json_get_double(json, "mb_attack_mid",      p.mb_attack_mid);
    p.mb_attack_high     = json_get_double(json, "mb_attack_high",     p.mb_attack_high);
    p.mb_release_low     = json_get_double(json, "mb_release_low",     p.mb_release_low);
    p.mb_release_mid     = json_get_double(json, "mb_release_mid",     p.mb_release_mid);
    p.mb_release_high    = json_get_double(json, "mb_release_high",    p.mb_release_high);

    // EQ: eq_gains array
    {
        double gains[8] = {0,0,0,0,0,0,0,0};
        json_get_double_array(json, "eq_gains", gains, 8, 0.0);
        for (int i = 0; i < 8; ++i) p.eq_gains[i] = gains[i];

        double freqs[8] = {60,120,250,500,1000,4000,8000,16000};
        json_get_double_array(json, "eq_frequencies", freqs, 8, 0.0);
        for (int i = 0; i < 8; ++i) p.eq_frequencies[i] = freqs[i];
    }

    p.analog_saturation  = json_get_bool(json,   "analog_saturation",  p.analog_saturation);
    p.saturation_drive   = json_get_double(json,  "saturation_drive",   p.saturation_drive);
    p.saturation_mode    = json_get_string(json,  "saturation_mode",    p.saturation_mode.c_str());

    p.ms_enabled         = json_get_bool(json,   "ms_enabled",         p.ms_enabled);
    p.mid_gain           = json_get_double(json,  "mid_gain",           p.mid_gain);
    p.side_gain          = json_get_double(json,  "side_gain",          p.side_gain);
    p.stereo_width       = json_get_double(json,  "stereo_width",       p.stereo_width);

    p.target_lufs        = json_get_double(json,  "target_lufs",        p.target_lufs);
    p.true_peak_ceiling  = json_get_double(json,  "true_peak_ceiling",  p.true_peak_ceiling);
    p.vinyl_mode         = json_get_bool(json,   "vinyl_mode",         p.vinyl_mode);

    p.sail_enabled       = json_get_bool(json,   "sail_enabled",       p.sail_enabled);
    {
        double sg[6] = {0,0,0,0,0,0};
        json_get_double_array(json, "sail_stem_gains", sg, 6, 0.0);
        for (int i = 0; i < 6; ++i) p.sail_stem_gains[i] = sg[i];
    }

    return p;
}

// ---------------------------------------------------------------------------
// RainResult struct
// ---------------------------------------------------------------------------

struct RainResult {
    std::vector<double> output_l;
    std::vector<double> output_r;
    std::vector<uint8_t> output_bytes;  // interleaved stereo doubles as raw bytes
    rain::LufsResult lufs;
    double true_peak_dbtp = 0.0;
};

// ---------------------------------------------------------------------------
// extern "C" exports
// ---------------------------------------------------------------------------

extern "C" {

const char* rain_get_version() {
    return rain::VERSION;
}

void* rain_process(
    const double* inputPtr,
    int inputLen,
    const char* paramsJson,
    double sampleRate)
{
    if (!inputPtr || inputLen <= 0) return nullptr;

    rain::ProcessingParams params = parse_params(paramsJson);

    const size_t n = static_cast<size_t>(inputLen);

    // Deinterleave: inputPtr is [L0,R0,L1,R1,...] with inputLen stereo pairs
    std::vector<double> left(n), right(n);
    for (size_t i = 0; i < n; ++i) {
        left[i]  = inputPtr[i * 2];
        right[i] = inputPtr[i * 2 + 1];
    }

    // --- DSP pipeline (strict order per spec) ---

    // 1. Apply EQ (if any eq_gains non-zero)
    {
        bool any_nonzero = false;
        for (int b = 0; b < 8; ++b) {
            if (std::abs(params.eq_gains[b]) > 1e-9) { any_nonzero = true; break; }
        }
        if (any_nonzero) {
            rain::apply_linear_phase_eq(left.data(), right.data(), n, sampleRate, params);
        }
    }

    // 2. Apply M/S (if ms_enabled)
    if (params.ms_enabled) {
        rain::apply_ms_processing(left.data(), right.data(), n, params);
    }

    // 3. Apply multiband compression
    rain::apply_multiband(left.data(), right.data(), n, sampleRate, params);

    // 4. Apply saturation (if analog_saturation)
    if (params.analog_saturation) {
        rain::apply_saturation(left.data(), right.data(), n, params);
    }

    // 5. Apply vinyl RIAA curve (if vinyl_mode — before limiting)
    if (params.vinyl_mode) {
        rain::apply_riaa(left.data(), right.data(), n, sampleRate);
    }

    // 6. Apply SAIL (always — handles limiting + normalization)
    rain::apply_sail(left.data(), right.data(), n, sampleRate, params);

    // --- Measure output ---
    rain::LufsResult lufs = rain::rain_measure_lufs(left.data(), right.data(), n, sampleRate);

    // --- Build result ---
    RainResult* result = new RainResult();
    result->output_l   = left;
    result->output_r   = right;
    result->lufs       = lufs;
    result->true_peak_dbtp = lufs.true_peak_dbtp;

    // Re-interleave as raw bytes: L0,R0,L1,R1,... each as 8 bytes (double)
    result->output_bytes.resize(n * 2 * sizeof(double));
    for (size_t i = 0; i < n; ++i) {
        double lv = left[i];
        double rv = right[i];
        std::memcpy(result->output_bytes.data() + (i * 2 + 0) * sizeof(double), &lv, sizeof(double));
        std::memcpy(result->output_bytes.data() + (i * 2 + 1) * sizeof(double), &rv, sizeof(double));
    }

    return static_cast<void*>(result);
}

void* rain_serialize_params(const char* jsonPtr) {
    if (!jsonPtr) return nullptr;
    rain::ProcessingParams* p = new rain::ProcessingParams(parse_params(jsonPtr));
    return static_cast<void*>(p);
}

const uint8_t* rain_result_output_ptr(void* handle) {
    if (!handle) return nullptr;
    RainResult* r = static_cast<RainResult*>(handle);
    return r->output_bytes.data();
}

int rain_result_output_len(void* handle) {
    if (!handle) return 0;
    RainResult* r = static_cast<RainResult*>(handle);
    return static_cast<int>(r->output_bytes.size());
}

double rain_result_lufs(void* handle) {
    if (!handle) return -std::numeric_limits<double>::infinity();
    RainResult* r = static_cast<RainResult*>(handle);
    return r->lufs.integrated;
}

double rain_result_true_peak(void* handle) {
    if (!handle) return -std::numeric_limits<double>::infinity();
    RainResult* r = static_cast<RainResult*>(handle);
    return r->true_peak_dbtp;
}

void rain_free_result(void* handle) {
    if (!handle) return;
    delete static_cast<RainResult*>(handle);
}

} // extern "C"
