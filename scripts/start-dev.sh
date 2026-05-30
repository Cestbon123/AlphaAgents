#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/start-dev.sh [--host HOST] [--backend-port PORT] [--frontend-port PORT] [--no-reload]

Start the AlphaAgents backend and frontend from WSL/Linux.

Options:
  --host HOST           Bind host for both services (default: DEV_HOST or 127.0.0.1)
  --backend-port PORT   Backend port (default: BACKEND_PORT or 8000)
  --frontend-port PORT  Frontend port (default: FRONTEND_PORT or 5173)
  --no-reload           Disable uvicorn reload
  -h, --help            Show this help
USAGE
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

HOST="${DEV_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
RELOAD="${BACKEND_RELOAD:-1}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --host" >&2
        exit 2
      fi
      HOST="$2"
      shift 2
      ;;
    --backend-port)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --backend-port" >&2
        exit 2
      fi
      BACKEND_PORT="$2"
      shift 2
      ;;
    --frontend-port)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --frontend-port" >&2
        exit 2
      fi
      FRONTEND_PORT="$2"
      shift 2
      ;;
    --no-reload)
      RELOAD="0"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Run scripts/start-dev.sh --help for usage." >&2
      exit 2
      ;;
  esac
done

PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
FRONTEND_DIR="$REPO_ROOT/frontend"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing virtualenv Python: $PYTHON_BIN" >&2
  echo "Create .venv in the repo root and install dependencies before starting dev services." >&2
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR" ]]; then
  echo "Missing frontend directory: $FRONTEND_DIR" >&2
  exit 1
fi

reload_args=()
case "${RELOAD,,}" in
  0|false|no|off)
    ;;
  *)
    reload_args=(--reload)
    ;;
esac

trap cleanup EXIT INT TERM

cd "$REPO_ROOT"

echo "Backend URL:  http://$HOST:$BACKEND_PORT"
echo "Frontend URL: http://$HOST:$FRONTEND_PORT"
echo "Press Ctrl+C to stop both services."
echo

"$PYTHON_BIN" -m uvicorn app.main:app --app-dir api --host "$HOST" --port "$BACKEND_PORT" "${reload_args[@]}" &
BACKEND_PID="$!"

"$PYTHON_BIN" -m http.server "$FRONTEND_PORT" --bind "$HOST" --directory "$FRONTEND_DIR" &
FRONTEND_PID="$!"

wait -n "$BACKEND_PID" "$FRONTEND_PID"
