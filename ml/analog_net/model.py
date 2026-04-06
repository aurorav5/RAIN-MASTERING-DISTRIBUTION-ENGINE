"""AnalogNet: lightweight 1D CNN for analog saturation curve modeling."""
import torch
import torch.nn as nn


class AnalogNet(nn.Module):
    SATURATION_MODES: list[str] = ["tape", "transistor", "tube"]

    def __init__(self) -> None:
        super().__init__()
        self.backbone = nn.Sequential(
            nn.Conv1d(1, 64, 7, padding=3), nn.GELU(),
            nn.Conv1d(64, 128, 5, padding=2), nn.GELU(),
            nn.Conv1d(128, 128, 3, padding=1), nn.GELU(),
        )
        # Three output heads: one per saturation mode, 128-point gain curve each
        self.heads = nn.ModuleList([
            nn.Conv1d(128, 1, 1) for _ in self.SATURATION_MODES
        ])

    def forward(self, freq_features: torch.Tensor) -> list[torch.Tensor]:
        # freq_features: [B, 1, 128]
        x = self.backbone(freq_features)
        return [head(x).squeeze(1) for head in self.heads]  # 3x [B, 128]
