"""RainNetDataset — loads (audio_path, genre_label, platform_label, target_params) tuples."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
import numpy as np
import torch
from torch.utils.data import Dataset


class RainNetDataset(Dataset):
    """
    Each sample: JSON manifest with keys:
        audio_path: str
        genre_label: int (0-86)
        platform_label: int (0-7)
        target_params: dict matching ProcessingParams schema
    """

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
        # Mel spectrogram extraction would use audio_analysis.extract_mel_spectrogram
        # For dataset loading, we expect pre-computed .npy files alongside audio
        mel_path = Path(sample["audio_path"]).with_suffix(".mel.npy")
        if mel_path.exists():
            mel = torch.from_numpy(np.load(str(mel_path))).float().unsqueeze(0)
        else:
            mel = torch.zeros(1, 128, 128)

        params = sample.get("target_params", {})
        param_vector = torch.zeros(32)

        # Populate parameter vector from manifest target_params dict
        # Order matches RainNetV2.decode_params output: multiband(12) + eq(8) + sat(2) + ms(4) + sail(6)
        if params:
            param_vector[0] = params.get("mb_threshold_low", -18.0)
            param_vector[1] = params.get("mb_threshold_mid", -18.0)
            param_vector[2] = params.get("mb_threshold_high", -18.0)
            param_vector[3] = params.get("mb_ratio_low", 2.5)
            param_vector[4] = params.get("mb_ratio_mid", 2.0)
            param_vector[5] = params.get("mb_ratio_high", 2.0)
            param_vector[6] = params.get("mb_attack_low", 10.0)
            param_vector[7] = params.get("mb_attack_mid", 5.0)
            param_vector[8] = params.get("mb_attack_high", 2.0)
            param_vector[9] = params.get("mb_release_low", 150.0)
            param_vector[10] = params.get("mb_release_mid", 80.0)
            param_vector[11] = params.get("mb_release_high", 40.0)
            eq_gains = params.get("eq_gains", [0.0] * 8)
            for j in range(8):
                param_vector[12 + j] = eq_gains[j] if j < len(eq_gains) else 0.0
            param_vector[20] = 1.0 if params.get("analog_saturation", False) else 0.0
            param_vector[21] = params.get("saturation_drive", 0.0)
            param_vector[22] = 1.0 if params.get("ms_enabled", False) else 0.0
            param_vector[23] = params.get("mid_gain", 0.0)
            param_vector[24] = params.get("side_gain", 0.0)
            param_vector[25] = params.get("stereo_width", 1.0)
            param_vector[26] = 1.0 if params.get("sail_enabled", False) else 0.0
            stem_gains = params.get("sail_stem_gains", [0.0] * 5)
            for j in range(5):
                param_vector[27 + j] = stem_gains[j] if j < len(stem_gains) else 0.0

        return {
            "mel": mel,
            "artist_vec": torch.zeros(64),
            "genre_id": torch.tensor(sample.get("genre_label", 0), dtype=torch.long),
            "platform_id": torch.tensor(sample.get("platform_label", 0), dtype=torch.long),
            "simple_mode": torch.tensor([[1.0]]),
            "target_params": param_vector,
        }
