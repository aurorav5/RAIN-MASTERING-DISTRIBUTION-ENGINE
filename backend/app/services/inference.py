"""
RainNet inference service.
RAIN_NORMALIZATION_VALIDATED gate is enforced here.
When gate=false: heuristic fallback is mandatory. No inference runs.
"""
import time
from typing import Optional
import numpy as np
import structlog

logger = structlog.get_logger()


_SATURATION_MODES: list[str] = ["tape", "tube", "transistor"]


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -88.0, 88.0)))


def _softplus(x: np.ndarray) -> np.ndarray:
    return np.log1p(np.exp(np.clip(x, -88.0, 88.0)))


def _decode_params(raw: np.ndarray) -> dict:
    """
    Convert raw ONNX output vector (46 neurons) to ProcessingParams dict.
    Layout mirrors RainNetV2.decode_params() in ml/rainnet/model.py exactly.

    Raw output layout (46 neurons):
        [0]       target_lufs                  -- sigmoid -> [-24.0, -8.0]
        [1]       true_peak_ceiling            -- sigmoid -> [-6.0, 0.0]
        [2-4]     mb_threshold_low/mid/high    -- sigmoid -> [-40.0, 0.0]
        [5-7]     mb_ratio_low/mid/high        -- softplus+1 -> [1.0, 20.0]
        [8-10]    mb_attack_low/mid/high       -- softplus -> ms
        [11-13]   mb_release_low/mid/high      -- softplus*10 -> ms
        [14-21]   eq_gains[0..7]               -- tanh*12 -> [-12.0, +12.0] dB
        [22]      analog_saturation            -- sigmoid -> bool threshold 0.5
        [23]      saturation_drive             -- sigmoid -> [0.0, 1.0]
        [24-26]   saturation_mode logits       -- argmax -> tape/tube/transistor
        [27]      ms_enabled                   -- sigmoid -> bool threshold 0.5
        [28]      mid_gain                     -- tanh*6 -> [-6.0, +6.0] dB
        [29]      side_gain                    -- tanh*6 -> [-6.0, +6.0] dB
        [30]      stereo_width                 -- sigmoid*2 -> [0.0, 2.0]
        [31]      sail_enabled                 -- sigmoid -> bool threshold 0.5
        [32-37]   sail_stem_gains[0..5]        -- tanh*3 -> [-3.0, +3.0] dB
        [38]      vinyl_mode                   -- sigmoid -> bool threshold 0.5
        [39-45]   macro controls               -- sigmoid*10 -> [0.0, 10.0]
    """
    # Loudness target
    target_lufs = float(_sigmoid(raw[0]) * 16.0 - 24.0)
    true_peak_ceiling = float(_sigmoid(raw[1]) * 6.0 - 6.0)

    # Multiband dynamics
    mb_threshold_low = float(_sigmoid(raw[2]) * -40.0)
    mb_threshold_mid = float(_sigmoid(raw[3]) * -40.0)
    mb_threshold_high = float(_sigmoid(raw[4]) * -40.0)

    mb_ratio_low = float(np.clip(_softplus(raw[5]) + 1.0, 1.0, 20.0))
    mb_ratio_mid = float(np.clip(_softplus(raw[6]) + 1.0, 1.0, 20.0))
    mb_ratio_high = float(np.clip(_softplus(raw[7]) + 1.0, 1.0, 20.0))

    mb_attack_low = float(np.clip(_softplus(raw[8]), 0.1, 100.0))
    mb_attack_mid = float(np.clip(_softplus(raw[9]), 0.1, 100.0))
    mb_attack_high = float(np.clip(_softplus(raw[10]), 0.1, 100.0))

    mb_release_low = float(np.clip(_softplus(raw[11]) * 10.0, 1.0, 500.0))
    mb_release_mid = float(np.clip(_softplus(raw[12]) * 10.0, 1.0, 500.0))
    mb_release_high = float(np.clip(_softplus(raw[13]) * 10.0, 1.0, 500.0))

    # EQ gains (8 bands)
    eq_gains = [float(np.tanh(raw[14 + i]) * 12.0) for i in range(8)]

    # Analog saturation
    analog_saturation = bool(_sigmoid(raw[22]) > 0.5)
    saturation_drive = float(_sigmoid(raw[23]))
    sat_logits = raw[24:27]
    saturation_mode = _SATURATION_MODES[int(np.argmax(sat_logits))]

    # Mid/Side processing
    ms_enabled = bool(_sigmoid(raw[27]) > 0.5)
    mid_gain = float(np.tanh(raw[28]) * 6.0)
    side_gain = float(np.tanh(raw[29]) * 6.0)
    stereo_width = float(_sigmoid(raw[30]) * 2.0)

    # SAIL
    sail_enabled = bool(_sigmoid(raw[31]) > 0.5)
    sail_stem_gains = [float(np.tanh(raw[32 + i]) * 3.0) for i in range(6)]

    # Vinyl mode
    vinyl_mode = bool(_sigmoid(raw[38]) > 0.5)

    # Override true_peak_ceiling for vinyl safety
    if vinyl_mode:
        true_peak_ceiling = min(true_peak_ceiling, -3.0)

    # Macro controls
    macro_brighten = float(_sigmoid(raw[39]) * 10.0)
    macro_glue = float(_sigmoid(raw[40]) * 10.0)
    macro_width = float(_sigmoid(raw[41]) * 10.0)
    macro_punch = float(_sigmoid(raw[42]) * 10.0)
    macro_warmth = float(_sigmoid(raw[43]) * 10.0)
    macro_space = float(_sigmoid(raw[44]) * 10.0)
    macro_repair = float(_sigmoid(raw[45]) * 10.0)

    return {
        # Loudness target
        "target_lufs": target_lufs,
        "true_peak_ceiling": true_peak_ceiling,
        # Multiband dynamics
        "mb_threshold_low": mb_threshold_low,
        "mb_threshold_mid": mb_threshold_mid,
        "mb_threshold_high": mb_threshold_high,
        "mb_ratio_low": mb_ratio_low,
        "mb_ratio_mid": mb_ratio_mid,
        "mb_ratio_high": mb_ratio_high,
        "mb_attack_low": mb_attack_low,
        "mb_attack_mid": mb_attack_mid,
        "mb_attack_high": mb_attack_high,
        "mb_release_low": mb_release_low,
        "mb_release_mid": mb_release_mid,
        "mb_release_high": mb_release_high,
        # EQ
        "eq_gains": eq_gains,
        # Analog saturation
        "analog_saturation": analog_saturation,
        "saturation_drive": saturation_drive,
        "saturation_mode": saturation_mode,
        # Mid/Side
        "ms_enabled": ms_enabled,
        "mid_gain": mid_gain,
        "side_gain": side_gain,
        "stereo_width": stereo_width,
        # SAIL
        "sail_enabled": sail_enabled,
        "sail_stem_gains": sail_stem_gains,
        # Vinyl
        "vinyl_mode": vinyl_mode,
        # Macro controls
        "macro_brighten": macro_brighten,
        "macro_glue": macro_glue,
        "macro_width": macro_width,
        "macro_punch": macro_punch,
        "macro_warmth": macro_warmth,
        "macro_space": macro_space,
        "macro_repair": macro_repair,
    }


