#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT_DIR/apps/api"
ADMIN_DIR="$ROOT_DIR/apps/admin-web"
LOG_DIR="$ROOT_DIR/.local-run"

mkdir -p "$LOG_DIR"

API_PID_FILE="$LOG_DIR/api.pid"
ADMIN_PID_FILE="$LOG_DIR/admin-web.pid"

if [[ -z "${PYTHON_BIN:-}" && -x "$ROOT_DIR/.venv/bin/python" ]]; then
  export PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  export PYTHON_BIN="${PYTHON_BIN:-python3}"
fi
export DATABASE_URL="${DATABASE_URL:-sqlite:///./ai_field.db}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
export MINIO_ENDPOINT="${MINIO_ENDPOINT:-localhost:9000}"
export TASK_QUEUE_MODE="${TASK_QUEUE_MODE:-inline}"
export WECHAT_MOCK="${WECHAT_MOCK:-true}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173,http://127.0.0.1:5173}"
export VITE_API_BASE_URL="${VITE_API_BASE_URL:-/api/v1}"
export TARO_APP_API_BASE_URL="${TARO_APP_API_BASE_URL:-http://127.0.0.1:8000/api/v1}"
export API_HOST=127.0.0.1

cleanup() {
  if [[ -f "$API_PID_FILE" ]]; then
    pid="$(cat "$API_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$API_PID_FILE"
  fi

  if [[ -f "$ADMIN_PID_FILE" ]]; then
    pid="$(cat "$ADMIN_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$ADMIN_PID_FILE"
  fi
}
trap cleanup EXIT

echo "==> 初始化数据库与基础种子"
cd "$API_DIR"
"$PYTHON_BIN" -m alembic upgrade head
"$PYTHON_BIN" -m app.db.seed

echo "==> 启动 API: http://127.0.0.1:8000"
DATABASE_URL="$DATABASE_URL" \
REDIS_URL="$REDIS_URL" \
MINIO_ENDPOINT="$MINIO_ENDPOINT" \
TASK_QUEUE_MODE="$TASK_QUEUE_MODE" \
WECHAT_MOCK="$WECHAT_MOCK" \
"$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >"$LOG_DIR/api.log" 2>&1 &
echo $! > "$API_PID_FILE"

echo "==> 启动管理端: http://127.0.0.1:5173"
cd "$ADMIN_DIR"
pnpm dev --host 127.0.0.1 --port 5173 >"$LOG_DIR/admin-web.log" 2>&1 &
echo $! > "$ADMIN_PID_FILE"

echo "API pid: $(cat "$API_PID_FILE")"
echo "Admin pid: $(cat "$ADMIN_PID_FILE")"
echo "日志:"
echo "  API:    $LOG_DIR/api.log"
echo "  Admin:  $LOG_DIR/admin-web.log"
echo "按 Ctrl+C 停止。"

wait
