#!/bin/bash
# The TTS environment (Chatterbox pins its own torch and transformers). Safe to re-run.
set -euo pipefail
AF="${ANIMEFORGE_HOME:-/scratch/$USER/animeforge}"
export PATH="$AF/bin:$PATH" UV_CACHE_DIR="$AF/cache/uv" UV_PYTHON_INSTALL_DIR="$AF/python"
if [ ! -x "$AF/venv-tts/bin/python" ]; then uv venv --python 3.11 "$AF/venv-tts"; fi
uv pip install --python "$AF/venv-tts/bin/python" chatterbox-tts faster-whisper huggingface_hub
