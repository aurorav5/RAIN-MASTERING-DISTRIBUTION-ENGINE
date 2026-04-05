"""Unit tests for backend.app.services.aie_vector."""
from __future__ import annotations

import pytest

from app.services.aie_vector import (
    VECTOR_DIM,
    ObservationSource,
    new_zero_vector,
    genre_centroid_vector,
    extract_observation_from_params,
    apply_ema_update,
    META_AGGRESSIVE,
    META_LOUDNESS_PUSH,
    DYN_LOUDNESS,
    STEREO_WIDTH,
)


def test_new_zero_vector_has_64_zeros() -> None:
    v = new_zero_vector()
    assert len(v) == VECTOR_DIM == 64
    assert all(x == 0.0 for x in v)


def test_genre_centroid_metal_has_positive_loudness_push_and_aggressive() -> None:
    v = genre_centroid_vector("metal")
    assert len(v) == 64
    assert v[META_LOUDNESS_PUSH] > 0.0
    assert v[META_AGGRESSIVE] > 0.0


def test_genre_centroid_classical_has_opposite_signs() -> None:
    v = genre_centroid_vector("classical")
    assert len(v) == 64
    # Classical must have negative signs where metal had positive
    assert v[META_LOUDNESS_PUSH] < 0.0
    assert v[META_AGGRESSIVE] < 0.0


def test_genre_centroid_unknown_is_zero() -> None:
    v = genre_centroid_vector("notarealgenre")
    assert v == [0.0] * 64


def test_apply_ema_update_zeros_plus_ones() -> None:
    zeros = new_zero_vector()
    ones = [1.0] * 64
    out = apply_ema_update(zeros, ones, weight=1.0, alpha=0.9)
    # new = 0.9*0 + 0.1*(1.0*1.0 + 0.0*0) = 0.1
    assert all(abs(x - 0.1) < 1e-9 for x in out)


def test_extract_observation_target_lufs_maps_to_dim19() -> None:
    params = {"target_lufs": -14.0}
    v = extract_observation_from_params(params)
    # _norm_linear(-14, -24, -8) = 2*(10/16) - 1 = 0.25
    assert abs(v[DYN_LOUDNESS] - 0.25) < 1e-9


def test_extract_observation_stereo_width_maps_to_dim28() -> None:
    params = {"stereo_width": 1.5}
    v = extract_observation_from_params(params)
    # _norm_linear(1.5, 0, 2) = 2*(1.5/2) - 1 = 0.5
    assert abs(v[STEREO_WIDTH] - 0.5) < 1e-9


def test_observation_source_constants() -> None:
    src = ObservationSource()
    assert src.EXPLICIT == 1.0
    assert src.AI_ACCEPTED == 0.6
    assert src.IMPLICIT == 0.3
