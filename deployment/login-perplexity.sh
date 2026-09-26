#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_APP_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
APP_DIR="${APP_DIR:-$DEFAULT_APP_DIR}"
ENV_FILE="${ENV_FILE:-$APP_DIR/deployment/production.env}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Env file not found: $ENV_FILE" >&2
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

UV_BIN="$(command -v uv || true)"
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"

if [[ ! -x "$UV_BIN" ]]; then
    echo "Could not find uv: $UV_BIN" >&2
    exit 1
fi

cd "$APP_DIR"
"$UV_BIN" run perplexity-login "$@"
