import torch
import torch.nn as nn
from typing import Optional


# Saturation mode encoding: float index to string label
_SATURATION_MODES: list[str] = ["tape", "tube", "transistor"]


class MelSpecEncoder(nn.Module):
    def __init__(self, output_dim: int = 256) -> None:
        super().__init__()
        self.convs = nn.Sequential(
            nn.Conv2d(1, 128, 3, padding=1), nn.GELU(), nn.LayerNorm([128, 128, 128]),
            nn.Conv2d(128, 256, 3, padding=1, stride=2), nn.GELU(),
            nn.Conv2d(256, 256, 3, padding=1, stride=2), nn.GELU(),
        )
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.proj = nn.Linear(256, output_dim)

    def forward(self, mel: torch.Tensor) -> torch.Tensor:
        # mel: [B, 1, 128, 128]
        x = self.convs(mel)
        x = self.pool(x).squeeze(-1).squeeze(-1)
        return self.proj(x)


class RainNetV2(nn.Module):
    """
    RainNet v2 -- predicts 46 raw parameters that decode into the canonical
    ProcessingParams schema (CLAUDE.md).

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
        [39-45]   macro controls: brighten, glue, width, punch, warmth, space, repair
                                               -- sigmoid*10 -> [0.0, 10.0]
    """

    N_PARAMS: int = 46

    def __init__(
        self,
        d_model: int = 256,
        n_heads: int = 8,
        n_layers: int = 4,
        n_genres: int = 87,
        n_platforms: int = 8,
    ) -> None:
        super().__init__()
        self.d_model = d_model
        self.mel_encoder = MelSpecEncoder(d_model)
        self.artist_proj = nn.Sequential(nn.Linear(64, d_model), nn.GELU())
        self.genre_embed = nn.Sequential(nn.Embedding(n_genres, 64), nn.Linear(64, d_model))
        self.platform_embed = nn.Sequential(nn.Embedding(n_platforms, 32), nn.Linear(32, d_model))
        self.mode_proj = nn.Sequential(nn.Linear(1, 32), nn.GELU(), nn.Linear(32, d_model))
        self.cls_token = nn.Parameter(torch.randn(1, 1, d_model))
        self.pos_embed = nn.Parameter(torch.randn(1, 6, d_model))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=1024,
            activation="gelu", batch_first=True, norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.decoder = nn.Sequential(
            nn.Linear(d_model, 512), nn.GELU(),
            nn.Linear(512, 256), nn.GELU(),
            nn.Linear(256, self.N_PARAMS),
        )

    def forward(
        self,
        mel: torch.Tensor,           # [B, 1, 128, 128]
        artist_vec: torch.Tensor,    # [B, 64]
        genre_id: torch.Tensor,      # [B] int64
        platform_id: torch.Tensor,   # [B] int64
        simple_mode: torch.Tensor,   # [B, 1] float32
    ) -> torch.Tensor:
        B = mel.shape[0]
        mel_tok = self.mel_encoder(mel).unsqueeze(1)
        art_tok = self.artist_proj(artist_vec).unsqueeze(1)
        gen_tok = self.genre_embed(genre_id).unsqueeze(1)
        plt_tok = self.platform_embed(platform_id).unsqueeze(1)
        mod_tok = self.mode_proj(simple_mode).unsqueeze(1)
        cls = self.cls_token.expand(B, -1, -1)
        tokens = torch.cat([cls, mel_tok, art_tok, gen_tok, plt_tok, mod_tok], dim=1)
        tokens = tokens + self.pos_embed
        out = self.transformer(tokens)
        cls_out = out[:, 0, :]
        return self.decoder(cls_out)

    def decode_params(self, raw: torch.Tensor) -> dict:
        """
        Convert raw model output [46] to a complete ProcessingParams dict.
        Every field from the canonical schema is present -- no optional keys.
        """
        p = raw.squeeze(0)

        # --- Loudness target ---
        # sigmoid -> [0,1] -> scale to [-24, -8]
        target_lufs = float(torch.sigmoid(p[0]) * 16.0 - 24.0)
        # sigmoid -> [0,1] -> scale to [-6, 0]
        true_peak_ceiling = float(torch.sigmoid(p[1]) * 6.0 - 6.0)

        # --- Multiband dynamics (12 params) ---
        mb_threshold_low = float(torch.sigmoid(p[2]) * -40.0)
        mb_threshold_mid = float(torch.sigmoid(p[3]) * -40.0)
        mb_threshold_high = float(torch.sigmoid(p[4]) * -40.0)

        mb_ratio_low = float(torch.clamp(nn.functional.softplus(p[5]) + 1.0, min=1.0, max=20.0))
        mb_ratio_mid = float(torch.clamp(nn.functional.softplus(p[6]) + 1.0, min=1.0, max=20.0))
        mb_ratio_high = float(torch.clamp(nn.functional.softplus(p[7]) + 1.0, min=1.0, max=20.0))

        mb_attack_low = float(torch.clamp(nn.functional.softplus(p[8]), min=0.1, max=100.0))
        mb_attack_mid = float(torch.clamp(nn.functional.softplus(p[9]), min=0.1, max=100.0))
        mb_attack_high = float(torch.clamp(nn.functional.softplus(p[10]), min=0.1, max=100.0))

        mb_release_low = float(torch.clamp(nn.functional.softplus(p[11]) * 10.0, min=1.0, max=500.0))
        mb_release_mid = float(torch.clamp(nn.functional.softplus(p[12]) * 10.0, min=1.0, max=500.0))
        mb_release_high = float(torch.clamp(nn.functional.softplus(p[13]) * 10.0, min=1.0, max=500.0))

        # --- EQ gains (8 bands) ---
        eq_gains = [float(torch.tanh(p[14 + i]) * 12.0) for i in range(8)]

        # --- Analog saturation (3 params) ---
        analog_saturation = bool(torch.sigmoid(p[22]).item() > 0.5)
        saturation_drive = float(torch.sigmoid(p[23]))
        # 3-class softmax over [24..26] -> argmax selects mode
        sat_logits = p[24:27]
        saturation_mode = _SATURATION_MODES[int(torch.argmax(sat_logits).item())]

        # --- Mid/Side processing (4 params) ---
        ms_enabled = bool(torch.sigmoid(p[27]).item() > 0.5)
        mid_gain = float(torch.tanh(p[28]) * 6.0)
        side_gain = float(torch.tanh(p[29]) * 6.0)
        stereo_width = float(torch.sigmoid(p[30]) * 2.0)

        # --- SAIL (7 params) ---
        sail_enabled = bool(torch.sigmoid(p[31]).item() > 0.5)
        sail_stem_gains = [float(torch.tanh(p[32 + i]) * 3.0) for i in range(6)]

        # --- Vinyl mode (1 param) ---
        vinyl_mode = bool(torch.sigmoid(p[38]).item() > 0.5)

        # Override true_peak_ceiling for vinyl safety
        if vinyl_mode:
            true_peak_ceiling = min(true_peak_ceiling, -3.0)

        # --- Macro controls (7 params, indices 39-45) ---
        macro_brighten = float(torch.sigmoid(p[39]) * 10.0)
        macro_glue = float(torch.sigmoid(p[40]) * 10.0)
        macro_width = float(torch.sigmoid(p[41]) * 10.0)
        macro_punch = float(torch.sigmoid(p[42]) * 10.0)
        macro_warmth = float(torch.sigmoid(p[43]) * 10.0)
        macro_space = float(torch.sigmoid(p[44]) * 10.0)
        macro_repair = float(torch.sigmoid(p[45]) * 10.0)

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
