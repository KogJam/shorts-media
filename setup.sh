#!/usr/bin/env bash
# One-time (per fresh machine) setup: offline voice model, pronunciation dictionary, emoji images.
# Everything comes from GitHub, so it works inside the restricted cloud sandbox.
set -euo pipefail
A="${SHORTS_ASSETS:-$HOME/tts}"
mkdir -p "$A"
cd "$A"
[ -d kokoro-onnx ] || git clone -q --depth 1 https://github.com/thewh1teagle/kokoro-onnx.git
[ -d cmudict ]     || git clone -q --depth 1 https://github.com/cmusphinx/cmudict.git
[ -f kokoro.onnx ] || curl -sSL -o kokoro.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx
[ -f voices.bin ]  || curl -sSL -o voices.bin  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
if [ ! -d noto-emoji/.git ]; then
  # blobless clone, nothing checked out: render.py fetches single emoji images on demand
  git clone -q --depth 1 --filter=blob:none --no-checkout https://github.com/googlefonts/noto-emoji.git
fi
python3 -c "import onnxruntime, numpy, PIL" || { echo "missing python deps (onnxruntime numpy pillow)"; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg missing"; exit 1; }
echo "setup ok: $A"
