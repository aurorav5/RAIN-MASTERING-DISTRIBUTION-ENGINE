#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# RAIN RainNet v2 Training — RunPod / any NVIDIA GPU
#
# Usage:
#   1. Launch RunPod instance (RTX 4090 recommended, ~$0.44/hr)
#   2. Clone repo: git clone https://github.com/aurorav5/rain-blueprint.git
#   3. cd rain-blueprint && bash scripts/train_runpod.sh
#
# Cost estimate: ~$2 for 4 hours on RTX 4090
# Output: models/rain_base.onnx (46-param, trained)
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail

echo "═══════════════════════════════════════════"
echo "  RAIN RainNet v2 Training Pipeline"
echo "═══════════════════════════════════════════"

# --- Check GPU ---
if ! command -v nvidia-smi &>/dev/null; then
    echo "ERROR: No NVIDIA GPU detected. This script requires CUDA."
    exit 1
fi
echo "GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)"

# --- Install deps ---
echo "[1/6] Installing dependencies..."
pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -q onnx onnxruntime onnxscript numpy scipy librosa soundfile
echo "  Done."

# --- Generate training data (heuristic bootstrap) ---
echo "[2/6] Generating training manifest from heuristics..."
PYTHONPATH=. python -c "
import json, random
from ml.rainnet.heuristics import get_heuristic_params, GENRE_PRESETS, PLATFORM_LUFS

GENRES = list(GENRE_PRESETS.keys())
PLATFORMS = list(PLATFORM_LUFS.keys())
N_SAMPLES = 10000  # 10K samples from heuristic perturbation

with open('training_manifest.jsonl', 'w') as f:
    for i in range(N_SAMPLES):
        genre = random.choice(GENRES)
        platform = random.choice(PLATFORMS)
        vinyl = platform == 'vinyl'
        params = get_heuristic_params(genre, platform, vinyl=vinyl)

        # Perturb to prevent overfitting to exact heuristic values
        for key in ['mb_ratio_low', 'mb_ratio_mid', 'mb_ratio_high']:
            params[key] = max(1.0, min(20.0, params[key] * random.uniform(0.8, 1.2)))
        for j in range(8):
            params['eq_gains'][j] = max(-12.0, min(12.0, params['eq_gains'][j] + random.uniform(-2.0, 2.0)))
        for key in ['macro_brighten','macro_glue','macro_width','macro_punch','macro_warmth','macro_space']:
            params[key] = max(0.0, min(10.0, params[key] + random.uniform(-1.5, 1.5)))
        params['stereo_width'] = max(0.0, min(2.0, params['stereo_width'] + random.uniform(-0.2, 0.2)))
        params['saturation_drive'] = max(0.0, min(1.0, params['saturation_drive'] + random.uniform(-0.1, 0.1)))

        f.write(json.dumps({
            'audio_path': f'synthetic/{i:05d}.wav',  # mel will be random for bootstrap
            'genre_label': GENRES.index(genre),
            'platform_label': PLATFORMS.index(platform),
            'target_params': params,
        }) + '\n')

print(f'Generated {N_SAMPLES} training samples → training_manifest.jsonl')
"

# --- Pre-compute synthetic mels (random for bootstrap — real audio later) ---
echo "[3/6] Generating synthetic mel spectrograms..."
PYTHONPATH=. python -c "
import numpy as np
import json
from pathlib import Path

Path('synthetic').mkdir(exist_ok=True)
with open('training_manifest.jsonl') as f:
    samples = [json.loads(l) for l in f if l.strip()]

for i, s in enumerate(samples):
    mel_path = Path(s['audio_path']).with_suffix('.mel.npy')
    mel_path.parent.mkdir(exist_ok=True)
    # Random mel spectrograms for bootstrap training
    # Replace with real audio mels for production training
    mel = np.random.randn(128, 128).astype(np.float32) * 0.5
    np.save(str(mel_path), mel)
    if (i+1) % 2000 == 0:
        print(f'  [{i+1}/{len(samples)}]')

print(f'Generated {len(samples)} synthetic mels')
"

# --- Train ---
echo "[4/6] Training RainNet v2 (46-param, 50 epochs)..."
PYTHONPATH=. python -m ml.rainnet.train training_manifest.jsonl \
    --output-dir models/checkpoints \
    --epochs 50 \
    --batch-size 64 \
    --device cuda

# --- Export ONNX ---
echo "[5/6] Exporting best checkpoint to ONNX..."
BEST_CKPT=$(ls -t models/checkpoints/rainnet_v2_epoch_*.pt | head -1)
echo "  Using checkpoint: $BEST_CKPT"
PYTHONPATH=. python -c "
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from ml.rainnet.export import export_onnx
export_onnx('${BEST_CKPT}', 'models/rain_trained.onnx')
"

# --- Verify ---
echo "[6/6] Verification..."
PYTHONPATH=. python -c "
import onnxruntime as ort
import numpy as np
sess = ort.InferenceSession('models/rain_trained.onnx', providers=['CUDAExecutionProvider','CPUExecutionProvider'])
out = sess.run(None, {
    'mel': np.random.randn(1,1,128,128).astype(np.float32),
    'artist_vec': np.zeros((1,64), dtype=np.float32),
    'genre_id': np.array([3], dtype=np.int64),
    'platform_id': np.array([0], dtype=np.int64),
    'simple_mode': np.ones((1,1), dtype=np.float32),
})
assert out[0].shape == (1, 46), f'FAILED: shape={out[0].shape}'
print(f'RainNet ONNX verified: shape={out[0].shape}')
print(f'  target_lufs: {out[0][0][0]:.4f}')
print(f'  macro_brighten: {out[0][0][39]:.4f}')
print(f'  macro_repair: {out[0][0][45]:.4f}')
"

echo ""
echo "═══════════════════════════════════════════"
echo "  Training Complete"
echo "═══════════════════════════════════════════"
echo "  Untrained ONNX: models/rain_base.onnx (random weights)"
echo "  Trained ONNX:   models/rain_trained.onnx"
echo ""
echo "  To deploy:"
echo "    scp models/rain_trained.onnx prod:/models/rain_base.onnx"
echo "    Set RAIN_NORMALIZATION_VALIDATED=true"
echo "    docker compose restart backend worker"
echo ""
echo "  NOTE: This model was trained on SYNTHETIC data (heuristic bootstrap)."
echo "  For production quality, retrain on REAL mastered audio with expert labels."
echo "═══════════════════════════════════════════"
