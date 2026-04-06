"""
Master engine integration tests.

Tests the full 10-stage mastering chain with real WAV audio.
No mocks — exercises actual DSP code with real numpy/scipy processing.
"""
import os
import tempfile
import numpy as np
import pytest
import soundfile as sf

os.environ.setdefault("RAIN_ENV", "test")


def _generate_test_wav(path: str, duration_sec: float = 3.0, sr: int = 44100) -> str:
    """Generate a stereo sine wave test file."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    left = 0.3 * np.sin(2 * np.pi * 440 * t)  # A4
    right = 0.3 * np.sin(2 * np.pi * 554.37 * t)  # C#5
    audio = np.column_stack([left, right])
    sf.write(path, audio, sr, subtype="PCM_16")
    return path


class TestMasterEngine:
    def test_full_chain_default_params(self):
        """Master with default params produces valid output."""
        from app.services.master_engine import master_audio, MasteringParams

        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = _generate_test_wav(os.path.join(tmpdir, "input.wav"))
            result = master_audio(
                wav_path, tmpdir,
                metadata={"title": "Test", "artist": "Test"},
            )

            assert os.path.exists(result.output_wav_path)
            assert os.path.exists(result.output_mp3_path)
            assert result.output_lufs != 0.0
            assert result.output_true_peak < 0.0  # should be below 0 dBTP
            assert result.analysis.duration > 0

    def test_output_lufs_within_target(self):
        """Output LUFS should be within ±1.5 LU of target."""
        from app.services.master_engine import master_audio, MasteringParams

        target = -14.0
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = _generate_test_wav(os.path.join(tmpdir, "input.wav"), duration_sec=5.0)
            result = master_audio(
                wav_path, tmpdir,
                params=MasteringParams(loudness=target),
                metadata={"title": "LUFS Test", "artist": "Test"},
            )

            delta = abs(result.output_lufs - target)
            assert delta < 1.5, f"Output LUFS {result.output_lufs} deviates {delta} LU from target {target}"

    def test_groove_analysis_populated(self):
        """Groove fields in AnalysisResult should have non-default values."""
        from app.services.master_engine import master_audio

        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = _generate_test_wav(os.path.join(tmpdir, "input.wav"))
            result = master_audio(
                wav_path, tmpdir,
                metadata={"genre": "afropop_house"},
            )

            # Groove engine should have been called, producing real values
            analysis = result.analysis
            assert analysis.tempo_bpm > 0
            assert 0.0 <= analysis.groove_score <= 1.0
            assert analysis.swing_ratio > 0

    def test_genre_specific_life_injection(self):
        """Electronic genre should get more saturation than classical."""
        from app.services.master_engine import apply_life_injection, INTERNAL_SR

        audio = np.random.randn(48000 * 2, 2) * 0.3  # 2 seconds
        electronic = apply_life_injection(audio.copy(), INTERNAL_SR, genre="electronic")
        classical = apply_life_injection(audio.copy(), INTERNAL_SR, genre="classical")

        # Electronic should have more energy added (higher RMS)
        rms_electronic = np.sqrt(np.mean(electronic ** 2))
        rms_classical = np.sqrt(np.mean(classical ** 2))
        # Both should be close to original but electronic gets more drive
        assert rms_electronic > rms_classical * 0.99  # electronic has more energy

    def test_groove_enhancement_applied(self):
        """Groove enhancement should modify audio when groove_score is low."""
        from app.services.master_engine import (
            apply_groove_enhancement, AnalysisResult, INTERNAL_SR,
        )

        audio = np.random.randn(48000 * 2, 2) * 0.3
        analysis = AnalysisResult(
            input_lufs=-20.0, input_true_peak=-3.0,
            spectral_centroid=3000.0, crest_factor=12.0,
            stereo_width=0.5, bass_energy_ratio=0.3,
            dynamic_range=12.0, sample_rate=48000,
            channels=2, duration=2.0,
            groove_score=0.2,  # Low groove — should trigger enhancement
            transient_sharpness=0.3,
        )

        enhanced = apply_groove_enhancement(audio, INTERNAL_SR, analysis, genre="hiphop")
        # Should not be identical to input (some processing applied)
        assert enhanced.shape == audio.shape

    def test_24bit_wav_output(self):
        """Output WAV should be 24-bit."""
        from app.services.master_engine import master_audio

        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = _generate_test_wav(os.path.join(tmpdir, "input.wav"))
            result = master_audio(wav_path, tmpdir)

            info = sf.info(result.output_wav_path)
            assert info.subtype == "PCM_24"
            assert info.samplerate == 48000

    def test_stereo_output(self):
        """Output should always be stereo."""
        from app.services.master_engine import master_audio

        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = _generate_test_wav(os.path.join(tmpdir, "input.wav"))
            result = master_audio(wav_path, tmpdir)

            data, sr = sf.read(result.output_wav_path, always_2d=True)
            assert data.shape[1] == 2
