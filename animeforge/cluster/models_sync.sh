#!/bin/bash
# Node scratch is purged after about 7 days; /share6 is persistent but is
# mounted only on the gateway. Jobs therefore copy the model cache to and from
# /share6 over SSH to the gateway (the same route the GEOM-Drugs data uses).
# Source this file, then call af_restore before using models and af_backup after
# downloading any. share6 has a 100 GB and 10,000-file quota: only model files
# go there (a few hundred files), never the Python environments.
AF_GW=${AF_GW:-ada-gw1}
AF_KEEP=${AF_KEEP:-/share6/$USER/animeforge/hf}
AF_SSH="ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new"

af_restore() {
  mkdir -p "$AF/hf"
  if ! $AF_SSH "$AF_GW" "test -d $AF_KEEP"; then echo "share6: no saved models yet"; return 0; fi
  echo "share6 -> scratch: restoring models that are missing here"
  rsync -a --ignore-existing --links -e "$AF_SSH" "$AF_GW:$AF_KEEP/" "$AF/hf/" && du -sh "$AF/hf"
}

af_backup() {
  local have_kb need_kb free_kb
  $AF_SSH "$AF_GW" "mkdir -p $AF_KEEP"
  have_kb=$($AF_SSH "$AF_GW" "du -sk $AF_KEEP | cut -f1")
  need_kb=$(( $(du -sk "$AF/hf" | cut -f1) - have_kb ))
  # quota line: used(KB) soft(KB) hard(KB) ...
  free_kb=$($AF_SSH "$AF_GW" "quota -w 2>/dev/null | awk '/share6/ {print \$3-\$2}'")
  echo "share6 backup: need $((need_kb/1048576)) GB more, quota has $(( ${free_kb:-0}/1048576 )) GB free"
  if [ "$need_kb" -le 0 ]; then echo "share6 already has everything"; return 0; fi
  if [ -z "$free_kb" ] || [ "$need_kb" -gt $(( free_kb - 2097152 )) ]; then
    echo "share6 backup REFUSED: it would leave under 2 GB of quota. Models on scratch will be purged in about 7 days."
    return 0
  fi
  rsync -a --links --exclude '*.incomplete' --exclude '.locks' -e "$AF_SSH" "$AF/hf/" "$AF_GW:$AF_KEEP/" \
    && echo "share6 backup done: $($AF_SSH "$AF_GW" "du -sh $AF_KEEP | cut -f1")"
}
