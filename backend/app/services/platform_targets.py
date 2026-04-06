"""
RAIN Platform Loudness Targets — 27 platforms per RAIN-PLATFORM-SPEC-v1.0

Each target defines: integrated LUFS, true peak ceiling (dBTP), and notes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformTarget:
    name: str
    slug: str
    target_lufs: float
    true_peak_ceiling: float
    lra_min: float | None = None  # Minimum LRA (vinyl)
    lra_max: float | None = None  # Maximum LRA (broadcast)
    notes: str = ""


PLATFORM_TARGETS: dict[str, PlatformTarget] = {
    # Tier 1 — Major streaming
    "spotify": PlatformTarget("Spotify", "spotify", -14.0, -1.0, notes="Default target for most releases"),
    "spotify_loud": PlatformTarget("Spotify (Loud)", "spotify_loud", -11.0, -1.0, notes="For genres that benefit from louder masters"),
    "apple_music": PlatformTarget("Apple Music (Stereo)", "apple_music", -16.0, -1.0, notes="SoundCheck normalization"),
    "apple_music_spatial": PlatformTarget("Apple Music (Spatial)", "apple_music_spatial", -16.0, -1.0, notes="Spatial content earns up to 10% higher royalty"),
    "dolby_atmos": PlatformTarget("Dolby Atmos Music", "dolby_atmos", -18.0, -1.0, notes="Internal normalization by renderer"),
    "youtube": PlatformTarget("YouTube", "youtube", -14.0, -1.0, notes="Volume normalization on upload"),
    "youtube_music": PlatformTarget("YouTube Music", "youtube_music", -14.0, -1.0, notes="Same as YouTube"),
    "tidal": PlatformTarget("Tidal HiFi", "tidal", -14.0, -1.0, notes="Volume normalization, lossless delivery"),
    "amazon_music": PlatformTarget("Amazon Music HD", "amazon_music", -14.0, -2.0, notes="Volume normalization"),
    "amazon_ultra_hd": PlatformTarget("Amazon Music Ultra HD", "amazon_ultra_hd", -14.0, -1.0, notes="24-bit lossless"),

    # Tier 2 — Secondary streaming
    "deezer": PlatformTarget("Deezer", "deezer", -15.0, -1.0, notes="ReplayGain normalization"),
    "soundcloud": PlatformTarget("SoundCloud", "soundcloud", -14.0, -1.0, notes="Loudness normalization since 2021"),
    "pandora": PlatformTarget("Pandora", "pandora", -14.0, -1.0, notes="Volume normalization"),
    "tiktok": PlatformTarget("TikTok", "tiktok", -14.0, -1.0, notes="Short-form optimized"),
    "instagram": PlatformTarget("Instagram/Facebook", "instagram", -14.0, -1.0, notes="Reels and Stories"),

    # Tier 3 — Physical & broadcast
    "cd": PlatformTarget("CD / Club Play", "cd", -9.0, -0.3, notes="No normalization applied"),
    "vinyl": PlatformTarget("Vinyl Pre-Master", "vinyl", -14.0, -1.0, lra_min=8.0, notes="LRA must be at least 8 LU"),
    "broadcast_ebu": PlatformTarget("Broadcast (EBU R128)", "broadcast_ebu", -23.0, -1.0, lra_max=20.0, notes="LRA must not exceed 20 LU"),
    "broadcast_atsc": PlatformTarget("Broadcast (ATSC A/85)", "broadcast_atsc", -24.0, -2.0, notes="US broadcast standard"),

    # Tier 4 — Specialty
    "audiobook_acx": PlatformTarget("Audiobook (ACX)", "audiobook_acx", -20.0, -3.0, notes="Range -18 to -23 LUFS, -3 dBTP"),
    "podcast": PlatformTarget("Podcast", "podcast", -16.0, -1.0, notes="Conversational loudness"),
    "game_audio": PlatformTarget("Game Audio", "game_audio", -18.0, -1.0, notes="Headroom for dynamic mixing"),

    # Tier 5 — Niche/regional
    "qobuz": PlatformTarget("Qobuz", "qobuz", -14.0, -1.0, notes="Hi-res lossless"),
    "anghami": PlatformTarget("Anghami", "anghami", -14.0, -1.0, notes="MENA region"),
    "jiosaavn": PlatformTarget("JioSaavn", "jiosaavn", -14.0, -1.0, notes="India"),
    "boomplay": PlatformTarget("Boomplay", "boomplay", -14.0, -1.0, notes="Africa"),
    "netease": PlatformTarget("NetEase Cloud Music", "netease", -14.0, -1.0, notes="China"),
}


def get_platform_target(slug: str) -> PlatformTarget:
    """Get platform target by slug. Falls back to Spotify defaults."""
    return PLATFORM_TARGETS.get(slug, PLATFORM_TARGETS["spotify"])


def list_platform_targets() -> list[dict]:
    """Return all platform targets as dicts for API response."""
    return [
        {
            "slug": t.slug,
            "name": t.name,
            "target_lufs": t.target_lufs,
            "true_peak_ceiling": t.true_peak_ceiling,
            "lra_min": t.lra_min,
            "lra_max": t.lra_max,
            "notes": t.notes,
        }
        for t in PLATFORM_TARGETS.values()
    ]
