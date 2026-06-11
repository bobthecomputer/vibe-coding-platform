#!/usr/bin/env bash
set -eu

export PYTHONDONTWRITEBYTECODE=1

BASE="${SYNTHELOS_BASE:-/volume1/Saclay/projects/syntelos}"
CUR="${SYNTHELOS_ROOT:-$BASE/current}"
CTRL="$CUR/.agent_control"
PORT="${FLUXIO_WEB_PORT:-47880}"
HOST="${FLUXIO_WEB_HOST:-0.0.0.0}"
PUBLIC_URL="${FLUXIO_PUBLIC_URL:-https://sysnology.tail602108.ts.net:47880}"
CERT="${FLUXIO_TLS_CERT:-$BASE/certs/sysnology.tail602108.ts.net.crt}"
KEY="${FLUXIO_TLS_KEY:-$BASE/certs/sysnology.tail602108.ts.net.key}"
PYTHON="${FLUXIO_BACKEND_PYTHON:-$BASE/.venv/bin/python}"
LOG_DIR="$BASE/logs"
PID_FILE="$CTRL/web_backend_47880.pid"
OUT_LOG="$CTRL/web_backend_47880.out.log"
ERR_LOG="$CTRL/web_backend_47880.err.log"
COMBINED_LOG="$LOG_DIR/web_backend_47880.log"

mkdir -p "$LOG_DIR" "$CTRL"

if [ -L "$CUR" ]; then
  CUR="$(readlink -f "$CUR")"
  CTRL="$CUR/.agent_control"
  PID_FILE="$CTRL/web_backend_47880.pid"
  OUT_LOG="$CTRL/web_backend_47880.out.log"
  ERR_LOG="$CTRL/web_backend_47880.err.log"
  mkdir -p "$CTRL"
fi

export PATH="$BASE/runtime/bin:$PATH"
export FLUXIO_RUNTIME_BIN_DIR="$BASE/runtime/bin"
export HOME="$BASE/runtime/home"
export NPM_CONFIG_CACHE="$BASE/runtime/home/.npm"
export OPENCLAW_STATE_DIR="$BASE/runtime/home/.openclaw"
export FLUXIO_RUNTIME_DELEGATION_MODE="${FLUXIO_RUNTIME_DELEGATION_MODE:-local_shim}"
export SYNTELOS_MISSION_EVENTS_MAX_BYTES="${SYNTELOS_MISSION_EVENTS_MAX_BYTES:-10485760}"
export SYNTELOS_MISSION_EVENTS_KEEP_LINES="${SYNTELOS_MISSION_EVENTS_KEEP_LINES:-5000}"

if [ -f "$BASE/runtime/home/.fluxio_provider_env" ]; then
  set -a
  . "$BASE/runtime/home/.fluxio_provider_env"
  set +a
fi

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  kill "$(cat "$PID_FILE")" || true
  sleep 2
fi

for pid in $(ps -ef | awk -v port="$PORT" '/run_web_backend.py/ && $0 ~ "--port " port && !/awk/ {print $2}'); do
  kill "$pid" || true
done
sleep 2

cd "$CUR"
nohup "$PYTHON" scripts/run_web_backend.py \
  --host "$HOST" \
  --port "$PORT" \
  --allow-port-reuse \
  --root "$CUR" \
  --static-root "$CUR/web/dist" \
  --public-url "$PUBLIC_URL" \
  --tls-cert-file "$CERT" \
  --tls-key-file "$KEY" \
  > "$OUT_LOG" 2> "$ERR_LOG" &

backend_pid=$!
echo "$backend_pid" > "$PID_FILE"
printf 'Started Fluxio backend pid %s on %s:%s\n' "$backend_pid" "$HOST" "$PORT" | tee "$COMBINED_LOG"

sleep 4
if ! kill -0 "$backend_pid" 2>/dev/null; then
  printf 'Fluxio backend exited during startup. See %s and %s\n' "$OUT_LOG" "$ERR_LOG" >&2
  exit 1
fi

curl -sk --max-time 10 "https://127.0.0.1:$PORT/api/health" || curl -sk --max-time 10 "https://127.0.0.1:$PORT/health"
