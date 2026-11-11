#!/bin/bash
#SBATCH -A plafnet2
#SBATCH -p plafnet2
#SBATCH -J af_voice
#SBATCH -w gnode114
#SBATCH --gres=gpu:1
#SBATCH -c 6
#SBATCH --mem=32G
#SBATCH --time=01:30:00
#SBATCH --output=animeforge/logs/voice_%j.log
# Phase 2: Hindi voice benchmark (Chatterbox Multilingual, checked by Whisper).
set -euo pipefail

export ANIMEFORGE_HOME=/scratch/$USER/animeforge
AF=$ANIMEFORGE_HOME
SRC=$AF/src-$SLURM_JOB_ID
mkdir -p "$AF" && cp -r "$HOME/animeforge/src" "$SRC"   # private copy: a later upload cannot change a running job
export PATH="$AF/bin:$PATH" UV_CACHE_DIR="$AF/cache/uv" UV_PYTHON_INSTALL_DIR="$AF/python"
export HF_HOME=$AF/hf TMPDIR=$AF/tmp PYTHONPATH=$SRC ANIMEFORGE_MODELS_DIR=$AF/hf
bash "$SRC/animeforge/cluster/setup_env.sh"
bash "$SRC/animeforge/cluster/setup_tts.sh"
source "$SRC/animeforge/cluster/models_sync.sh"; af_restore
export ANIMEFORGE_ACK=chatterbox-multilingual
mkdir -p "$AF/tmp"

PY=$AF/venv-tts/bin/python
SP=$($PY -c "import site;print(site.getsitepackages()[0])")
export LD_LIBRARY_PATH=$(ls -d $SP/nvidia/*/lib | tr '\n' ':')${LD_LIBRARY_PATH:-}

$PY - <<'PYEOF'
import os
from pathlib import Path
from animeforge import registry
from animeforge.storage import ensure_space
registry.require("chatterbox-multilingual", acknowledged=("chatterbox-multilingual",))
registry.require("whisper-large-v3")
ensure_space(Path(os.environ["HF_HOME"]), 18.0, "Chatterbox (13.9 GB) and Whisper large-v3 (3.1 GB)")
PYEOF

OUT=$AF/out/voice-chatterbox-hi
$PY -m animeforge.cluster.voice_bench --out "$OUT"
af_backup
mkdir -p "$HOME/animeforge/out" && cp -r "$OUT" "$HOME/animeforge/out/"
