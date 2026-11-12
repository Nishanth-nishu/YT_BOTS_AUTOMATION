#!/bin/bash
#SBATCH -A plafnet2
#SBATCH -p plafnet2
#SBATCH -J af_shot
#SBATCH --exclude=gnode118
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=animeforge/logs/shot_%j.log
# One shot for the job queue: a still, then a clip. Needs SHOT_ID; reads
# animeforge/cluster/prompts/$SHOT_ID.still.txt and $SHOT_ID.motion.txt.
set -euo pipefail
: "${SHOT_ID:?set SHOT_ID}"
SEED=${SEED:-7} FRAMES=${FRAMES:-121} STEPS=${STEPS:-30}

export ANIMEFORGE_HOME=/scratch/$USER/animeforge
AF=$ANIMEFORGE_HOME
SRC=$AF/src-$SLURM_JOB_ID
mkdir -p "$AF/tmp" && cp -r "$HOME/animeforge/src" "$SRC"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export HF_HOME=$AF/hf TMPDIR=$AF/tmp PYTHONPATH=$SRC ANIMEFORGE_MODELS_DIR=$AF/hf
bash "$SRC/animeforge/cluster/setup_env.sh"
source "$SRC/animeforge/cluster/models_sync.sh"; af_restore "models--cagliostrolab*" "models--Wan-AI*"
export ANIMEFORGE_ACK=animagine-xl-4
PY=$AF/venv/bin/python
P=$SRC/animeforge/cluster/prompts

$PY -c "
from animeforge import registry
for m in ('animagine-xl-4', 'wan2.2-ti2v-5b'):
    registry.require(m, acknowledged=('animagine-xl-4',))
"
OUT=$AF/out/$SHOT_ID
mkdir -p "$OUT"
$PY -m animeforge.cluster.gen_still --out "$OUT/first_frame.png" --count 1 --seed "$SEED" --prompt "$(cat "$P/$SHOT_ID.still.txt")"
$PY -m animeforge.cluster.gen_shot --image "$OUT/first_frame-$SEED.png" --out "$OUT/shot.mp4" --seed "$SEED" \
  --frames "$FRAMES" --steps "$STEPS" --prompt "$(cat "$P/$SHOT_ID.motion.txt")"

mkdir -p "$HOME/animeforge/out" && rm -rf "$HOME/animeforge/out/$SHOT_ID" && cp -r "$OUT" "$HOME/animeforge/out/"
