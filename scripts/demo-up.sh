#!/usr/bin/env bash
# One command: live desk + inbound Guava line, in tmux. Re-run to restart.
#   ./scripts/demo-up.sh            # desk on :8741 + voice line
#   ./scripts/demo-up.sh replay     # same, then play the scripted scenario into the log (B-roll)
# Env (optional): GUAVA_AGENT_NUMBER, or put exports in ~/.config/dock/env.sh. Needs `guava login` (or GUAVA_API_KEY).
# The voice line and the local desk share ONE log on this machine (data/runtime/live.jsonl) by default, so the
# desk you record at http://127.0.0.1:8741 shows every call. DOCK_LIVE_URL in env.sh is ignored unless
# DOCK_REMOTE=1 (remote desk writes need a matching DOCK_WRITE_TOKEN; a mismatch was a 403 on the 6:16 call).
set -euo pipefail
cd "$(dirname "$0")/.."
ENV="${DOCK_ENV:-$HOME/.config/dock/env.sh}"
SRC="[ -f $ENV ] && . $ENV;"
# Caller ID: the AgentLine demo phone is Luis (driver). DOCK_CALLER_ROLE=shipper ./scripts/demo-up.sh makes it Dan.
SRC="$SRC export DOCK_CALLER_ROLE=${DOCK_CALLER_ROLE:-};"
# Local log is the source; the voice line mirrors its events to DOCK_LIVE_URL (best effort, off the call path).
if [ "${DOCK_REMOTE:-0}" != "1" ]; then SRC="$SRC export DOCK_MIRROR_URL=\${DOCK_MIRROR_URL:-\${DOCK_LIVE_URL:-}}; unset DOCK_LIVE_URL;"; fi
uv sync -q
tmux kill-session -t dockweb 2>/dev/null || true
tmux kill-session -t dockvoice 2>/dev/null || true
tmux new-session -d -s dockweb "$SRC uv run dock-web --live --port ${PORT:-8741} 2>&1 | tee -a /tmp/dockweb.log"
tmux new-session -d -s dockvoice "$SRC export PATH=\$HOME/.local/bin:\$PATH; while true; do uv run dock-voice serve 2>&1 | tee -a /tmp/dockvoice.log; echo restarting; sleep 2; done"
sleep 3
echo "Desk:  http://127.0.0.1:${PORT:-8741}   (log: $([ "${DOCK_REMOTE:-0}" = 1 ] && echo remote desk || echo data/runtime/live.jsonl))"
echo "Line:  ${GUAVA_AGENT_NUMBER:-set GUAVA_AGENT_NUMBER}   (logs: /tmp/dockvoice.log, calls saved to demo/calls/)"
if [ "${1:-}" = "replay" ]; then
  bash -c "$SRC uv run dock-live replay --pause ${PAUSE:-8}"
fi
