#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/start-backend.sh [--host HOST] [--port PORT] [--no-reload]

Start the AlphaAgents backend from WSL/Linux.

Options:
  --host HOST    Bind host (default: BACKEND_HOST or 127.0.0.1)
  --port PORT    Bind port (default: BACKEND_PORT or 8000)
  --no-reload    Disable uvicorn reload
  -h, --help     Show this help
USAGE
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

HOST="${BACKEND_HOST:-127.0.0.1}"
PORT="${BACKEND_PORT:-8000}"
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
    --port)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --port" >&2
        exit 2
      fi
      PORT="$2"
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
      echo "Run scripts/start-backend.sh --help for usage." >&2
      exit 2
      ;;
  esac
done

PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing virtualenv Python: $PYTHON_BIN" >&2
  echo "Create .venv in the repo root and install dependencies before starting the backend." >&2
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

echo "Backend URL: http://$HOST:$PORT"
echo "Frontend URL: http://127.0.0.1:5173 when scripts/start-dev.sh is running"
echo

cd "$REPO_ROOT"
exec "$PYTHON_BIN" -m uvicorn app.main:app --app-dir api --host "$HOST" --port "$PORT" "${reload_args[@]}"
