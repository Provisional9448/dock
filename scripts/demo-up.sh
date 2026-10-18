#!/usr/bin/env bash
# Start one inbound listener and its read-only evidence desk. Never restart existing sessions.
# Credentials may be configured outside Git in DOCK_ENV (default ~/.config/dock/env.sh).
set -euo pipefail

if (( $# )); then
  echo 'Usage: DOCK_INBOUND_MODE=live ./scripts/demo-up.sh (no replay argument)' >&2
  exit 1
fi
if [[ "${DOCK_INBOUND_MODE:-}" != live ]]; then
  echo 'Set DOCK_INBOUND_MODE=live explicitly after checking your included inbound allowance.' >&2
  exit 1
fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$repo_root"
dock_env="${DOCK_ENV:-$HOME/.config/dock/env.sh}"
if [[ -f "$dock_env" ]]; then
  # User-owned shell configuration; never print credential values.
  source "$dock_env"
fi
export DOCK_INBOUND_MODE=live
export DOCK_INBOUND_LOG="${DOCK_INBOUND_LOG:-$repo_root/data/runtime/inbound-demo.jsonl}"
export DOCK_INBOUND_AS_OF="${DOCK_INBOUND_AS_OF:-2026-10-17T19:36:00Z}"
desk_port="${PORT:-8741}"
if [[ ! "$desk_port" =~ ^[0-9]+$ ]] || (( 10#$desk_port < 1 || 10#$desk_port > 65535 )); then
  echo 'PORT must be an integer from 1 to 65535.' >&2
  exit 1
fi
if [[ -f /tmp/dock-inbound.pid ]]; then
  inbound_pid="$(cat -- /tmp/dock-inbound.pid)"
  if [[ "$inbound_pid" =~ ^[1-9][0-9]*$ ]] && kill -0 "$inbound_pid" 2>/dev/null; then
    echo 'An existing inbound listener is recorded in /tmp/dock-inbound.pid; leaving it untouched.' >&2
    exit 1
  fi
fi
command -v tmux >/dev/null
for session in dockweb dockvoice; do
  if tmux has-session -t "=$session" 2>/dev/null; then
    echo "Existing $session session found; leaving it untouched. Inspect it before starting another demo." >&2
    exit 1
  fi
done
if [[ -z "${GUAVA_AGENT_NUMBER:-}" ]]; then
  echo 'Configure GUAVA_AGENT_NUMBER in your environment or DOCK_ENV before starting.' >&2
  exit 1
fi

uv sync --frozen
uv run --frozen dock-inbound status --log "$DOCK_INBOUND_LOG" --as-of "$DOCK_INBOUND_AS_OF"

# tmux executes shell text: quote each path/value with bash printf %q, never credentials.
printf -v common 'cd -- %q; if [[ -f %q ]]; then source %q; fi; export DOCK_INBOUND_MODE=live DOCK_INBOUND_LOG=%q DOCK_INBOUND_AS_OF=%q GUAVA_AGENT_NUMBER=%q PATH=%q; ' \
  "$repo_root" "$dock_env" "$dock_env" "$DOCK_INBOUND_LOG" "$DOCK_INBOUND_AS_OF" "$GUAVA_AGENT_NUMBER" "$PATH"
printf -v web_args 'uv run --frozen dock-web --host 127.0.0.1 --port %q --runtime-log %q --as-of %q' \
  "$desk_port" "$DOCK_INBOUND_LOG" "$DOCK_INBOUND_AS_OF"
web_cmd="set -euo pipefail; ${common}${web_args} 2>&1 | tee -a /tmp/dockweb.log"
voice_cmd="set -euo pipefail; ${common}uv run --frozen dock-voice serve 2>&1 | tee -a /tmp/dockvoice.log"
printf -v web_shell 'bash -c %q' "$web_cmd"
printf -v voice_shell 'bash -c %q' "$voice_cmd"
tmux new-session -d -s dockweb "$web_shell"
tmux new-session -d -s dockvoice "$voice_shell"
echo "Started tmux sessions dockweb and dockvoice; inspect logs to confirm listener readiness."
echo "Desk on Zo: http://127.0.0.1:$desk_port"
echo "Shared inbound log: $DOCK_INBOUND_LOG; pinned demo time: $DOCK_INBOUND_AS_OF"
echo 'Logs: /tmp/dockweb.log and /tmp/dockvoice.log. No automatic retries or restarts.'
