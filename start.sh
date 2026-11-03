#!/usr/bin/env bash
# Starts the Streamlit tutor reliably in GitHub Codespaces.
#
# Why TLS detection: the Codespaces port forwarder talks to port 8501 either via plain HTTP
# or via HTTPS (port protocol "HTTPS" in the Ports tab). If Streamlit speaks the other
# protocol, the browser gets HTTP 502/504. In TLS=auto mode this script starts Streamlit
# with plain HTTP, tests the forwarded URL and, if that fails, restarts it with a
# self-signed certificate (.streamlit/certs, git-ignored).
#
# Usage:  bash start.sh [--foreground]
# Env:    PORT=8501   TLS=auto|on|off (default auto)   LOG=/tmp/streamlit-daml.log
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PORT="${PORT:-8501}"
LOG="${LOG:-/tmp/streamlit-daml.log}"
TLS_MODE="${TLS:-auto}"
PYTHON="$ROOT/.venv/bin/python"
CERT_DIR="$ROOT/.streamlit/certs"
MODE_FILE="$ROOT/.streamlit/certs/last_mode"
PID=""
SCHEME="http"

if [ ! -x "$PYTHON" ]; then
    echo "ERROR: $ROOT/.venv not found. Run: bash .devcontainer/setup.sh" >&2
    exit 1
fi
export PATH="$HOME/.daml/bin:$PATH"

if [ -n "${CODESPACE_NAME:-}" ]; then
    URL="https://${CODESPACE_NAME}-${PORT}.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
else
    URL=""
fi

stop_streamlit() {
    local pids
    pids="$(pgrep -f "streamlit run src/app.py" || true)"
    [ -z "$pids" ] && return 0
    echo "Stopping Streamlit instance(s): $(echo "$pids" | tr '\n' ' ')"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    for _ in $(seq 1 10); do pgrep -f "streamlit run src/app.py" >/dev/null || return 0; sleep 1; done
    pkill -9 -f "streamlit run src/app.py" 2>/dev/null || true
    sleep 1
}

ensure_cert() {
    if [ -s "$CERT_DIR/cert.pem" ] && [ -s "$CERT_DIR/key.pem" ]; then return 0; fi
    mkdir -p "$CERT_DIR"
    if ! openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj "/CN=localhost" \
        -keyout "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem" >/dev/null 2>&1; then
        echo "ERROR: openssl could not create a self-signed certificate." >&2
        return 1
    fi
    chmod 600 "$CERT_DIR/key.pem"
}

streamlit_args() {  # $1 = on|off
    ARGS=(-m streamlit run src/app.py --server.port "$PORT")
    SCHEME="http"
    if [ "$1" = "on" ]; then
        ensure_cert || return 1
        ARGS+=(--server.sslCertFile "$CERT_DIR/cert.pem" --server.sslKeyFile "$CERT_DIR/key.pem")
        SCHEME="https"
    fi
}

start_streamlit() {  # $1 = on|off ; returns 0 when the local health check is ok
    streamlit_args "$1" || return 1
    nohup "$PYTHON" "${ARGS[@]}" > "$LOG" 2>&1 &
    PID=$!
    echo -n "Starting Streamlit ($SCHEME, PID $PID) "
    for _ in $(seq 1 60); do
        if ! kill -0 "$PID" 2>/dev/null; then
            echo; echo "ERROR: Streamlit exited. Log ($LOG):" >&2; tail -20 "$LOG" >&2; return 1
        fi
        if curl -sfk -m 2 "$SCHEME://127.0.0.1:$PORT/_stcore/health" >/dev/null; then echo " ready"; return 0; fi
        echo -n "."; sleep 1
    done
    echo; echo "ERROR: local health check timed out." >&2
    return 1
}

# 0 = forwarded URL works, 1 = it does not, 2 = cannot be checked (not in Codespaces)
proxy_check() {
    [ -n "$URL" ] && [ -n "${GITHUB_TOKEN:-}" ] || return 2
    local hdr code="000"
    hdr="$(mktemp)"; chmod 600 "$hdr"
    printf 'X-Github-Token: %s\n' "$GITHUB_TOKEN" > "$hdr"   # builtin: token never appears in ps
    for _ in $(seq 1 6); do
        code="$(curl --http1.1 -s -m 15 -o /dev/null -w '%{http_code}' -H @"$hdr" "$URL/_stcore/health" || true)"
        [ "$code" = "200" ] && break
        sleep 3
    done
    rm -f "$hdr"
    echo "Forwarded URL check: HTTP $code"
    [ "$code" = "200" ]
}

stop_streamlit

if [ "${1:-}" = "--foreground" ]; then
    mode="$TLS_MODE"
    if [ "$mode" = "auto" ]; then mode="$(cat "$MODE_FILE" 2>/dev/null || echo off)"; fi
    streamlit_args "$mode" || exit 1
    echo "Foreground mode ($SCHEME). URL: ${URL:-$SCHEME://localhost:$PORT}"
    exec "$PYTHON" "${ARGS[@]}"
fi

case "$TLS_MODE" in
    on|off)
        start_streamlit "$TLS_MODE" || exit 1
        proxy_check; rc=$?
        ;;
    auto)
        start_streamlit off || exit 1
        proxy_check; rc=$?
        if [ $rc -eq 1 ]; then
            echo "Forwarder does not accept plain HTTP -> restarting Streamlit with TLS..."
            stop_streamlit
            start_streamlit on || exit 1
            proxy_check; rc=$?
            if [ $rc -ne 0 ]; then
                echo "TLS did not help either -> back to plain HTTP."
                stop_streamlit
                start_streamlit off || exit 1
            fi
        fi
        ;;
    *) echo "ERROR: TLS must be auto, on or off (got '$TLS_MODE')." >&2; exit 1 ;;
esac

mkdir -p "$CERT_DIR"
[ "$SCHEME" = "https" ] && echo on > "$MODE_FILE" || echo off > "$MODE_FILE"

echo "----------------------------------------------------------------"
echo "Streamlit PID $PID ($SCHEME), log: $LOG"
if [ -n "$URL" ]; then
    echo "Open: $URL"
    if [ "${rc:-2}" -ne 0 ]; then
        echo "WARNING: the forwarded URL did not answer. In the VS Code 'Ports' tab, check that"
        echo "port $PORT is listed (add it if missing) and try again: bash start.sh"
    fi
else
    echo "Open: $SCHEME://localhost:$PORT"
fi
