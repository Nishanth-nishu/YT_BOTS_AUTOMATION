#!/bin/bash
# Builds the AnimeForge GPU environment on a compute node's local scratch.
# Run inside a Slurm job (see first_shot.sbatch). Safe to re-run.
set -euo pipefail

AF="${ANIMEFORGE_HOME:-/scratch/$USER/animeforge}"
mkdir -p "$AF"/{bin,hf,out,cache,tmp}
# Two jobs starting together on one node both tried to create the environment; take turns.
exec 9>"$AF/setup.lock"; flock 9
export UV_CACHE_DIR="$AF/cache/uv" UV_PYTHON_INSTALL_DIR="$AF/python" TMPDIR="$AF/tmp"

free_gb=$(df -BG --output=avail "$AF" | tail -1 | tr -dc 0-9)
echo "scratch free: ${free_gb} GB"
if [ "$free_gb" -lt 40 ]; then echo "refusing: under 40 GB free for the environment"; exit 3; fi

if [ ! -x "$AF/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$AF/bin" UV_NO_MODIFY_PATH=1 sh
fi
export PATH="$AF/bin:$PATH"

if [ ! -x "$AF/venv/bin/python" ]; then
  uv venv --python 3.11 "$AF/venv"
fi
uv pip install --python "$AF/venv/bin/python" \
  torch torchvision --index-url https://download.pytorch.org/whl/cu124
uv pip install --python "$AF/venv/bin/python" \
  diffusers transformers accelerate safetensors sentencepiece protobuf ftfy \
  pillow numpy imageio imageio-ffmpeg huggingface_hub peft

"$AF/venv/bin/python" - <<'EOF'
import torch, diffusers, transformers
print("torch", torch.__version__, "cuda", torch.cuda.is_available(),
      torch.cuda.get_device_name(0) if torch.cuda.is_available() else "-")
print("diffusers", diffusers.__version__, "transformers", transformers.__version__)
assert torch.cuda.is_available()
EOF
