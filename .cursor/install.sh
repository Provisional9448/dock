#!/usr/bin/env bash
# Cloud Agent and teammate bootstrap. Idempotent. Does not log in or read secrets.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Non-interactive login shells do not load ~/.bashrc, so a binary that only
# lives in ~/.local/bin is invisible to later install and agent commands.
link_tool() {
  local name="$1"
  local source="${HOME}/.local/bin/${name}"
  if [[ -x "${source}" ]]; then
    sudo ln -sf "${source}" "/usr/local/bin/${name}"
  fi
}

if ! command -v uv >/dev/null 2>&1 && [[ ! -x "${HOME}/.local/bin/uv" ]]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
link_tool uv

if [[ ! -x "${HOME}/.local/bin/guava" ]]; then
  curl -fsSL https://goguava.ai/install.sh | sh
fi
link_tool guava

cd "${ROOT}"
uv sync --frozen
