#!/bin/bash
# Polls for training completion, then exports ONNX
cd "$(dirname "$0")/.."
while true; do
  COUNT=$(ls models/checkpoints/rainnet_v2_epoch_*.pt 2>/dev/null | wc -l)
  if [ "$COUNT" -ge 25 ]; then
    echo "Training complete ($COUNT epochs). Exporting ONNX..."
    BEST=$(ls -t models/checkpoints/rainnet_v2_epoch_*.pt | head -1)
    PYTHONPATH=. python -X utf8 -c "
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from ml.rainnet.export import export_onnx
export_onnx('$BEST', 'models/rain_trained.onnx')
print('ONNX export complete: models/rain_trained.onnx')
"
    break
  fi
  echo "$(date +%H:%M) - $COUNT/25 epochs complete..."
  sleep 300
done
