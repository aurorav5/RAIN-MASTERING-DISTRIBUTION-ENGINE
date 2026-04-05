"""BPM estimation with librosa double-count correction.

Librosa's tempo estimators (`librosa.beat.tempo`, `beat_track`) consistently report
2x the true BPM on modern material by locking onto eighth/sixteenth-note subdivisions.
Never trust a raw librosa BPM value — always run it through `corrected_bpm()`.

For production-quality tempo in RAIN, this module also exposes a hook for
Essentia's RhythmExtractor2013 when available.
"""
from __future__ import annotations
from typing import Optional
import numpy as np
import structlog

logger = structlog.get_logger()


# Genre-realistic BPM envelope. Values outside this range almost always indicate
# octave error (subdivision double-count or half-time under-count).
BPM_FLOOR = 50.0
BPM_CEILING = 200.0
# "Expected" target range most music lives in — used as the anchor for folding.
EXPECTED_MIN = 60.0
EXPECTED_MAX = 170.0


def corrected_bpm(raw_bpm: float, reference_bpm: Optional[float] = None) -> float:
    """
    Apply octave-fold correction to a raw librosa BPM estimate.

    If `reference_bpm` is given (e.g. from an AIE centroid or user-declared target),
    choose whichever of {raw, raw/2, raw*2} is closest to the reference.

    Without a reference, fold into the EXPECTED range:
      - raw > EXPECTED_MAX          → prefer raw/2 if it lands in [EXPECTED_MIN, EXPECTED_MAX]
      - raw < EXPECTED_MIN          → prefer raw*2 if it lands in range
      - raw already in range        → keep as-is
    """
    if raw_bpm <= 0 or not np.isfinite(raw_bpm):
        return 0.0

    candidates = [raw_bpm, raw_bpm / 2.0, raw_bpm * 2.0]

    if reference_bpm is not None and reference_bpm > 0:
        corrected = min(candidates, key=lambda c: abs(c - reference_bpm))
        if corrected != raw_bpm:
            logger.debug(
                "bpm_folded_to_reference",
                raw=raw_bpm, reference=reference_bpm, corrected=corrected,
            )
        return corrected

    # No reference — fold into expected range
    in_range = [c for c in candidates if EXPECTED_MIN <= c <= EXPECTED_MAX]
    if in_range:
        # Prefer the one closest to the genre median (110 BPM is a reasonable global median)
        chosen = min(in_range, key=lambda c: abs(c - 110.0))
    else:
        # All candidates out of range — clamp to nearest bound
        chosen = min(candidates, key=lambda c: min(abs(c - BPM_FLOOR), abs(c - BPM_CEILING)))

    if chosen != raw_bpm:
        logger.info("bpm_corrected", raw=raw_bpm, corrected=chosen)
    return chosen


def estimate_bpm_librosa(
    samples: np.ndarray,
    sample_rate: int,
    reference_bpm: Optional[float] = None,
) -> tuple[float, float]:
    """
    Estimate BPM using librosa, apply correction. Returns (corrected_bpm, raw_bpm).
    Pass `reference_bpm` from AIE or track metadata when available.
    """
    import librosa

    if samples.ndim == 2:
        samples = samples.mean(axis=1)  # mono-sum

    onset_env = librosa.onset.onset_strength(y=samples.astype(np.float32), sr=sample_rate)
    tempo_value = librosa.beat.tempo(onset_envelope=onset_env, sr=sample_rate)
    raw = float(tempo_value[0]) if len(tempo_value) > 0 else 0.0
    corrected = corrected_bpm(raw, reference_bpm=reference_bpm)
    return corrected, raw


def estimate_bpm_essentia(samples: np.ndarray, sample_rate: int) -> float:
    """
    Preferred path when Essentia is available. RhythmExtractor2013 is onset-based
    and does not exhibit the librosa octave-doubling failure mode.
    Raises RAIN-E810 if Essentia is not installed.
    """
    try:
        import essentia.standard as es  # type: ignore
    except ImportError as exc:
        raise RuntimeError("RAIN-E810: essentia not available for BPM estimation") from exc

    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    # Essentia expects float32 mono
    extractor = es.RhythmExtractor2013(method="multifeature")
    bpm, _beats, _confidence, _estimates, _bpm_intervals = extractor(samples.astype(np.float32))
    return float(bpm)
