#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="ai-provider-gateway"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_APP_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
APP_DIR="${APP_DIR:-$DEFAULT_APP_DIR}"
RUN_AS_USER="${RUN_AS_USER:-${SUDO_USER:-$(id -un)}}"
RUN_AS_GROUP="$(id -gn "$RUN_AS_USER")"
ENV_FILE="${ENV_FILE:-$APP_DIR/deployment/production.env}"
PORT="${PORT:-8002}"
WORKERS="${WORKERS:-1}"
APP_MODULE="${APP_MODULE:-ai_provider_gateway.api.app:app}"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
LOGROTATE_FILE="/etc/logrotate.d/${SERVICE_NAME}"
BROWSER_VERSION="ungoogled-chromium-154.0.8037.57-1-arm64_linux"
BROWSER_ARCHIVE="ungoogled-chromium-154.0.8037.57-1-arm64_linux.tar.xz"

if [[ "$(uname -s)" != "Linux" ]] || ! command -v systemctl >/dev/null; then
    echo "This deployment script requires a Linux system with systemd." >&2
    exit 1
fi

case "$(uname -m)" in
    aarch64|arm64) ;;
    *)
        echo "This deployment requires an ARM64 host; found $(uname -m)." >&2
        exit 1
        ;;
esac

if [[ ! -f "$APP_DIR/pyproject.toml" ]] || [[ ! -f "$APP_DIR/deployment/${SERVICE_NAME}.service" ]]; then
    echo "APP_DIR must be the repository root: $APP_DIR" >&2
    exit 1
fi

if [[ $EUID -ne 0 ]]; then
    exec sudo --preserve-env=APP_DIR,RUN_AS_USER,ENV_FILE,PORT,WORKERS,APP_MODULE,LOG_FILE "$0"
fi

if ! id "$RUN_AS_USER" >/dev/null 2>&1; then
    echo "RUN_AS_USER does not exist: $RUN_AS_USER" >&2
    exit 1
fi

if ! command -v git >/dev/null; then
    echo "git is required." >&2
    exit 1
fi

if ! command -v curl >/dev/null; then
    echo "curl is required to install uv when it is missing." >&2
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    install -D -m 0600 -o root -g "$RUN_AS_GROUP" "$APP_DIR/deployment/production.env.example" "$ENV_FILE"
    echo "Created $ENV_FILE. Set AI_PROVIDER_GATEWAY_API_KEY, then rerun this script." >&2
    exit 1
fi

if grep -qE '^AI_PROVIDER_GATEWAY_API_KEY=($|replace-with-)' "$ENV_FILE"; then
    echo "Set a non-placeholder AI_PROVIDER_GATEWAY_API_KEY in $ENV_FILE, then rerun this script." >&2
    exit 1
fi

PROJECTS_FILE="$(awk -F= '$1 == "WEB_GOOGLE_FLOW_PROJECTS_FILE" { print substr($0, index($0, "=") + 1); exit }' "$ENV_FILE")"
if [[ -n "$PROJECTS_FILE" ]] && [[ ! -r "$PROJECTS_FILE" ]]; then
    echo "WEB_GOOGLE_FLOW_PROJECTS_FILE is not readable: $PROJECTS_FILE" >&2
    exit 1
fi

STATE_DIR="$(awk -F= '$1 == "AI_PROVIDER_GATEWAY_STATE_DIR" { print substr($0, index($0, "=") + 1); exit }' "$ENV_FILE")"
STATE_DIR="${STATE_DIR:-/var/lib/ai-provider-gateway}"
LOG_FILE="${LOG_FILE:-$STATE_DIR/ai-provider-gateway.log}"

git -C "$APP_DIR" submodule update --init --recursive

UV_BIN="$(sudo -u "$RUN_AS_USER" -H sh -c 'command -v uv' || true)"
if [[ -z "$UV_BIN" ]]; then
    sudo -u "$RUN_AS_USER" -H sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
    UV_BIN="$(sudo -u "$RUN_AS_USER" -H sh -c 'command -v uv || printf "%s/.local/bin/uv" "$HOME"')"
fi

if [[ ! -x "$UV_BIN" ]]; then
    echo "Could not find uv after installation: $UV_BIN" >&2
    exit 1
fi

