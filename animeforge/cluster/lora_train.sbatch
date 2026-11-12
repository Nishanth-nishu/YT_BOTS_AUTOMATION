#!/bin/bash
#SBATCH -A plafnet2
#SBATCH -p plafnet2
#SBATCH -J af_lora_train
#SBATCH --exclude=gnode118
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=48G
#SBATCH --time=03:00:00
#SBATCH --output=animeforge/logs/lora_train_%j.log
# Train a character LoRA with Kohya sd-scripts on the chosen pictures, then test it.
# Needs EPISODE_ID and TRIGGER. Reads ~/animeforge/out/lora-$EPISODE_ID (candidates and selected.txt).
set -euo pipefail
: "${EPISODE_ID:?set EPISODE_ID}" "${TRIGGER:?set TRIGGER}"
STEPS=${STEPS:-1200} DIM=${DIM:-16}

export ANIMEFORGE_HOME=/scratch/$USER/animeforge
AF=$ANIMEFORGE_HOME
SRC=$AF/src-$SLURM_JOB_ID
mkdir -p "$AF/tmp" && cp -r "$HOME/animeforge/src" "$SRC"
export HF_HOME=$AF/hf TMPDIR=$AF/tmp PYTHONPATH=$SRC ANIMEFORGE_MODELS_DIR=$AF/hf
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
bash "$SRC/animeforge/cluster/setup_env.sh"
bash "$SRC/animeforge/cluster/setup_train.sh"
source "$SRC/animeforge/cluster/models_sync.sh"; af_restore "models--cagliostrolab*" "models--h94*"
PY=$AF/venv/bin/python
PYT=$AF/venv-train/bin/python
$PY -c "
from animeforge import registry
for m in ('animagine-xl-4', 'ipadapter-plus', 'kohya-sd-scripts'):
    registry.require(m, acknowledged=('animagine-xl-4', 'ipadapter-plus', 'kohya-sd-scripts'))
print('licence gate passed')
"
HOMEDIR=$HOME/animeforge/out/lora-$EPISODE_ID
WORK=$AF/out/lora-$EPISODE_ID-job$SLURM_JOB_ID      # a fresh folder per job: nothing to clear
mkdir -p "$WORK" && cp -r "$HOMEDIR/." "$WORK/"
$PY -m animeforge.cluster.lora_prep "$WORK" "$TRIGGER"

# The trainer fetches its tokenizers from two other repositories. The base model ships the same
# tokenizers, so hand it those instead of downloading from a repository we have not cleared.
SNAP=$(ls -d "$AF"/hf/hub/models--cagliostrolab--animagine-xl-4.0/snapshots/* | head -1)
TOK=$WORK/tokenizers
mkdir -p "$TOK"
cp -rL "$SNAP/tokenizer" "$TOK/openai_clip-vit-large-patch14"
cp -rL "$SNAP/tokenizer_2" "$TOK/laion_CLIP-ViT-bigG-14-laion2B-39B-b160k"

T0=$(date +%s)
cd "$AF/sd-scripts"
( while sleep 20; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits; done > "$WORK/vram.log" ) &
WATCH=$!
# bf16, not fp16: with fp16 the trainer asks the base model for "fp16" weight files, which this repository does not have.
HF_HUB_OFFLINE=1 $PYT sdxl_train_network.py \
  --pretrained_model_name_or_path "$SNAP" --tokenizer_cache_dir "$TOK" \
  --dataset_config "$WORK/dataset.toml" --output_dir "$WORK/model" --output_name "$TRIGGER" \
  --save_model_as safetensors --save_every_n_steps 400 \
  --network_module networks.lora --network_dim "$DIM" --network_alpha $((DIM / 2)) --network_train_unet_only \
  --optimizer_type AdamW --learning_rate 1e-4 --lr_scheduler cosine --lr_warmup_steps 50 \
  --max_train_steps "$STEPS" --mixed_precision bf16 --save_precision fp16 --no_half_vae \
  --cache_latents --cache_text_encoder_outputs --gradient_checkpointing --sdpa \
  --min_snr_gamma 5 --seed 42 --max_data_loader_n_workers 2
kill $WATCH || true
T1=$(date +%s)
cd "$SRC"
PEAK=$(sort -n "$WORK/vram.log" | tail -1)
echo "{\"train_seconds\": $((T1 - T0)), \"steps\": $STEPS, \"dim\": $DIM, \"peak_vram_mb_whole_gpu\": ${PEAK:-0}}" > "$WORK/train_report.json"
cat "$WORK/train_report.json"; ls -la "$WORK/model"

LORA=$WORK/model/$TRIGGER.safetensors
$PY -m animeforge.cluster.lora_eval --spec "$SRC/animeforge/cluster/episodes/$EPISODE_ID.json" \
  --reference "$WORK/reference.png" --lora "$LORA" --trigger "$TRIGGER" --out "$WORK/eval"
MID=$(ls "$WORK"/model/*step00000800.safetensors 2>/dev/null | head -1 || true)
if [ -n "$MID" ]; then
  $PY -m animeforge.cluster.lora_eval --spec "$SRC/animeforge/cluster/episodes/$EPISODE_ID.json" \
    --reference "$WORK/reference.png" --lora "$MID" --trigger "$TRIGGER" --out "$WORK/eval-800"
fi

# Keep the LoRA at home (small) and on share6; results at home.
mkdir -p "$HOME/animeforge/loras" && cp "$WORK"/model/*.safetensors "$HOME/animeforge/loras/"
$AF_SSH "$AF_GW" "mkdir -p /share6/$USER/animeforge/loras" && rsync -a -e "$AF_SSH" "$WORK/model/" "$AF_GW:/share6/$USER/animeforge/loras/"
for d in eval eval-800 "train-$TRIGGER"; do
  if [ -d "$WORK/$d" ]; then mkdir -p "$HOMEDIR/$d" && cp -r "$WORK/$d/." "$HOMEDIR/$d/"; fi
done
cp "$WORK"/train_report.json "$WORK"/training_set.json "$WORK"/dataset.toml "$HOMEDIR/"
du -sh "$HOME/animeforge/loras" "$HOMEDIR"
