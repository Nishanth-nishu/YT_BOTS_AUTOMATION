#!/bin/bash
#SBATCH -A plafnet2
#SBATCH -p plafnet2
#SBATCH -J af_lipsync
#SBATCH --exclude=gnode118
#SBATCH --gres=gpu:1
#SBATCH -c 6
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=animeforge/logs/lipsync_%j.log
# Phase 5 prototype: Arjuna says one line with audio-timed lip flaps.
set -euo pipefail

export ANIMEFORGE_HOME=/scratch/$USER/animeforge
AF=$ANIMEFORGE_HOME
SRC=$AF/src-$SLURM_JOB_ID
mkdir -p "$AF/tmp" && cp -r "$HOME/animeforge/src" "$SRC"
export HF_HOME=$AF/hf TMPDIR=$AF/tmp PYTHONPATH=$SRC ANIMEFORGE_MODELS_DIR=$AF/hf
bash "$SRC/animeforge/cluster/setup_env.sh"
bash "$SRC/animeforge/cluster/setup_tts.sh"
source "$SRC/animeforge/cluster/models_sync.sh"; af_restore "models--ResembleAI*" "models--cagliostrolab*"
export ANIMEFORGE_ACK=animagine-xl-4,chatterbox-multilingual
PY=$AF/venv/bin/python
TTS=$AF/venv-tts/bin/python
OUT=$AF/out/lipflap-arjuna
mkdir -p "$OUT"

if [ ! -f "$OUT/line.wav" ]; then
  SP=$($TTS -c "import site;print(site.getsitepackages()[0])")
  LD_LIBRARY_PATH=$(ls -d $SP/nvidia/*/lib | tr '\n' ':')${LD_LIBRARY_PATH:-} $TTS - "$OUT/line.wav" <<'PYEOF'
import sys, torch, torchaudio
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
m = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
torch.manual_seed(1234)
w = m.generate("गुरुदेव, मुझे केवल चिड़िया की आँख दिखाई दे रही है।", language_id="hi").detach().cpu()
w = w.unsqueeze(0) if w.dim() == 1 else w
torchaudio.save(sys.argv[1], w, m.sr, encoding="PCM_S", bits_per_sample=16)
PYEOF
fi

$PY -m animeforge.cluster.lipflap --voice "$OUT/line.wav" --out "$OUT" \
  --prompt "1boy, solo, original, young indian warrior prince, brown skin, long black hair in a topknot, small golden crown, ornate blue and gold armor, golden armbands, forest background"
af_backup
mkdir -p "$HOME/animeforge/out" && rm -rf "$HOME/animeforge/out/lipflap-arjuna" && cp -r "$OUT" "$HOME/animeforge/out/"
