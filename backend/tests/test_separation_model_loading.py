"""
Separation model loading tests.

Verifies that _ensure_models_loaded loads the correct model type for each pass.
Since actual model files aren't available in test, we mock the load functions
and verify the correct loader is called for each pass.
"""
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("RAIN_ENV", "test")
os.environ.setdefault("SEPARATION_ENABLED", "true")


class TestSeparationModelLoading:
    def test_pass1_loads_bsroformer(self):
        """Pass 1 should use load_bsroformer_model."""
        from app.tasks.separation import _ensure_models_loaded, _SeparationTaskBase

        _SeparationTaskBase._pass1_model = None
        _SeparationTaskBase._pass2_model = "already_loaded"
        _SeparationTaskBase._pass4_model = "already_loaded"

        mock_model = {"model_type": "bs_roformer"}
        with patch("app.services.separation_engine.load_bsroformer_model", return_value=mock_model) as mock_load:
            _ensure_models_loaded("test.ckpt", "cpu")
            mock_load.assert_called_once_with("test.ckpt", "cpu")
            assert _SeparationTaskBase._pass1_model == mock_model

    def test_pass2_loads_karaoke(self):
        """Pass 2 should use load_karaoke_model, not load_bsroformer_model."""
        from app.tasks.separation import _ensure_models_loaded, _SeparationTaskBase

        _SeparationTaskBase._pass1_model = "already_loaded"
        _SeparationTaskBase._pass2_model = None
        _SeparationTaskBase._pass4_model = "already_loaded"

        mock_model = {"model_type": "mel_band_roformer"}
        with patch("app.services.separation_engine.load_bsroformer_model") as mock_bs, \
             patch("app.services.separation_engine.load_karaoke_model", return_value=mock_model) as mock_karaoke:
            _ensure_models_loaded("test.ckpt", "cpu")
            mock_bs.assert_not_called()
            mock_karaoke.assert_called_once_with("cpu")
            assert _SeparationTaskBase._pass2_model == mock_model

    def test_pass3_no_model(self):
        """Pass 3 uses spectral fallback — no model should be loaded."""
        from app.tasks.separation import _SeparationTaskBase

        # Pass 3 should remain None (spectral fallback)
        # The _ensure_models_loaded function should NOT set _pass3_model
        _SeparationTaskBase._pass3_model = None
        _SeparationTaskBase._pass1_model = "loaded"
        _SeparationTaskBase._pass2_model = "loaded"
        _SeparationTaskBase._pass4_model = "loaded"

        with patch("app.services.separation_engine.load_bsroformer_model") as mock_bs, \
             patch("app.services.separation_engine.load_karaoke_model") as mock_k, \
             patch("app.services.separation_engine.load_dereverb_model") as mock_d:
            from app.tasks.separation import _ensure_models_loaded
            _ensure_models_loaded("test.ckpt", "cpu")
            # None of the loaders should be called since 1, 2, 4 are already loaded
            mock_bs.assert_not_called()
            mock_k.assert_not_called()
            mock_d.assert_not_called()
            # Pass 3 model should still be None
            assert _SeparationTaskBase._pass3_model is None

    def test_pass4_loads_dereverb(self):
        """Pass 4 should use load_dereverb_model."""
        from app.tasks.separation import _ensure_models_loaded, _SeparationTaskBase

        _SeparationTaskBase._pass1_model = "already_loaded"
        _SeparationTaskBase._pass2_model = "already_loaded"
        _SeparationTaskBase._pass4_model = None

        mock_model = {"model_type": "mel_band_roformer"}
        with patch("app.services.separation_engine.load_dereverb_model", return_value=mock_model) as mock_dereverb:
            _ensure_models_loaded("test.ckpt", "cpu")
            mock_dereverb.assert_called_once_with("cpu")
            assert _SeparationTaskBase._pass4_model == mock_model
