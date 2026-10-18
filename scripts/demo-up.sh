#!/usr/bin/env bash
# One command: live desk + inbound Guava line, in tmux. Re-run to restart.
#   ./scripts/demo-up.sh            # desk on :8741 + voice line
#   ./scripts/demo-up.sh replay     # same, then play the scripted scenario into the log (B-roll)
# Env (optional): GUAVA_AGENT_NUMBER, DOCK_LIVE_URL + DOCK_WRITE_TOKEN (write to a remote desk),
# or put exports in ~/.config/dock/env.sh. Needs `guava login` (or GUAVA_API_KEY) for the voice line.
set -euo pipefail
cd "$(dirname "$0")/.."
ENV="${DOCK_ENV:-$HOME/.config/dock/env.sh}"
SRC="[ -f $ENV ] && . $ENV;"
uv sync -q
tmux kill-session -t dockweb 2>/dev/null || true
tmux kill-session -t dockvoice 2>/dev/null || true
tmux new-session -d -s dockweb "$SRC uv run dock-web --live --port ${PORT:-8741} 2>&1 | tee -a /tmp/dockweb.log"
tmux new-session -d -s dockvoice "$SRC export PATH=\$HOME/.local/bin:\$PATH; while true; do uv run dock-voice serve 2>&1 | tee -a /tmp/dockvoice.log; echo restarting; sleep 2; done"
sleep 3
echo "Desk:  http://127.0.0.1:${PORT:-8741}   ${DOCK_LIVE_URL:-}"
echo "Line:  ${GUAVA_AGENT_NUMBER:-set GUAVA_AGENT_NUMBER}   (logs: /tmp/dockvoice.log, calls saved to demo/calls/)"
if [ "${1:-}" = "replay" ]; then
  bash -c "$SRC uv run dock-live replay --pause ${PAUSE:-8}"
fi
