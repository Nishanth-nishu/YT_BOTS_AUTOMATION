#!/bin/bash
#SBATCH -A plafnet2
#SBATCH -p plafnet2
#SBATCH -J af_bench
#SBATCH --exclude=gnode118
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=48G
#SBATCH --time=03:00:00
#SBATCH --output=animeforge/logs/bench_%j.log
# Phase 4: Wan 2.2 TI2V-5B on the RTX 3090 at cheaper settings, same first frame and seed
# as the first shot (704x1280, 50 steps), so time, memory and quality can be compared.
set -euo pipefail

export ANIMEFORGE_HOME=/scratch/$USER/animeforge
AF=$ANIMEFORGE_HOME
SRC=$AF/src-$SLURM_JOB_ID
mkdir -p "$AF/tmp" && cp -r "$HOME/animeforge/src" "$SRC"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export HF_HOME=$AF/hf TMPDIR=$AF/tmp PYTHONPATH=$SRC ANIMEFORGE_MODELS_DIR=$AF/hf
bash "$SRC/animeforge/cluster/setup_env.sh"
source "$SRC/animeforge/cluster/models_sync.sh"; af_restore
PY=$AF/venv/bin/python
IMG=$AF/out/arjuna-01-draws-bow/first_frame-11.png
OUT=$AF/out/bench-wan22-5b
PROMPT="Anime style. A young Indian warrior prince in blue and gold armor slowly raises his longbow and draws the string back, eyes narrowing in focus. His hair and red sash move gently in the wind, dawn light flickers through the trees behind him. Slow camera push-in. Consistent face, smooth natural motion."

$PY -m animeforge.cluster.gen_shot --image "$IMG" --prompt "$PROMPT" --seed 11 --steps 30 --out "$OUT/720p-30steps.mp4"
$PY -m animeforge.cluster.gen_shot --image "$IMG" --prompt "$PROMPT" --seed 11 --steps 30 --width 480 --height 864 --out "$OUT/480p-30steps.mp4"
$PY -m animeforge.cluster.gen_shot --image "$IMG" --prompt "$PROMPT" --seed 11 --steps 20 --width 480 --height 864 --out "$OUT/480p-20steps.mp4"
$PY -m animeforge.cluster.gen_shot --image "$IMG" --prompt "$PROMPT" --seed 11 --steps 30 --offload none --out "$OUT/720p-30steps-nooffload.mp4" || echo "no-offload run failed (recorded as not fitting)"
af_backup
mkdir -p "$HOME/animeforge/out" && rm -rf "$HOME/animeforge/out/bench-wan22-5b" && cp -r "$OUT" "$HOME/animeforge/out/"
