#!/bin/bash
# REELFORGE Ada bootstrap. Runs on the Ada LOGIN node (has internet).
# Installs a user-local Node.js into ~/reelforge/tools, installs the
# video-engine dependencies, and pre-downloads Remotion's headless browser.
# Idempotent: safe to re-run.
set -euo pipefail

ROOT="$HOME/reelforge"
TOOLS="$ROOT/tools"
mkdir -p "$TOOLS" "$ROOT/runs" "$ROOT/logs"

echo "== Node.js =="
if [ ! -x "$TOOLS/node/bin/node" ]; then
  VER=$(curl -sS https://nodejs.org/dist/index.json | python3 -c "import json,sys; d=json.load(sys.stdin); print([x['version'] for x in d if x['version'].startswith('v22.') and x.get('lts')][0])")
  echo "installing node $VER"
  curl -sSL "https://nodejs.org/dist/$VER/node-$VER-linux-x64.tar.xz" | tar xJ -C "$TOOLS"
  mv "$TOOLS/node-$VER-linux-x64" "$TOOLS/node"
fi
export PATH="$TOOLS/node/bin:$PATH"
node --version
npm --version

echo "== video-engine deps =="
cd "$ROOT/video-engine"
if [ -f package-lock.json ]; then
  npm ci --no-audit --no-fund 2>&1 | tail -3
else
  npm install --no-audit --no-fund 2>&1 | tail -3
fi

echo "== Remotion browser =="
npx remotion browser ensure 2>&1 | tail -3

echo "== versions =="
npx remotion versions 2>&1 | head -4
du -sh "$ROOT/video-engine/node_modules" "$TOOLS/node" 2>/dev/null
df -h "$HOME" | tail -1
echo "BOOTSTRAP_OK"
