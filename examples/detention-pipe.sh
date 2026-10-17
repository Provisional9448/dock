#!/usr/bin/env bash
# Facts in, detention trail out. Nothing is dialed and nothing is texted.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p data/runtime
uv run dock-events cat data/samples/harbor-rye.raw.jsonl \
  | uv run dock-clock --replay --as-of 2026-10-17T22:05:00Z \
  | uv run dock-notify \
  | uv run dock-proof --load LL-88421 --out data/runtime/LL-88421-trail.md
echo "wrote data/runtime/LL-88421-trail.md" >&2
