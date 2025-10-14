#!/bin/bash
# Script: run_auto_strategy.sh
# الهدف: تشغيل المجدول التلقائي مرّة واحدة وتخزين النتائج في ملف مستقل للمقارنة.

set -euo pipefail

PROM_URL=${PROM_URL:-http://localhost:9090}
EXPORT_WINDOW=${EXPORT_WINDOW:-10}
OUT_DIR=${OUT_DIR:-reports/replay}
TIMESTAMP=$(date +%F_%H%M%S)
OUT_FILE=${OUT_FILE:-$OUT_DIR/auto_${TIMESTAMP}.xlsx}

mkdir -p "$OUT_DIR"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEFAULT_PYTHON="$SCRIPT_DIR/venv/bin/python3"
PYTHON_BIN=${PYTHON_BIN:-}
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$DEFAULT_PYTHON" ]]; then
    PYTHON_BIN="$DEFAULT_PYTHON"
  else
    PYTHON_BIN=$(command -v python3)
    if [[ -z "$PYTHON_BIN" ]]; then
      echo "❌ Unable to locate python3 interpreter. Set PYTHON_BIN to continue." >&2
      exit 1
    fi
  fi
fi

EXPORT_EXCEL=1 \
EXPORT_EXCEL_OUT="$OUT_FILE" \
EXPORT_EXCEL_WINDOW="$EXPORT_WINDOW" \
PROM_URL="$PROM_URL" \
"$PYTHON_BIN" collector/auto_weight_scheduler.py "$@"

echo "✅ Auto-weighting metrics exported to $OUT_FILE"
