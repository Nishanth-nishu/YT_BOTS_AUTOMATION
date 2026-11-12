#!/bin/bash
#SBATCH -A plafnet2
#SBATCH -p plafnet2
#SBATCH -J af_episode
#SBATCH --exclude=gnode118
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=48G
#SBATCH --time=06:00:00
#SBATCH --output=animeforge/logs/episode_%j.log
# One episode: stills, clips and voices for every shot. Needs EPISODE_ID.
set -euo pipefail
: "${EPISODE_ID:?set EPISODE_ID}"

export ANIMEFORGE_HOME=/scratch/$USER/animeforge
AF=$ANIMEFORGE_HOME
SRC=$AF/src-$SLURM_JOB_ID
mkdir -p "$AF/tmp" && cp -r "$HOME/animeforge/src" "$SRC"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export HF_HOME=$AF/hf TMPDIR=$AF/tmp PYTHONPATH=$SRC ANIMEFORGE_MODELS_DIR=$AF/hf
bash "$SRC/animeforge/cluster/setup_env.sh"
source "$SRC/animeforge/cluster/models_sync.sh"; af_restore
export ANIMEFORGE_ACK=animagine-xl-4,ipadapter-plus,chatterbox-multilingual
SPEC=$SRC/animeforge/cluster/episodes/$EPISODE_ID.json
OUT=$AF/out/$EPISODE_ID
# Resume on any node: work already copied home is carried over, so finished shots are not redone.
if [ ! -d "$OUT" ] && [ -d "$HOME/animeforge/out/$EPISODE_ID" ]; then
  mkdir -p "$AF/out" && cp -r "$HOME/animeforge/out/$EPISODE_ID" "$OUT"
fi
# Whatever happens next, finished shots go home so a retry (on any node) keeps them.
save_home() {
  [ -d "$OUT" ] || return 0
  mkdir -p "$HOME/animeforge/out/$EPISODE_ID" && cp -r "$OUT/." "$HOME/animeforge/out/$EPISODE_ID/" && du -sh "$HOME/animeforge/out/$EPISODE_ID"
}
trap save_home EXIT
PY=$AF/venv/bin/python
TTS=$AF/venv-tts/bin/python

$PY - <<'PYEOF'
import os
from animeforge import registry
ack = tuple(os.environ["ANIMEFORGE_ACK"].split(","))
for m in ("animagine-xl-4", "ipadapter-plus", "wan2.2-ti2v-5b", "chatterbox-multilingual", "whisper-large-v3"):
    registry.require(m, acknowledged=ack)
print("licence gate passed")
PYEOF

$PY -m animeforge.cluster.episode_job "$SPEC" "$OUT"

# The voice environment is built only now, so a slow package server cannot hold up the clips.
bash "$SRC/animeforge/cluster/setup_tts.sh"
SP=$($TTS -c "import site;print(site.getsitepackages()[0])")
export LD_LIBRARY_PATH=$(ls -d $SP/nvidia/*/lib | tr '\n' ':')${LD_LIBRARY_PATH:-}
$TTS -m animeforge.cluster.voice_job "$SPEC" "$OUT"

af_backup
