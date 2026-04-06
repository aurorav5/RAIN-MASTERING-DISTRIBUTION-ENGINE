"""
Multi-format download / transcode tests.

Tests that ffmpeg transcoding produces valid output files for each format.
Requires ffmpeg on PATH (installed in Docker worker image).
"""
import io
import os
import subprocess
import numpy as np
import pytest
import soundfile as sf

os.environ.setdefault("RAIN_ENV", "test")


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _make_wav_bytes(duration_sec: float = 1.0, sr: int = 48000) -> bytes:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    audio = np.column_stack([
        0.3 * np.sin(2 * np.pi * 440 * t),
        0.3 * np.sin(2 * np.pi * 554 * t),
    ])
    buf = io.BytesIO()
    sf.write(buf, audio, sr, subtype="PCM_24", format="WAV")
    return buf.getvalue()


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not on PATH")
class TestTranscode:
    @pytest.fixture
    def wav_bytes(self):
        return _make_wav_bytes(duration_sec=2.0)

    @pytest.mark.asyncio
    async def test_mp3_transcode(self, wav_bytes):
        from app.api.routes.download import _transcode
        result = await _transcode(wav_bytes, "mp3")
        assert len(result) > 0
        # MP3 files start with ID3 or sync bytes
        assert result[:3] == b"ID3" or result[:2] == b"\xff\xfb"

    @pytest.mark.asyncio
    async def test_flac_transcode(self, wav_bytes):
        from app.api.routes.download import _transcode
        result = await _transcode(wav_bytes, "flac")
        assert len(result) > 0
        assert result[:4] == b"fLaC"

    @pytest.mark.asyncio
    async def test_aac_transcode(self, wav_bytes):
        from app.api.routes.download import _transcode
        result = await _transcode(wav_bytes, "aac")
        assert len(result) > 0
        # M4A container starts with ftyp
        assert b"ftyp" in result[:12]

    @pytest.mark.asyncio
    async def test_ogg_transcode(self, wav_bytes):
        from app.api.routes.download import _transcode
        result = await _transcode(wav_bytes, "ogg")
        assert len(result) > 0
        assert result[:4] == b"OggS"


class TestDDPGeneration:
    def test_ddp_image_contains_required_files(self):
        import zipfile
        from unittest.mock import MagicMock
        from app.api.routes.download import _build_ddp_image

        wav_bytes = _make_wav_bytes(duration_sec=3.0)
        mock_session = MagicMock()
        mock_session.id = "test-session-123"
        mock_session.isrc = "USRC12345678"
        mock_session.title = "Test Track"

        ddp_zip = _build_ddp_image(wav_bytes, mock_session)
        assert len(ddp_zip) > 0

        with zipfile.ZipFile(io.BytesIO(ddp_zip)) as zf:
            names = zf.namelist()
            assert "DDPID" in names
            assert "DDPMS" in names
            assert "PQSHEET" in names
            assert "AUDIO.PCM" in names

            ddpid = zf.read("DDPID").decode()
            assert "DDP_ID" in ddpid
            assert "test-session-123" in ddpid

            pqsheet = zf.read("PQSHEET").decode()
            assert "USRC12345678" in pqsheet
