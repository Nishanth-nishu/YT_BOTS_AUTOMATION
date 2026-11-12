#!/bin/bash
# The TTS environment (Chatterbox pins its own torch and transformers). Safe to re-run.
set -euo pipefail
AF="${ANIMEFORGE_HOME:-/scratch/$USER/animeforge}"
mkdir -p "$AF"/{bin,hf,out,cache,tmp}
# Two jobs starting together on one node both tried to create the environment; take turns.
exec 9>"$AF/setup.lock"; flock 9
export PATH="$AF/bin:$PATH" UV_CACHE_DIR="$AF/cache/uv" UV_PYTHON_INSTALL_DIR="$AF/python"
if [ ! -x "$AF/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$AF/bin" UV_NO_MODIFY_PATH=1 sh
fi
if [ ! -x "$AF/venv-tts/bin/python" ]; then uv venv --python 3.11 "$AF/venv-tts"; fi
# Measured 2026-11-12: files.pythonhosted.org gave the nodes about 0.3 MB/s while download.pytorch.org gave 27 MB/s,
# and Chatterbox's 2.5 GB of torch and CUDA wheels never finished. Take those from the PyTorch index first.
export UV_HTTP_TIMEOUT=300 UV_LOCK_TIMEOUT=3600
uv pip install --python "$AF/venv-tts/bin/python" torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
uv pip install --python "$AF/venv-tts/bin/python" chatterbox-tts faster-whisper huggingface_hub "setuptools<81"   # resemble-perth (the watermarker) imports pkg_resources
