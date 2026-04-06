#!/usr/bin/env python3
"""Download and verify all neural model checkpoints for RAIN.

Uses the openmirlab pip packages (bs-roformer-infer, melband-roformer-infer)
which auto-manage checkpoints via MODEL_REGISTRY.

Usage:
    pip install bs-roformer-infer melband-roformer-infer
    python scripts/download_models.py

After running, set SEPARATION_ENABLED=true in your .env to enable separation.
"""
from __future__ import annotations

import sys
import os
import subprocess

# Add backend to path so we can import app config
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "backend"))


def check_package(name: str) -> bool:
    try:
        __import__(name.replace("-", "_"))
        return True
    except ImportError:
        return False


def install_packages():
    """Install the separation packages if missing."""
    packages = ["bs-roformer-infer", "melband-roformer-infer"]
    for pkg in packages:
        if not check_package(pkg):
            print(f"Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])


def download_bs_roformer():
    """Download BS-RoFormer SW 6-stem model."""
    from bs_roformer import MODEL_REGISTRY

    slug = "roformer-model-bs-roformer-sw-by-jarredou"
    print(f"\n[1/3] Downloading BS-RoFormer SW ({slug})...")
    try:
        MODEL_REGISTRY.download(slug)
        entry = MODEL_REGISTRY.get(slug)
        print(f"  -> Config: models/{entry.slug}/{entry.config}")
        print(f"  -> Checkpoint: models/{entry.slug}/{entry.checkpoint}")
        print(f"  -> Stems: vocals, drums, bass, guitar, piano, other (6-stem)")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def download_karaoke():
    """Download MVSep Karaoke model for vocal lead/backing split."""
    from mel_band_roformer import MODEL_REGISTRY

    slug = "roformer-model-mel-roformer-karaoke-aufr33-viperx"
    print(f"\n[2/3] Downloading Karaoke MelBand RoFormer ({slug})...")
    try:
        MODEL_REGISTRY.download(slug)
        entry = MODEL_REGISTRY.get(slug)
        print(f"  -> Config: models/{entry.slug}/{entry.config}")
        print(f"  -> Checkpoint: models/{entry.slug}/{entry.checkpoint}")
        print(f"  -> Stems: lead vocals, backing vocals")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def download_dereverb():
    """Download anvuew dereverb MelBand RoFormer."""
    from mel_band_roformer import MODEL_REGISTRY

    slug = "roformer-model-melband-roformer-de-reverb-by-anvuew"
    print(f"\n[3/3] Downloading Dereverb MelBand RoFormer ({slug})...")
    try:
        MODEL_REGISTRY.download(slug)
        entry = MODEL_REGISTRY.get(slug)
        print(f"  -> Config: models/{entry.slug}/{entry.config}")
        print(f"  -> Checkpoint: models/{entry.slug}/{entry.checkpoint}")
        print(f"  -> Output: room/reverb (wet), noreverb (dry)")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def list_all_available():
    """List all available models from both registries."""
    print("\n=== Available BS-RoFormer models ===")
    try:
        from bs_roformer import MODEL_REGISTRY as BS_REG
        print(BS_REG.as_table())
    except Exception:
        print("  (bs-roformer-infer not installed)")

    print("\n=== Available MelBand RoFormer models ===")
    try:
        from mel_band_roformer import MODEL_REGISTRY as MB_REG
        for cat in MB_REG.categories():
            models = MB_REG.list(cat)
            print(f"\n  {cat}:")
            for m in models:
                print(f"    - {m.name} ({m.slug})")
    except Exception:
        print("  (melband-roformer-infer not installed)")


def main():
    print("RAIN Model Checkpoint Downloader")
    print("=" * 50)

    if "--list" in sys.argv:
        install_packages()
        list_all_available()
        return 0

    install_packages()

    results = {
        "BS-RoFormer SW (6-stem)": download_bs_roformer(),
        "Karaoke (vocal split)": download_karaoke(),
        "Dereverb (room extraction)": download_dereverb(),
    }

    print("\n" + "=" * 50)
    print("DOWNLOAD SUMMARY")
    print("=" * 50)
    all_ok = True
    for name, ok in results.items():
        status = "OK" if ok else "FAILED"
        print(f"  {name}: {status}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("All models downloaded successfully.")
        print("Set SEPARATION_ENABLED=true in your .env to enable 12-stem separation.")
        print()
        print("Note: LarsNet (drum sub-separation) is not yet pip-installable.")
        print("Pass 3 uses spectral band-splitting as a fallback until LarsNet is available.")
    else:
        print("Some downloads failed. Check network connectivity and retry.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
