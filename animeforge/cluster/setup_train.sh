#!/bin/bash
# The LoRA training environment: Kohya sd-scripts in its own venv (it pins its
# own diffusers and transformers). Safe to re-run.
set -euo pipefail
AF="${ANIMEFORGE_HOME:-/scratch/$USER/animeforge}"
mkdir -p "$AF"/{bin,hf,out,cache,tmp}
exec 9>"$AF/setup.lock"; flock 9
export PATH="$AF/bin:$PATH" UV_CACHE_DIR="$AF/cache/uv" UV_PYTHON_INSTALL_DIR="$AF/python"
export UV_HTTP_TIMEOUT=300 UV_LOCK_TIMEOUT=3600
if [ ! -x "$AF/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$AF/bin" UV_NO_MODIFY_PATH=1 sh
fi
KOHYA_REF=${KOHYA_REF:-v0.12.3}
if [ ! -d "$AF/sd-scripts/.git" ]; then
  git clone --depth 1 --branch "$KOHYA_REF" https://github.com/kohya-ss/sd-scripts "$AF/sd-scripts"
fi
git -C "$AF/sd-scripts" log -1 --format='sd-scripts %h %ad %s' --date=short
if [ ! -x "$AF/venv-train/bin/python" ]; then uv venv --python 3.11 "$AF/venv-train"; fi
PYT="$AF/venv-train/bin/python"
# The large wheels come from the PyTorch index (PyPI was at 0.3 MB/s on 2026-11-12).
uv pip install --python "$PYT" torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
# requirements.txt ends with "-e ." (the repo's own `library` package); install the rest, then the repo.
grep -vE '^\s*-e\s|^\s*#|^\s*$' "$AF/sd-scripts/requirements.txt" > "$AF/tmp/kohya-req.txt"
uv pip install --python "$PYT" -r "$AF/tmp/kohya-req.txt"
uv pip install --python "$PYT" -e "$AF/sd-scripts"
"$PYT" -c "import torch, diffusers, transformers, library; print('train env: torch', torch.__version__, 'diffusers', diffusers.__version__, 'transformers', transformers.__version__)"
