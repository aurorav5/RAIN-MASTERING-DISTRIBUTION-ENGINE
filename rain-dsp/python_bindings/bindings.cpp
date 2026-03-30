#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include "../include/rain_dsp.h"
#include "../include/lufs.h"
#include "../include/true_peak.h"
#include <string>
#include <vector>
#include <stdexcept>
#include <sstream>

// Minimal JSON parser for ProcessingParams
// Extracts float/bool/string fields from a flat JSON object
static rain::ProcessingParams parse_params(const std::string& json_str) {
    rain::ProcessingParams p{};
    // defaults
    p.target_lufs = -14.0;
    p.true_peak_ceiling = -1.0;
    p.mb_threshold_low = -24.0;
    p.mb_threshold_mid = -18.0;
    p.mb_threshold_high = -12.0;
    p.mb_ratio_low = 2.5;
    p.mb_ratio_mid = 2.0;
    p.mb_ratio_high = 2.0;
    p.mb_attack_low = 10.0;
    p.mb_attack_mid = 5.0;
    p.mb_attack_high = 2.0;
    p.mb_release_low = 150.0;
    p.mb_release_mid = 80.0;
    p.mb_release_high = 40.0;
    for (int i = 0; i < 8; ++i) p.eq_gains[i] = 0.0;
    p.analog_saturation = false;
    p.saturation_drive = 0.0;
    p.saturation_mode = "tape";
    p.ms_enabled = false;
    p.mid_gain = 0.0;
    p.side_gain = 0.0;
    p.stereo_width = 1.0;
    p.sail_enabled = true;
    for (int i = 0; i < 6; ++i) p.sail_stem_gains[i] = 0.0;
    p.vinyl_mode = false;

    // Very simple key-value extraction (not a full JSON parser)
    auto get_double = [&](const std::string& key) -> double {
        auto pos = json_str.find("\"" + key + "\"");
        if (pos == std::string::npos) return 0.0;
        auto colon = json_str.find(':', pos);
        if (colon == std::string::npos) return 0.0;
        return std::stod(json_str.substr(colon + 1));
    };
    auto get_bool = [&](const std::string& key) -> bool {
        auto pos = json_str.find("\"" + key + "\"");
        if (pos == std::string::npos) return false;
        auto colon = json_str.find(':', pos);
        if (colon == std::string::npos) return false;
        auto val_start = json_str.find_first_not_of(" \t\n\r", colon + 1);
        return json_str.substr(val_start, 4) == "true";
    };

    p.target_lufs = get_double("target_lufs");
    if (p.target_lufs == 0.0) p.target_lufs = -14.0;
    p.true_peak_ceiling = get_double("true_peak_ceiling");
    if (p.true_peak_ceiling == 0.0) p.true_peak_ceiling = -1.0;
    p.mb_threshold_low = get_double("mb_threshold_low");
    if (p.mb_threshold_low == 0.0) p.mb_threshold_low = -24.0;
    p.mb_threshold_mid = get_double("mb_threshold_mid");
    if (p.mb_threshold_mid == 0.0) p.mb_threshold_mid = -18.0;
    p.mb_threshold_high = get_double("mb_threshold_high");
    if (p.mb_threshold_high == 0.0) p.mb_threshold_high = -12.0;
    p.mb_ratio_low = get_double("mb_ratio_low");
    if (p.mb_ratio_low == 0.0) p.mb_ratio_low = 2.5;
    p.mb_ratio_mid = get_double("mb_ratio_mid");
    if (p.mb_ratio_mid == 0.0) p.mb_ratio_mid = 2.0;
    p.mb_ratio_high = get_double("mb_ratio_high");
    if (p.mb_ratio_high == 0.0) p.mb_ratio_high = 2.0;
    p.mb_attack_low = get_double("mb_attack_low");
    if (p.mb_attack_low == 0.0) p.mb_attack_low = 10.0;
    p.mb_attack_mid = get_double("mb_attack_mid");
    if (p.mb_attack_mid == 0.0) p.mb_attack_mid = 5.0;
    p.mb_attack_high = get_double("mb_attack_high");
    if (p.mb_attack_high == 0.0) p.mb_attack_high = 2.0;
    p.mb_release_low = get_double("mb_release_low");
    if (p.mb_release_low == 0.0) p.mb_release_low = 150.0;
    p.mb_release_mid = get_double("mb_release_mid");
    if (p.mb_release_mid == 0.0) p.mb_release_mid = 80.0;
    p.mb_release_high = get_double("mb_release_high");
    if (p.mb_release_high == 0.0) p.mb_release_high = 40.0;
    p.analog_saturation = get_bool("analog_saturation");
    p.saturation_drive = get_double("saturation_drive");
    p.ms_enabled = get_bool("ms_enabled");
    p.mid_gain = get_double("mid_gain");
    p.side_gain = get_double("side_gain");
    p.stereo_width = get_double("stereo_width");
    if (p.stereo_width == 0.0) p.stereo_width = 1.0;
    p.sail_enabled = true;
    p.vinyl_mode = get_bool("vinyl_mode");
    return p;
}

namespace py = pybind11;

PYBIND11_MODULE(rain_dsp_native, m) {
    m.doc() = "RainDSP Python bindings";

    py::class_<rain::LufsResult>(m, "LufsResult")
        .def_readonly("integrated", &rain::LufsResult::integrated)
        .def_readonly("short_term", &rain::LufsResult::short_term)
        .def_readonly("momentary", &rain::LufsResult::momentary)
        .def_readonly("loudness_range", &rain::LufsResult::loudness_range)
        .def_readonly("true_peak_dbtp", &rain::LufsResult::true_peak_dbtp);

    m.def("process",
        [](py::array_t<double> left_arr, py::array_t<double> right_arr,
           double sample_rate, const std::string& params_json)
        -> std::tuple<py::array_t<double>, py::array_t<double>, std::string>
        {
            auto left_buf = left_arr.request();
            auto right_buf = right_arr.request();
            const size_t n = static_cast<size_t>(left_buf.size);

            rain::ProcessingParams params = parse_params(params_json);

            std::vector<double> out_left(n), out_right(n);
            const double* in_l = static_cast<const double*>(left_buf.ptr);
            const double* in_r = static_cast<const double*>(right_buf.ptr);

            rain::rain_process(in_l, in_r, out_left.data(), out_right.data(), n, sample_rate, params);

            // Measure output
            rain::LufsResult lufs = rain::rain_measure_lufs(out_left.data(), out_right.data(), n, sample_rate);
            double tp = rain::rain_measure_true_peak(out_left.data(), out_right.data(), n, sample_rate);

            std::ostringstream json;
            json << std::fixed;
            json << "{\"integrated_lufs\":" << lufs.integrated
                 << ",\"short_term_lufs\":" << lufs.short_term
                 << ",\"momentary_lufs\":" << lufs.momentary
                 << ",\"loudness_range\":" << lufs.loudness_range
                 << ",\"true_peak_dbtp\":" << tp << "}";

            py::array_t<double> out_l_arr(n), out_r_arr(n);
            std::copy(out_left.begin(), out_left.end(),
                      static_cast<double*>(out_l_arr.request().ptr));
            std::copy(out_right.begin(), out_right.end(),
                      static_cast<double*>(out_r_arr.request().ptr));

            return {out_l_arr, out_r_arr, json.str()};
        },
        "Process audio through RainDSP pipeline. Returns (out_left, out_right, result_json).",
        py::arg("left"), py::arg("right"), py::arg("sample_rate"), py::arg("params_json")
    );
}
