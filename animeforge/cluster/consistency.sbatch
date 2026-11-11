#!/bin/bash
#SBATCH -A plafnet2
#SBATCH -p plafnet2
#SBATCH -J af_consistency
#SBATCH -w gnode114
#SBATCH --gres=gpu:1
#SBATCH -c 6
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=animeforge/logs/consistency_%j.log
# Phase 3: does IP-Adapter Plus keep Arjuna the same across six new scenes?
set -euo pipefail

export ANIMEFORGE_HOME=/scratch/$USER/animeforge
AF=$ANIMEFORGE_HOME
SRC=$AF/src-$SLURM_JOB_ID
mkdir -p "$AF" && cp -r "$HOME/animeforge/src" "$SRC"
export HF_HOME=$AF/hf TMPDIR=$AF/tmp PYTHONPATH=$SRC ANIMEFORGE_MODELS_DIR=$AF/hf
bash "$SRC/animeforge/cluster/setup_env.sh"
source "$SRC/animeforge/cluster/models_sync.sh"; af_restore
export ANIMEFORGE_ACK=animagine-xl-4,ipadapter-plus
PY=$AF/venv/bin/python

$PY -m animeforge.cluster.fetch_model ipadapter-plus h94/IP-Adapter \
  --allow "models/image_encoder/config.json" "models/image_encoder/model.safetensors" \
          "sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"
$PY -m animeforge.cluster.fetch_model animagine-xl-4 cagliostrolab/animagine-xl-4.0 \
  --allow "model_index.json" "scheduler/*" "text_encoder/*" "text_encoder_2/*" \
          "tokenizer/*" "tokenizer_2/*" "unet/*" "vae/*"

CHAR="young indian warrior prince, archer, brown skin, long black hair in a topknot, small golden crown, ornate blue and gold armor over white dhoti, red sash, golden armbands"
SCALE=${SCALE:-0.6}
if [ "${PLAIN_REF:-0}" = "1" ]; then
  # A reference on a plain background, so the adapter has no scenery to copy.
  REF=$AF/out/consistency-arjuna-plain/reference.png
  OUT=$AF/out/consistency-arjuna-plain
  mkdir -p "$OUT"
  $PY -m animeforge.cluster.gen_still --out "$REF" --seed 11     --prompt "1boy, solo, original, $CHAR, upper body, looking at viewer, simple background, white background, anime coloring, masterpiece, high score, great score, absurdres"
else
  REF=${REF:-$AF/out/arjuna-01-draws-bow/first_frame-11.png}
  OUT=$AF/out/consistency-arjuna
fi
$PY -m animeforge.cluster.consistency --reference "$REF" --out "$OUT" --scale "$SCALE" --character "$CHAR"
af_backup
mkdir -p "$HOME/animeforge/out" && cp -r "$OUT" "$HOME/animeforge/out/"
