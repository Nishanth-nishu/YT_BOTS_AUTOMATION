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

# af_restore                      restore everything saved
# af_restore PATTERN [PATTERN...]  restore only hub folders matching, e.g. "models--cagliostrolab*"
af_restore() {
  mkdir -p "$AF/hf"
  if ! $AF_SSH "$AF_GW" "test -d $AF_KEEP"; then echo "share6: no saved models yet"; return 0; fi
  echo "share6 -> scratch: restoring models that are missing here ${*:+(only: $*)}"
  if [ "$#" -eq 0 ]; then
    rsync -a --ignore-existing --links -e "$AF_SSH" "$AF_GW:$AF_KEEP/" "$AF/hf/" && du -sh "$AF/hf"
    return
  fi
  # The cache keeps the weights in hub/blobs and each model folder holds only
  # links to them, so a model's restore list is its folder plus the blobs its links name.
  local list="$AF/restore-$$.list" dirs
  dirs=$(printf 'hub/%s ' "$@")
  $AF_SSH "$AF_GW" "cd $AF_KEEP && { find $dirs \( -type f -o -type l \) -print; find $dirs -type l -exec realpath --relative-to=. {} \; ; } 2>/dev/null | sort -u" > "$list"
  echo "restore list: $(wc -l < "$list") files"
  rsync -a --ignore-existing --links --files-from="$list" -e "$AF_SSH" "$AF_GW:$AF_KEEP/" "$AF/hf/" && du -sh "$AF/hf"
  rm -f "$list"
}

af_backup() {
  local need_kb free_kb
  $AF_SSH "$AF_GW" "mkdir -p $AF_KEEP"
  # Size of what this node has and share6 lacks (a dry run), not a difference of totals:
  # a node holding only two models was told "already has everything" while a new one went unsaved.
  need_kb=$(rsync -an --stats --links --exclude '*.incomplete' --exclude '.locks' -e "$AF_SSH" "$AF/hf/" "$AF_GW:$AF_KEEP/"             | awk -F: '/Total transferred file size/ {gsub(/[^0-9]/, "", $2); print int($2/1024)}')
  need_kb=${need_kb:-0}
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
