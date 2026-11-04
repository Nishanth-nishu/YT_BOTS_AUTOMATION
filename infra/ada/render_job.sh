#!/bin/bash
# REELFORGE render job for Ada (SLURM). Submit with:
#   sbatch --export=ALL,COMP=Reel,PROPS=runs/<id>/spec.json,OUT=runs/<id>/reel.mp4,PROFILE=standard infra/ada/render_job.sh
# Never targets gnode118 (excluded below).
#SBATCH --job-name=reelforge-render
#SBATCH --partition=plafnet2
#SBATCH --account=plafnet2
#SBATCH --exclude=gnode118
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=/home2/%u/reelforge/logs/render_%j.log
set -euo pipefail

ROOT="$HOME/reelforge"
export PATH="$ROOT/tools/node/bin:$PATH"
module load u22/ffmpeg/7.1.1

COMP="${COMP:-SmokeTest}"
PROPS="${PROPS:-}"
OUT="${OUT:-runs/${COMP}_${SLURM_JOB_ID}.mp4}"
PROFILE="${PROFILE:-standard}"
CONCURRENCY="${CONCURRENCY:-8}"
CRF=18
if [ "$PROFILE" = "draft" ]; then CRF=24; fi
if [ "$PROFILE" = "cinematic" ]; then CRF=16; fi

cd "$ROOT/video-engine"
echo "node=$(hostname) job=$SLURM_JOB_ID comp=$COMP profile=$PROFILE conc=$CONCURRENCY"
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
mkdir -p "$(dirname "$ROOT/$OUT")"

RAW="$ROOT/${OUT%.mp4}.raw.mp4"
START=$(date +%s)
PROPS_ARG=()
if [ -n "$PROPS" ]; then PROPS_ARG=(--props="$ROOT/$PROPS"); fi

# Sample peak RSS of the whole job every 2 s in the background.
( while true; do ps -o rss= -u "$USER" | awk '{s+=$1} END {print s/1024}' >> "$ROOT/logs/mem_${SLURM_JOB_ID}.txt"; sleep 2; done ) &
MEMPID=$!

npx remotion render src/index.ts "$COMP" "$RAW" \
  --codec h264 --crf "$CRF" --concurrency "$CONCURRENCY" \
  --color-space bt709 --gl angle "${PROPS_ARG[@]}" --log=warn
RENDER_END=$(date +%s)
kill $MEMPID 2>/dev/null || true

# Two-pass loudness normalisation to -16 LUFS, true peak -1.5 dBFS.
LN=$(ffmpeg -nostats -i "$RAW" -af loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | python3 -c '
import sys, json
t = sys.stdin.read(); s = t.rfind("{"); e = t.rfind("}")
if s < 0: print("loudnorm=I=-16:TP=-1.5:LRA=11"); sys.exit()
m = json.loads(t[s:e+1])
print("loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true" % (m["input_i"], m["input_tp"], m["input_lra"], m["input_thresh"], m["target_offset"]))')

# Final encode with NVENC to Instagram-safe settings.
ffmpeg -y -v error -i "$RAW" \
  -c:v h264_nvenc -preset p5 -rc vbr -cq 20 -b:v 0 -profile:v high \
  -pix_fmt yuv420p -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -af "$LN" -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$ROOT/$OUT"
ENC_END=$(date +%s)

PEAK_MB=$(sort -n "$ROOT/logs/mem_${SLURM_JOB_ID}.txt" | tail -1)
echo "RENDER_SECONDS=$((RENDER_END-START)) ENCODE_SECONDS=$((ENC_END-RENDER_END)) PEAK_RSS_MB=${PEAK_MB}"
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,r_frame_rate,pix_fmt,color_range -of compact "$ROOT/$OUT"
rm -f "$RAW"
echo "JOB_OK"
