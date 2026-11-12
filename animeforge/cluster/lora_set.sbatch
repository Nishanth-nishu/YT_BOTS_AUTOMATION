#!/bin/bash
#SBATCH -A plafnet2
#SBATCH -p plafnet2
#SBATCH -J af_lora_set
#SBATCH --exclude=gnode118
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=animeforge/logs/lora_set_%j.log
# Candidate training pictures for a character LoRA, and the training environment. Needs EPISODE_ID
# (the episode whose character and reference are used).
set -euo pipefail
: "${EPISODE_ID:?set EPISODE_ID}"

export ANIMEFORGE_HOME=/scratch/$USER/animeforge
AF=$ANIMEFORGE_HOME
SRC=$AF/src-$SLURM_JOB_ID
mkdir -p "$AF/tmp" && cp -r "$HOME/animeforge/src" "$SRC"
export HF_HOME=$AF/hf TMPDIR=$AF/tmp PYTHONPATH=$SRC ANIMEFORGE_MODELS_DIR=$AF/hf
bash "$SRC/animeforge/cluster/setup_env.sh"
source "$SRC/animeforge/cluster/models_sync.sh"; af_restore "models--cagliostrolab*" "models--h94*"
PY=$AF/venv/bin/python
$PY -c "
from animeforge import registry
for m in ('animagine-xl-4', 'ipadapter-plus', 'kohya-sd-scripts'):
    registry.require(m, acknowledged=('animagine-xl-4', 'ipadapter-plus', 'kohya-sd-scripts'))
print('licence gate passed')
"
OUT=$AF/out/lora-$EPISODE_ID
mkdir -p "$OUT"
save_home() { mkdir -p "$HOME/animeforge/out/lora-$EPISODE_ID" && cp -r "$OUT/." "$HOME/animeforge/out/lora-$EPISODE_ID/"; }
trap save_home EXIT
cp "$HOME/animeforge/out/$EPISODE_ID/reference.png" "$OUT/reference.png"
$PY -m animeforge.cluster.lora_set --spec "$SRC/animeforge/cluster/episodes/$EPISODE_ID.json" \
  --reference "$OUT/reference.png" --out "$OUT"

bash "$SRC/animeforge/cluster/setup_train.sh"
"$AF/venv-train/bin/python" "$AF/sd-scripts/sdxl_train_network.py" --help > "$OUT/trainer_help.txt" 2>&1 || true
wc -l "$OUT/trainer_help.txt"
