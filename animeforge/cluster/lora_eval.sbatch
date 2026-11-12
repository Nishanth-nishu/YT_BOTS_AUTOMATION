#!/bin/bash
#SBATCH -A plafnet2
#SBATCH -p plafnet2
#SBATCH -J af_lora_eval
#SBATCH --exclude=gnode118
#SBATCH --gres=gpu:1
#SBATCH -c 6
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=animeforge/logs/lora_eval_%j.log
# Test a trained LoRA at another strength. Needs EPISODE_ID, LORA (file in ~/animeforge/loras),
# TRIGGER and SCALES (space-free list like 0.5:0.7).
set -euo pipefail
: "${EPISODE_ID:?}" "${LORA:?}" "${TRIGGER:?}" "${SCALES:?}"

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
"
HOMEDIR=$HOME/animeforge/out/lora-$EPISODE_ID
for S in ${SCALES//:/ }; do
  OUT=$AF/out/lora-eval-$SLURM_JOB_ID/eval-${LORA%.safetensors}-$S
  $PY -m animeforge.cluster.lora_eval --spec "$SRC/animeforge/cluster/episodes/$EPISODE_ID.json" \
    --reference "$HOMEDIR/reference.png" --lora "$HOME/animeforge/loras/$LORA" --trigger "$TRIGGER" \
    --lora-scale "$S" --out "$OUT"
  mkdir -p "$HOMEDIR/$(basename "$OUT")" && cp "$OUT"/contact_sheet.jpg "$OUT"/report.json "$HOMEDIR/$(basename "$OUT")/"
done
