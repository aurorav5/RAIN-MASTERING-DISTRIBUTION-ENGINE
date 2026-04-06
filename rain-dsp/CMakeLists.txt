cmake_minimum_required(VERSION 3.20)
project(RainDSP VERSION 6.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(BUILD_WASM "Build WebAssembly target" OFF)
option(BUILD_TESTS "Build test suite" ON)
option(ENABLE_AVX2 "Enable AVX2 optimization" ON)

# Source files
set(RAIN_DSP_SOURCES
    src/lufs.cpp
    src/true_peak.cpp
    src/multiband.cpp
    src/linear_phase_eq.cpp
    src/fft.cpp
    src/sail.cpp
    src/ms_processing.cpp
    src/saturation.cpp
    src/riaa.cpp
    src/biquad.cpp
    src/limiter.cpp
)

if(BUILD_WASM)
    # WASM target
    add_executable(rain_dsp_wasm ${RAIN_DSP_SOURCES} src/main.cpp)
    target_include_directories(rain_dsp_wasm PRIVATE include)
    set_target_properties(rain_dsp_wasm PROPERTIES
        OUTPUT_NAME "rain_dsp"
        SUFFIX ".js"
    )

    set(WASM_EXPORTED_FUNCTIONS
        "_rain_process"
        "_rain_serialize_params"
        "_rain_result_output_ptr"
        "_rain_result_output_len"
        "_rain_result_lufs"
        "_rain_result_true_peak"
        "_rain_free_result"
        "_rain_get_version"
        "_malloc"
        "_free"
    )
    string(JOIN "," WASM_EXPORTED_FUNCTIONS_STR ${WASM_EXPORTED_FUNCTIONS})

    set_target_properties(rain_dsp_wasm PROPERTIES
        LINK_FLAGS "-sEXPORTED_FUNCTIONS=[${WASM_EXPORTED_FUNCTIONS_STR}] \
                    -sEXPORTED_RUNTIME_METHODS=[ccall,cwrap,HEAPU8,UTF8ToString] \
                    -sALLOW_MEMORY_GROWTH=1 \
                    -sMAXIMUM_MEMORY=1073741824 \
                    -sMODULARIZE=1 \
                    -sEXPORT_NAME='RainDSP' \
                    -sENVIRONMENT='web,worker' \
                    -sWASM_BIGINT \
                    -O3 \
                    -msimd128 \
                    -mrelaxed-simd \
                    -sAUDIO_WORKLET \
                    -sWASM_WORKERS \
                    -sSHARED_MEMORY \
                    -sINITIAL_MEMORY=67108864 \
                    -sMALLOC=emmalloc \
                    --closure=1"
    )
    target_compile_options(rain_dsp_wasm PRIVATE
        -O3
        -msimd128
        -mrelaxed-simd
        -ffast-math
        -fno-exceptions
        -fno-rtti
        -flto
    )
else()
    # Native library (for testing)
    add_library(rain_dsp STATIC ${RAIN_DSP_SOURCES})
    target_include_directories(rain_dsp PUBLIC include)

    if(ENABLE_AVX2)
        target_compile_options(rain_dsp PRIVATE -mavx2 -mfma -O3)
    else()
        target_compile_options(rain_dsp PRIVATE -msse4.2 -O3)
    endif()

    # Find FFTW3 for native builds
    find_package(PkgConfig QUIET)
    if(PkgConfig_FOUND)
        pkg_check_modules(FFTW3 QUIET fftw3)
        if(FFTW3_FOUND)
            target_compile_definitions(rain_dsp PRIVATE HAVE_FFTW3)
            target_link_libraries(rain_dsp ${FFTW3_LIBRARIES})
            target_include_directories(rain_dsp PRIVATE ${FFTW3_INCLUDE_DIRS})
        endif()
    endif()

    # Tests
    if(BUILD_TESTS)
        enable_testing()
        include(FetchContent)
        FetchContent_Declare(
            googletest
            URL https://github.com/google/googletest/archive/v1.14.0.zip
            DOWNLOAD_EXTRACT_TIMESTAMP ON
        )
        FetchContent_MakeAvailable(googletest)

        add_executable(rain_dsp_tests
            tests/test_lufs.cpp
            tests/test_true_peak.cpp
            tests/test_multiband.cpp
            tests/test_kweight.cpp
            tests/test_riaa.cpp
            tests/test_ms.cpp
        )
        target_link_libraries(rain_dsp_tests rain_dsp GTest::gtest_main)
        target_include_directories(rain_dsp_tests PRIVATE include)

        include(GoogleTest)
        gtest_discover_tests(rain_dsp_tests)
    endif()
endif()