class InferenceService:
    _instance: Optional["InferenceService"] = None
    _session = None  # ort.InferenceSession when loaded

    @classmethod
    def get(cls) -> "InferenceService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._load_model()

    def _load_model(self) -> None:
        from pathlib import Path
        from app.core.config import settings
        model_path = Path(settings.ONNX_MODEL_PATH)
        if not model_path.exists():
            logger.warning("rainnet_model_not_found", path=str(model_path))
            return
        try:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            self._session = ort.InferenceSession(
                str(model_path),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            logger.info("rainnet_loaded", path=str(model_path))
        except Exception as e:
            logger.error("rainnet_load_failed", error=str(e), error_code="RAIN-E401")

    def predict(
        self,
        mel_spectrogram: np.ndarray,
        artist_vector: np.ndarray,
        genre_id: int,
        platform_id: int,
        simple_mode: bool,
    ) -> Optional[dict]:
        """Returns ProcessingParams dict or None if gate blocked / inference failed."""
        from app.core.config import settings

        if not settings.RAIN_NORMALIZATION_VALIDATED:
            logger.info(
                "rainnet_blocked_by_gate",
                error_code="RAIN-E400",
                message="RAIN_NORMALIZATION_VALIDATED=false — heuristic fallback active",
            )
            return None

        if self._session is None:
            logger.error("rainnet_model_unavailable", error_code="RAIN-E401")
            return None

        t0 = time.time()
        try:
            outputs = self._session.run(
                ["params_raw"],
                {
                    "mel":          mel_spectrogram[np.newaxis, np.newaxis].astype(np.float32),
                    "artist_vec":   artist_vector[np.newaxis].astype(np.float32),
                    "genre_id":     np.array([genre_id], dtype=np.int64),
                    "platform_id":  np.array([platform_id], dtype=np.int64),
                    "simple_mode":  np.array([[1.0 if simple_mode else 0.0]], dtype=np.float32),
                },
            )
            elapsed = time.time() - t0
            duration_ms = int(elapsed * 1000)
            logger.info("rainnet_inference_complete", stage="inference", duration_ms=duration_ms)
            if elapsed > 2.0:
                logger.warning("rainnet_slow_inference", elapsed_s=round(elapsed, 3), duration_ms=duration_ms, error_code="RAIN-E402")
            return _decode_params(outputs[0][0])

        except Exception as e:
            logger.error("rainnet_inference_error", error=str(e), error_code="RAIN-E402")
            return None

    PLATFORM_ID_MAP: dict[str, int] = {
        "spotify": 0, "apple_music": 1, "youtube": 2, "tidal": 3,
        "amazon_music": 4, "tiktok": 5, "soundcloud": 6, "vinyl": 7,
    }

    def get_params(
        self,
        mel_spectrogram: np.ndarray,
        artist_vector: np.ndarray,
        genre: Optional[str],
        platform: str,
        simple_mode: bool,
    ) -> tuple[dict, str]:
        """
        Returns (params_dict, source) where source is 'rainnet' or 'heuristic'.
        Never raises. Always returns a valid full ProcessingParams dict.
        """
        from ml.rainnet.heuristics import get_heuristic_params, PLATFORM_LUFS

        platform_id = self.PLATFORM_ID_MAP.get(platform, 0)

        # Cold-start check: zero artist vector means no sessions yet
        if artist_vector is not None and np.all(np.abs(artist_vector) < 1e-8):
            from ml.rainnet.heuristics import get_heuristic_params
            params = get_heuristic_params(genre or "default", platform or "spotify")
            return params, "heuristic_cold_start"

        result = self.predict(mel_spectrogram, artist_vector, 0, platform_id, simple_mode)
        if result is None:
            vinyl = platform == "vinyl"
            params = get_heuristic_params(genre, platform, vinyl=vinyl)
            return params, "heuristic"

        # Patch platform-dependent fields that are not predicted
        result["target_lufs"] = PLATFORM_LUFS.get(platform, -14.0)
        result["true_peak_ceiling"] = -3.0 if platform == "vinyl" else -1.0
        result["vinyl_mode"] = platform == "vinyl"
        return result, "rainnet"
