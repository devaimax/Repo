#!/bin/bash
# Script: run_spread_strategy.sh
# الهدف: إعادة تعيين الخدمات إلى استراتيجية Spread القياسية ثم حفظ القياسات في ملف مستقل.

set -euo pipefail

PROM_URL=${PROM_URL:-http://localhost:9090}
EXPORT_WINDOW=${EXPORT_WINDOW:-10}
OUT_DIR=${OUT_DIR:-reports/replay}
TIMESTAMP=$(date +%F_%H%M%S)
OUT_FILE=${OUT_FILE:-$OUT_DIR/spread_${TIMESTAMP}.xlsx}

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

"$PYTHON_BIN" collector/spread_reset.py \
  --force \
  --prom-url "$PROM_URL" \
  --export-excel \
  --export-out "$OUT_FILE" \
  --export-window "$EXPORT_WINDOW" \
  "$@"

echo "✅ Spread metrics exported to $OUT_FILE"
