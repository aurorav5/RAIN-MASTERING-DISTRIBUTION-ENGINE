"""Non-blocking audio I/O helpers.

Replaces blocking `librosa.load()` calls in request-path code. Simple reads use
soundfile (fast, pure C). Heavy DSP (mel spectrograms, resampling, onset detection)
is offloaded to a ProcessPoolExecutor — ThreadPoolExecutor won't help because the
GIL blocks CPU-bound numpy work.

For operations taking >2 seconds, dispatch a Celery task instead (worker.py queues).
"""
from __future__ import annotations
import asyncio
import io
from concurrent.futures import ProcessPoolExecutor
from typing import Optional
import numpy as np
import soundfile as sf
import structlog

logger = structlog.get_logger()

# Single shared process pool. Sized conservatively — each process loads numpy+scipy.
_audio_pool: Optional[ProcessPoolExecutor] = None


def _get_pool() -> ProcessPoolExecutor:
    global _audio_pool
    if _audio_pool is None:
        import os
        max_workers = min(4, (os.cpu_count() or 2))
        _audio_pool = ProcessPoolExecutor(max_workers=max_workers)
    return _audio_pool


async def read_audio(
    source: str | bytes, *, dtype: str = "float32", always_2d: bool = True
) -> tuple[np.ndarray, int]:
    """
    Async non-blocking audio read. Returns (samples, sample_rate).
    Uses soundfile (libsndfile) which releases the GIL.
    `source` is a filesystem path or raw bytes.
    """
    def _read() -> tuple[np.ndarray, int]:
        if isinstance(source, bytes):
            data, sr = sf.read(io.BytesIO(source), dtype=dtype, always_2d=always_2d)
        else:
            data, sr = sf.read(source, dtype=dtype, always_2d=always_2d)
        return data, sr

    return await asyncio.to_thread(_read)


async def write_audio(path: str, samples: np.ndarray, sample_rate: int, subtype: str = "PCM_24") -> None:
    """Async non-blocking audio write (soundfile, releases GIL)."""
    await asyncio.to_thread(sf.write, path, samples, sample_rate, subtype)


async def compute_mel_spectrogram(
    samples: np.ndarray, sample_rate: int, *, n_mels: int = 128, n_fft: int = 2048, hop_length: int = 512
) -> np.ndarray:
    """
    Offload mel spectrogram computation to a process pool.
    Use this instead of calling librosa.feature.melspectrogram in request handlers.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _get_pool(),
        _compute_mel_worker,
        samples,
        sample_rate,
        n_mels,
        n_fft,
        hop_length,
    )


def _compute_mel_worker(
    samples: np.ndarray, sample_rate: int, n_mels: int, n_fft: int, hop_length: int
) -> np.ndarray:
    """Worker function — runs in a separate process."""
    import librosa
    if samples.ndim == 2:
        samples = samples.mean(axis=1)  # mono-sum for analysis
    return librosa.feature.melspectrogram(
        y=samples.astype(np.float32),
        sr=sample_rate,
        n_mels=n_mels,
        n_fft=n_fft,
        hop_length=hop_length,
    )


def shutdown_pool() -> None:
    """Call on application shutdown."""
    global _audio_pool
    if _audio_pool is not None:
        _audio_pool.shutdown(wait=False)
        _audio_pool = None
