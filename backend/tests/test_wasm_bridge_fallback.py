"""
WASM bridge fallback tests.

Verifies the bridge correctly falls back to Python DSP when neither
pybind11 native extension nor CLI is available (the typical case).
"""
import io
import os
import numpy as np
import pytest
import soundfile as sf

os.environ.setdefault("RAIN_ENV", "test")


def _make_wav_bytes(duration_sec: float = 1.0, sr: int = 48000) -> bytes:
    """Generate stereo WAV bytes."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    audio = np.column_stack([
        0.3 * np.sin(2 * np.pi * 440 * t),
        0.3 * np.sin(2 * np.pi * 554 * t),
    ])
    buf = io.BytesIO()
    sf.write(buf, audio, sr, subtype="PCM_16", format="WAV")
    return buf.getvalue()


class TestWASMBridgeFallback:
    def test_detects_python_backend(self):
        """On a standard Python env, bridge should detect python_dsp backend."""
        from app.services.wasm_bridge import RainDSPBridge

        bridge = RainDSPBridge()
        assert bridge._backend == "python_dsp"

    def test_process_produces_audio(self):
        """Python fallback should produce valid WAV output."""
        from app.services.wasm_bridge import RainDSPBridge

        bridge = RainDSPBridge()
        wav_bytes = _make_wav_bytes()
        output_bytes, result = bridge.process(wav_bytes, {"target_lufs": -14.0})

        assert len(output_bytes) > 0
        # Verify it's valid WAV
        audio, sr = sf.read(io.BytesIO(output_bytes), dtype="float64", always_2d=True)
        assert sr == 48000
        assert audio.shape[1] == 2

    def test_render_result_has_real_measurements(self):
        """RenderResult should have non-zero measurements from Python DSP."""
        from app.services.wasm_bridge import RainDSPBridge

        bridge = RainDSPBridge()
        wav_bytes = _make_wav_bytes(duration_sec=2.0)
        _, result = bridge.process(wav_bytes, {"target_lufs": -14.0})

        assert result.backend_used == "python_dsp"
        assert result.integrated_lufs != 0.0
        assert result.true_peak_dbtp < 0.0
        assert result.integrated_lufs < 0.0  # should be negative

    def test_backend_used_field_present(self):
        """RenderResult must include backend_used field."""
        from app.services.wasm_bridge import RainDSPBridge, RenderResult

        bridge = RainDSPBridge()
        wav_bytes = _make_wav_bytes()
        _, result = bridge.process(wav_bytes, {})

        assert hasattr(result, "backend_used")
        assert result.backend_used in ("raindsp_native", "raindsp_cli", "python_dsp")
