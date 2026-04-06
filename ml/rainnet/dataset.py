"""RainNetDataset — loads (audio_path, genre_label, platform_label, target_params) tuples.

Target vector is 46-dimensional, matching RainNetV2.N_PARAMS and the canonical
ProcessingParams schema (CLAUDE.md). Index layout matches model.py decode_params():

    [0]       target_lufs              sigmoid -> [-24, -8]
    [1]       true_peak_ceiling        sigmoid -> [-6, 0]
    [2-4]     mb_threshold_*           sigmoid -> [-40, 0]
    [5-7]     mb_ratio_*               softplus+1
    [8-10]    mb_attack_*              softplus
    [11-13]   mb_release_*             softplus*10
    [14-21]   eq_gains[8]              tanh*12
    [22]      analog_saturation        sigmoid -> bool
    [23]      saturation_drive         sigmoid
    [24-26]   saturation_mode logits   3-class (tape=0, tube=1, transistor=2)
    [27]      ms_enabled               sigmoid -> bool
    [28]      mid_gain                 tanh*6
    [29]      side_gain                tanh*6
    [30]      stereo_width             sigmoid*2
    [31]      sail_enabled             sigmoid -> bool
    [32-37]   sail_stem_gains[0:6]     tanh*3 (model outputs 6, padded to 12 in decode)
    [38]      vinyl_mode               sigmoid -> bool
    [39-45]   macros[7]                sigmoid*10
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import Dataset

_SAT_MODES = {"tape": 0, "tube": 1, "transistor": 2}


class RainNetDataset(Dataset):
    """Each sample is a JSON line with: audio_path, genre_label, platform_label, target_params."""

    def __init__(self, manifest_path: str, sr: int = 48000) -> None:
        self.samples: list[dict] = []
        self.sr = sr
        with open(manifest_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    self.samples.append(json.loads(line))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        sample = self.samples[idx]

        # Mel spectrogram — pre-computed .npy alongside audio
        mel_path = Path(sample["audio_path"]).with_suffix(".mel.npy")
        if mel_path.exists():
            mel = torch.from_numpy(np.load(str(mel_path))).float().unsqueeze(0)
        else:
            mel = torch.zeros(1, 128, 128)

        params = sample.get("target_params", {})
        pv = torch.zeros(46)  # 46-dim target vector

        if params:
            # [0-1] Loudness target
            pv[0] = params.get("target_lufs", -14.0)
            pv[1] = params.get("true_peak_ceiling", -1.0)

            # [2-4] Multiband thresholds
            pv[2] = params.get("mb_threshold_low", -18.0)
            pv[3] = params.get("mb_threshold_mid", -18.0)
            pv[4] = params.get("mb_threshold_high", -18.0)

            # [5-7] Multiband ratios
            pv[5] = params.get("mb_ratio_low", 2.5)
            pv[6] = params.get("mb_ratio_mid", 2.0)
            pv[7] = params.get("mb_ratio_high", 2.0)

            # [8-10] Attack
            pv[8] = params.get("mb_attack_low", 10.0)
            pv[9] = params.get("mb_attack_mid", 5.0)
            pv[10] = params.get("mb_attack_high", 2.0)

            # [11-13] Release
            pv[11] = params.get("mb_release_low", 150.0)
            pv[12] = params.get("mb_release_mid", 80.0)
            pv[13] = params.get("mb_release_high", 40.0)

            # [14-21] EQ gains
            eq = params.get("eq_gains", [0.0] * 8)
            for j in range(8):
                pv[14 + j] = eq[j] if j < len(eq) else 0.0

            # [22] Analog saturation (bool → float)
            pv[22] = 1.0 if params.get("analog_saturation", False) else 0.0

            # [23] Saturation drive
            pv[23] = params.get("saturation_drive", 0.0)

            # [24-26] Saturation mode (3-class one-hot logits)
            mode = params.get("saturation_mode", "tape")
            mode_idx = _SAT_MODES.get(mode, 0)
            pv[24 + mode_idx] = 3.0  # strong logit for target class

            # [27] M/S enabled
            pv[27] = 1.0 if params.get("ms_enabled", False) else 0.0

            # [28-30] Mid/Side + stereo
            pv[28] = params.get("mid_gain", 0.0)
            pv[29] = params.get("side_gain", 0.0)
            pv[30] = params.get("stereo_width", 1.0)

            # [31] SAIL enabled
            pv[31] = 1.0 if params.get("sail_enabled", False) else 0.0

            # [32-37] SAIL stem gains (6 from model output)
            # Model uses 6 neurons for sail at [32-37]; remaining 6 stems are
            # populated from separation output in production (not predicted by RainNet).
            sg = params.get("sail_stem_gains", [0.0] * 12)
            for j in range(min(6, len(sg))):
                pv[32 + j] = sg[j]  # only first 6 are model-predicted

            # [38] Vinyl mode
            pv[38] = 1.0 if params.get("vinyl_mode", False) else 0.0

            # [39-45] Macros (7)
            pv[39] = params.get("macro_brighten", 5.0)
            pv[40] = params.get("macro_glue", 5.0)
            pv[41] = params.get("macro_width", 5.0)
            pv[42] = params.get("macro_punch", 5.0)
            pv[43] = params.get("macro_warmth", 5.0)
            pv[44] = params.get("macro_space", 5.0)
            pv[45] = params.get("macro_repair", 0.0)

        return {
            "mel": mel,
            "artist_vec": torch.zeros(64),
            "genre_id": torch.tensor(sample.get("genre_label", 0), dtype=torch.long),
            "platform_id": torch.tensor(sample.get("platform_label", 0), dtype=torch.long),
            "simple_mode": torch.tensor([1.0]),  # shape (1,) — batched to (B, 1)
            "target_params": pv,
        }
