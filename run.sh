#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
EDGE_DIR="$ROOT_DIR/edge"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_NAME="${BACKEND_NAME:-visitor-backend}"
EDGE_NAME="${EDGE_NAME:-visitor-edge}"
FRONTEND_NAME="${FRONTEND_NAME:-visitor-frontend}"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_SCRIPT="${FRONTEND_SCRIPT:-dev}"

log() {
  printf '[run.sh] %s\n' "$*"
}

die() {
  printf '[run.sh] %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Pemakaian:
  ./run.sh [start|restart|stop|delete|status|logs]

Perintah:
  start    Menyalakan frontend, backend, dan edge via PM2
  restart  Restart semua service (akan dibuat ulang jika belum ada)
  stop     Stop semua service tanpa menghapusnya dari PM2
  delete   Hapus semua service dari PM2
  status   Tampilkan status service PM2
  logs     Tampilkan log ketiga service

Environment opsional:
  FRONTEND_SCRIPT=dev|start
  BACKEND_HOST=0.0.0.0
  BACKEND_PORT=8000
  BACKEND_NAME=visitor-backend
  EDGE_NAME=visitor-edge
  FRONTEND_NAME=visitor-frontend
EOF
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Command '$1' tidak ditemukan."
}

to_service_command() {
  local binary_path="$1"
  local service_dir="$2"

  case "$binary_path" in
    "$service_dir"/*)
      printf '.%s\n' "${binary_path#$service_dir}"
      ;;
    *)
      printf '%s\n' "$binary_path"
      ;;
  esac
}

find_python() {
  local service_dir="$1"
  local candidates=(
    "$service_dir/.venv/bin/python"
    "$service_dir/venv/bin/python"
    "$service_dir/.venv/Scripts/python.exe"
    "$service_dir/venv/Scripts/python.exe"
  )
  local candidate

  for candidate in "${candidates[@]}"; do
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  if command -v python3.12 >/dev/null 2>&1; then
    command -v python3.12
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi

  return 1
}

find_uvicorn() {
  local service_dir="$1"
  local candidates=(
    "$service_dir/.venv/bin/uvicorn"
    "$service_dir/venv/bin/uvicorn"
    "$service_dir/.venv/Scripts/uvicorn.exe"
    "$service_dir/venv/Scripts/uvicorn.exe"
  )
  local candidate

  for candidate in "${candidates[@]}"; do
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  if command -v uvicorn >/dev/null 2>&1; then
    command -v uvicorn
    return 0
  fi

  return 1
}

pm2_has_process() {
  pm2 jlist | grep -Fq "\"name\":\"$1\""
}

delete_if_exists() {
  local name="$1"

  if pm2_has_process "$name"; then
    log "Menghapus proses lama: $name"
    pm2 delete "$name" >/dev/null
  fi
}

stop_if_exists() {
  local name="$1"

  if pm2_has_process "$name"; then
    log "Menghentikan proses: $name"
    pm2 stop "$name" >/dev/null
  fi
}

start_backend() {
  local uvicorn_bin="$1"
  local uvicorn_cmd quoted_uvicorn quoted_host quoted_port

  delete_if_exists "$BACKEND_NAME"
  log "Menyalakan backend di http://localhost:$BACKEND_PORT"
  uvicorn_cmd="$(to_service_command "$uvicorn_bin" "$BACKEND_DIR")"
  printf -v quoted_uvicorn '%q' "$uvicorn_cmd"
  printf -v quoted_host '%q' "$BACKEND_HOST"
  printf -v quoted_port '%q' "$BACKEND_PORT"
  pm2 start bash \
    --name "$BACKEND_NAME" \
    --cwd "$BACKEND_DIR" \
    -- -lc "exec $quoted_uvicorn app.main:app --host $quoted_host --port $quoted_port" >/dev/null
}

start_edge() {
  local python_bin="$1"
  local python_cmd quoted_python

  delete_if_exists "$EDGE_NAME"
  log "Menyalakan edge worker"
  python_cmd="$(to_service_command "$python_bin" "$EDGE_DIR")"
  printf -v quoted_python '%q' "$python_cmd"
  pm2 start bash \
    --name "$EDGE_NAME" \
    --cwd "$EDGE_DIR" \
    -- -lc "exec $quoted_python worker.py" >/dev/null
}

start_frontend() {
  delete_if_exists "$FRONTEND_NAME"
  log "Menyalakan frontend dengan script npm '$FRONTEND_SCRIPT'"
  pm2 start npm \
    --name "$FRONTEND_NAME" \
    --cwd "$FRONTEND_DIR" \
    -- run "$FRONTEND_SCRIPT" >/dev/null
}

save_pm2_state() {
  pm2 save >/dev/null
}

show_status() {
  pm2 list
}

start_services() {
  local backend_python edge_python uvicorn_bin

  require_cmd pm2
  require_cmd npm

  backend_python="$(find_python "$BACKEND_DIR")" || die "Python backend tidak ditemukan."
  edge_python="$(find_python "$EDGE_DIR")" || die "Python edge tidak ditemukan."
  uvicorn_bin="$(find_uvicorn "$BACKEND_DIR")" || die "uvicorn backend tidak ditemukan."

  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    log "Peringatan: frontend/node_modules belum ada. Jika start gagal, jalankan npm install di folder frontend."
  fi

  log "Backend python : $backend_python"
  log "Edge python    : $edge_python"
  log "Backend uvicorn: $uvicorn_bin"

  start_backend "$uvicorn_bin"
  start_edge "$edge_python"
  start_frontend
  save_pm2_state
  show_status
}

restart_services() {
  start_services
}

stop_services() {
  require_cmd pm2
  stop_if_exists "$FRONTEND_NAME"
  stop_if_exists "$EDGE_NAME"
  stop_if_exists "$BACKEND_NAME"
  save_pm2_state
  show_status
}

delete_services() {
  require_cmd pm2
  delete_if_exists "$FRONTEND_NAME"
  delete_if_exists "$EDGE_NAME"
  delete_if_exists "$BACKEND_NAME"
  save_pm2_state
  show_status
}

show_logs() {
  require_cmd pm2
  pm2 logs "$BACKEND_NAME" "$EDGE_NAME" "$FRONTEND_NAME"
}

main() {
  local action="${1:-start}"

  case "$action" in
    start)
      start_services
      ;;
    restart)
      restart_services
      ;;
    stop)
      stop_services
      ;;
    delete)
      delete_services
      ;;
    status)
      show_status
      ;;
    logs)
      show_logs
      ;;
    -h|--help|help)
      usage
      ;;
    *)
      usage
      die "Perintah tidak dikenali: $action"
      ;;
  esac
}

main "$@"
