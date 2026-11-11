#!/bin/bash
#SBATCH -A plafnet2
#SBATCH -p plafnet2
#SBATCH -J af_first_shot
#SBATCH -w gnode114
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=48G
#SBATCH --time=03:00:00
#SBATCH --output=animeforge/logs/first_shot_%j.log
# One character, one five-second shot: Arjuna, still then image-to-video.
set -euo pipefail

export ANIMEFORGE_HOME=/scratch/$USER/animeforge
AF=$ANIMEFORGE_HOME
SRC=$AF/src-$SLURM_JOB_ID
mkdir -p "$AF" && cp -r "$HOME/animeforge/src" "$SRC"   # private copy: a later upload cannot change a running job

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export HF_HOME=$AF/hf TMPDIR=$AF/tmp PYTHONPATH=$SRC
bash "$SRC/animeforge/cluster/setup_env.sh"
source "$SRC/animeforge/cluster/models_sync.sh"; af_restore
export ANIMEFORGE_MODELS_DIR=$AF/hf ANIMEFORGE_ACK=animagine-xl-4
PY=$AF/venv/bin/python
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv

$PY -m animeforge.cluster.fetch_model animagine-xl-4 cagliostrolab/animagine-xl-4.0 \
  --allow "model_index.json" "scheduler/*" "text_encoder/*" "text_encoder_2/*" \
          "tokenizer/*" "tokenizer_2/*" "unet/*" "vae/*"
$PY -m animeforge.cluster.fetch_model wan2.2-ti2v-5b Wan-AI/Wan2.2-TI2V-5B-Diffusers

SHOT=$AF/out/arjuna-01-draws-bow
mkdir -p "$SHOT"
$PY -m animeforge.cluster.gen_still --out "$SHOT/first_frame.png" --count 4 --seed 11 \
  --prompt "1boy, solo, original, young indian warrior prince, archer, brown skin, long black hair in a topknot, small golden crown, determined eyes, ornate blue and gold armor over white dhoti, red sash, golden armbands, holding a longbow, quiver on back, forest hermitage at dawn, soft rim light, upper body, looking to the side, anime coloring, masterpiece, high score, great score, absurdres"

$PY -m animeforge.cluster.gen_shot --image "$SHOT/first_frame-11.png" --out "$SHOT/shot.mp4" --seed 11 \
  --prompt "Anime style. A young Indian warrior prince in blue and gold armor slowly raises his longbow and draws the string back, eyes narrowing in focus. His hair and red sash move gently in the wind, dawn light flickers through the trees behind him. Slow camera push-in. Consistent face, smooth natural motion."

af_backup
mkdir -p "$HOME/animeforge/out"
cp -r "$SHOT" "$HOME/animeforge/out/"
ls -la "$HOME/animeforge/out/arjuna-01-draws-bow"
