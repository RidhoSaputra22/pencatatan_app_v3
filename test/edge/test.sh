#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/matplotlib}"
mkdir -p "$MPLCONFIGDIR"

exec "$ROOT_DIR/edge/.venv/bin/python" "$ROOT_DIR/test/edge/run_video_tracking.py" "$@"