install -d -m 0750 -o "$RUN_AS_USER" -g "$RUN_AS_GROUP" "$STATE_DIR"
# Failure captures (screenshots/HTML of logged-in provider pages): owner-only.
install -d -m 0700 -o "$RUN_AS_USER" -g "$RUN_AS_GROUP" "$STATE_DIR/web-automation"
install -d -m 0700 -o "$RUN_AS_USER" -g "$RUN_AS_GROUP" "$STATE_DIR/web-automation/failures"
install -d -m 0750 -o "$RUN_AS_USER" -g "$RUN_AS_GROUP" "$(dirname -- "$LOG_FILE")"
touch "$LOG_FILE"
chown "$RUN_AS_USER:$RUN_AS_GROUP" "$LOG_FILE"
chmod 0640 "$LOG_FILE"

BROWSER_SOURCE_DIR="$APP_DIR/binaries/ungoogled-chromium"
BROWSER_ARCHIVE_PATH="$BROWSER_SOURCE_DIR/$BROWSER_ARCHIVE"
BROWSER_ROOT="$STATE_DIR/browser"
BROWSER_DIR="$BROWSER_ROOT/$BROWSER_VERSION"
BROWSER_EXECUTABLE="$BROWSER_DIR/chrome"
if [[ ! -f "$BROWSER_ARCHIVE_PATH" ]]; then
    echo "Bundled ungoogled-chromium archive is missing: $BROWSER_ARCHIVE_PATH" >&2
    exit 1
fi
if ! (cd "$BROWSER_SOURCE_DIR" && sha256sum --check --status SHA256SUMS); then
    echo "Bundled ungoogled-chromium archive checksum mismatch." >&2
    exit 1
fi
install -d -m 0750 -o "$RUN_AS_USER" -g "$RUN_AS_GROUP" "$BROWSER_ROOT"
if [[ ! -x "$BROWSER_EXECUTABLE" ]]; then
    temporary_browser_dir="$(mktemp -d "$BROWSER_ROOT/.${BROWSER_VERSION}.tmp.XXXXXX")"
    trap 'rm -rf "$temporary_browser_dir"' EXIT
    tar -xJf "$BROWSER_ARCHIVE_PATH" -C "$temporary_browser_dir"
    if [[ ! -x "$temporary_browser_dir/$BROWSER_VERSION/chrome" ]]; then
        echo "Bundled ungoogled-chromium archive has an unexpected layout." >&2
        exit 1
    fi
    rm -rf "$BROWSER_DIR"
    mv "$temporary_browser_dir/$BROWSER_VERSION" "$BROWSER_DIR"
    rmdir "$temporary_browser_dir"
    trap - EXIT
fi
chown -R "$RUN_AS_USER:$RUN_AS_GROUP" "$BROWSER_DIR"
if ! sudo -u "$RUN_AS_USER" -H "$BROWSER_EXECUTABLE" --version; then
    echo "Installed ungoogled-chromium could not start: $BROWSER_EXECUTABLE" >&2
    exit 1
fi
sudo -u "$RUN_AS_USER" -H "$UV_BIN" sync --frozen --extra driver --directory "$APP_DIR"

sed \
    -e "s|__RUN_AS_USER__|$RUN_AS_USER|g" \
    -e "s|__APP_DIR__|$APP_DIR|g" \
    -e "s|__ENV_FILE__|$ENV_FILE|g" \
    -e "s|__UV_BIN__|$UV_BIN|g" \
    -e "s|__APP_MODULE__|$APP_MODULE|g" \
    -e "s|__PORT__|$PORT|g" \
    -e "s|__WORKERS__|$WORKERS|g" \
    -e "s|__LOG_FILE__|$LOG_FILE|g" \
    "$APP_DIR/deployment/${SERVICE_NAME}.service" > "$UNIT_FILE"

cat > "$LOGROTATE_FILE" <<EOF
$LOG_FILE {
    daily
    dateext
    dateformat -%Y%m%d
    rotate 30
    maxage 30
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
    su $RUN_AS_USER $RUN_AS_GROUP
}
EOF
chmod 0644 "$LOGROTATE_FILE"

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
systemctl is-active --quiet "$SERVICE_NAME"

for _ in {1..15}; do
    if health="$(curl --fail --silent "http://127.0.0.1:${PORT}/health" 2>/dev/null)"; then
        echo "Deployment complete: $health"
        exit 0
    fi
    sleep 1
done

systemctl status "$SERVICE_NAME" --no-pager >&2 || true
echo "Service started but /health did not become available." >&2
exit 1
