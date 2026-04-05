"""BS-RoFormer cascaded separation engine wrapper.

This module wraps the actual BS-RoFormer / MelBand RoFormer inference calls
used by the RAIN 12-stem separation pipeline.

The underlying inference is intended to be performed with the ZFTurbo
training / inference repo:
    https://github.com/ZFTurbo/Music-Source-Separation-Training

TODO (RAIN-SEP-INT):
- Import the ZFTurbo inference scaffolding (configs + utils.demix) once the
  BS-RoFormer checkpoints are provisioned into /models/.
- Replace each `_guarded_call` with an actual model.demix(...) invocation.
- Wire the LarsNet / DrumSep and anvuew dereverb MelBand RoFormer checkpoints
  into a shared loader (each pass uses a distinct checkpoint).

Expected tensor conventions
---------------------------
All audio buffers passed into / out of this module are numpy float32 arrays
with shape (channels, samples) and sample_rate == 44100 Hz, matching the
BS-RoFormer training configuration. Mono inputs must be broadcast to
(2, samples) by the caller before invocation.

Pass layout (cascade)
---------------------
Pass 1  BS-RoFormer SW                -> vocals, drums, bass, guitar, piano, other   (6 stems)
Pass 2  MVSep Karaoke BS-RoFormer     -> lead_vocals, backing_vocals                  (from pass-1 vocals)
Pass 3  LarsNet / DrumSep             -> kick, snare, hats, percussion                (from pass-1 drums)
Pass 4  anvuew dereverb MelBand RoFormer -> room; residual -> fx_other                (from pass-1 other)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings


_SR_EXPECTED = 44100


def _assert_ready(error_code: str, detail: str) -> None:
    """Raise NotImplementedError unless separation is enabled and a checkpoint exists on disk."""
    if not settings.SEPARATION_ENABLED:
        raise NotImplementedError(
            f"{error_code}: BS-RoFormer model not integrated — SEPARATION_ENABLED is False ({detail})"
        )
    if not Path(settings.BSROFORMER_MODEL_PATH).exists():
        raise NotImplementedError(
            f"{error_code}: BS-RoFormer model not integrated — checkpoint required at "
            f"{settings.BSROFORMER_MODEL_PATH} ({detail})"
        )


def load_bsroformer_model(checkpoint_path: str, device: str) -> object:
    """Load a BS-RoFormer / MelBand RoFormer checkpoint from disk.

    Args:
        checkpoint_path: filesystem path to the .ckpt / .pt weights
        device: torch device string (e.g. "cuda:0", "cpu")

    Returns:
        An opaque model handle understood by the `run_pass_*` functions below.

    Raises:
        NotImplementedError: RAIN-E620 — integration pending / checkpoint missing.
    """
    # TODO(RAIN-SEP-INT): construct the ZFTurbo model class per the YAML config,
    # load the state dict, move to `device`, set eval mode.
    _assert_ready("RAIN-E620", f"load_bsroformer_model path={checkpoint_path} device={device}")
    raise NotImplementedError(
        "RAIN-E620: BS-RoFormer model not integrated — checkpoint required"
    )


def run_pass_1_6stem(model: Any, audio: np.ndarray, sr: int) -> dict[str, np.ndarray]:
    """Pass 1 — BS-RoFormer SW separating a full mix into 6 high-level stems.

    Args:
        model: loaded BS-RoFormer SW handle
        audio: np.ndarray shape (2, samples), float32, 44.1 kHz
        sr:    sample rate (must be 44100)

    Returns:
        dict with keys: vocals, drums, bass, guitar, piano, other
        each value is np.ndarray shape (2, samples), float32.
    """
    # TODO(RAIN-SEP-INT): call ZFTurbo demix() with the 6-stem BS-RoFormer SW config,
    # return the stem dict aligned to the canonical stem names above.
    _assert_ready("RAIN-E621", f"run_pass_1_6stem sr={sr} shape={getattr(audio, 'shape', None)}")
    raise NotImplementedError(
        "RAIN-E621: BS-RoFormer model not integrated — checkpoint required"
    )


def run_pass_2_karaoke(
    model: Any, vocals: np.ndarray, sr: int
) -> tuple[np.ndarray, np.ndarray]:
    """Pass 2 — MVSep Karaoke BS-RoFormer splitting vocals into lead/backing.

    Args:
        model: loaded Karaoke BS-RoFormer handle
        vocals: np.ndarray shape (2, samples), the vocals stem from pass 1
        sr: sample rate (must be 44100)

    Returns:
        (lead_vocals, backing_vocals) — each np.ndarray shape (2, samples).
    """
    # TODO(RAIN-SEP-INT): invoke the MVSep Karaoke BS-RoFormer checkpoint on the
    # pass-1 vocals. Lead is the primary singer; backing is harmony / doubles.
    _assert_ready("RAIN-E621", f"run_pass_2_karaoke sr={sr} shape={getattr(vocals, 'shape', None)}")
    raise NotImplementedError(
        "RAIN-E621: BS-RoFormer model not integrated — checkpoint required"
    )


def run_pass_3_drums(model: Any, drums: np.ndarray, sr: int) -> dict[str, np.ndarray]:
    """Pass 3 — LarsNet / DrumSep splitting the drum bus into per-piece stems.

    Args:
        model: loaded LarsNet / DrumSep handle
        drums: np.ndarray shape (2, samples), the drums stem from pass 1
        sr: sample rate (must be 44100)

    Returns:
        dict with keys: kick, snare, hats, percussion — each np.ndarray (2, samples).
    """
    # TODO(RAIN-SEP-INT): run LarsNet (or the equivalent DrumSep BS-RoFormer variant)
    # on the pass-1 drums bus; map the model outputs to kick/snare/hats/percussion.
    _assert_ready("RAIN-E621", f"run_pass_3_drums sr={sr} shape={getattr(drums, 'shape', None)}")
    raise NotImplementedError(
        "RAIN-E621: BS-RoFormer model not integrated — checkpoint required"
    )


def run_pass_4_dereverb(
    model: Any, other: np.ndarray, sr: int
) -> tuple[np.ndarray, np.ndarray]:
    """Pass 4 — anvuew dereverb MelBand RoFormer splitting room from residual FX.

    Args:
        model: loaded anvuew dereverb MelBand RoFormer handle
        other: np.ndarray shape (2, samples), the "other" stem from pass 1
        sr: sample rate (must be 44100)

    Returns:
        (room, fx_other) — room is extracted reverb/ambience; fx_other is the
        residual non-reverb content (i.e. dry_other = other - room).
    """
    # TODO(RAIN-SEP-INT): run anvuew dereverb MelBand RoFormer; the model outputs
    # the wet reverb component (room). Residual fx_other is computed as the
    # difference: fx_other = other - room.
    _assert_ready("RAIN-E621", f"run_pass_4_dereverb sr={sr} shape={getattr(other, 'shape', None)}")
    raise NotImplementedError(
        "RAIN-E621: BS-RoFormer model not integrated — checkpoint required"
    )
