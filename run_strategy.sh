#!/bin/bash
# Script: run_strategy.sh
# الهدف: تشغيل استراتيجية واحدة (Spread أو Manual أو Auto) وتخزين النتائج
# داخل مجلد منظم حسب اسم الاستراتيجية ومرحلة تشغيل الكلستر (قبل/بعد التوسيع).

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./run_strategy.sh <strategy> [before|after] [-- extra args]

strategy: spread | manual | auto
phase   : before (default) or after

Any additional arguments are forwarded to the underlying strategy runner,
e.g.:
  ./run_strategy.sh manual after --services monitor_fact_100k monitor_matrix_4k

Environment variables:
  PROM_URL      Prometheus endpoint (forwarded when supported)
  EXPORT_WINDOW Sampling window in minutes (forwarded when supported)
  OUTPUT_BASE   Base directory for archived results (default: reports/replay/strategies)
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

STRATEGY=$(echo "$1" | tr '[:upper:]' '[:lower:]')
case "$STRATEGY" in
  spread|manual|auto)
    ;;
  *)
    echo "❌ Unknown strategy: $1"
    usage
    exit 1
    ;;
esac
shift

PHASE="before"
EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    before|after)
      PHASE="$1"
      shift
      ;;
    --phase)
      if [[ $# -lt 2 ]]; then
        echo "❌ --phase requires a value (before|after)"
        exit 1
      fi
      PHASE="$2"
      shift 2
      ;;
    --phase=*)
      PHASE="${1#*=}"
      shift
      ;;
    --)
      shift
      EXTRA_ARGS+=("$@")
      break
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

PHASE=$(echo "$PHASE" | tr '[:upper:]' '[:lower:]')
if [[ "$PHASE" != "before" && "$PHASE" != "after" ]]; then
  echo "❌ Invalid phase: $PHASE (expected before or after)"
  exit 1
fi

OUTPUT_BASE=${OUTPUT_BASE:-reports/replay/strategies}
TIMESTAMP=$(date +%F_%H%M%S)
PHASE_DIR="$OUTPUT_BASE/$STRATEGY/$PHASE"
mkdir -p "$PHASE_DIR"

OUT_FILE="$PHASE_DIR/${STRATEGY}_${PHASE}_${TIMESTAMP}.xlsx"

echo "🚀 Running $STRATEGY strategy ($PHASE phase)"
echo "📂 Results will be stored under: $PHASE_DIR"

case "$STRATEGY" in
  spread)
    OUT_DIR="$PHASE_DIR" \
    OUT_FILE="$OUT_FILE" \
    ./run_spread_strategy.sh "${EXTRA_ARGS[@]}"
    ;;
  manual)
    OUT_DIR="$PHASE_DIR" \
    OUT_FILE="$OUT_FILE" \
    ./run_manual_strategy.sh "${EXTRA_ARGS[@]}"
    ;;
  auto)
    OUT_DIR="$PHASE_DIR" \
    OUT_FILE="$OUT_FILE" \
    ./run_auto_strategy.sh "${EXTRA_ARGS[@]}"
    ;;
esac

echo "✅ Archived ${STRATEGY^} strategy output → $OUT_FILE"
