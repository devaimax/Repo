#!/bin/bash
# Script: run_single_cycle.sh
# الهدف: تشغيل استراتيجيات السوارم (Spread → Manual → Auto) دورة واحدة متتابعة مع إعادة نشر كاملة لضمان نتائج حديثة.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./run_single_cycle.sh [before|after]

Environment overrides:
  PROM_URL             Prometheus endpoint (default: http://localhost:9090)
  EXPORT_WINDOW        نافذة التصدير بالدقائق (default: 10)
  OUTPUT_BASE          مجلد التخزين الأساسي (default: reports/replay/single_cycle)
  SPREAD_FORCE         اضبطها على 0 لتعطيل docker service update --force أثناء baseline
  AUTO_FORCE_REDEPLOY  اضبطها على 0 لتعطيل إجبار إعادة النشر في الاستراتيجية الآلية
EOF
}

PHASE=${PHASE:-before}
if [[ $# -gt 0 ]]; then
  case "$1" in
    before|after)
      PHASE="$1"
      shift
      ;;
    -*)
      usage
      exit 1
      ;;
    *)
      usage
      exit 1
      ;;
  esac
fi

if [[ $# -gt 0 ]]; then
  usage
  exit 1
fi

PHASE=$(echo "$PHASE" | tr '[:upper:]' '[:lower:]')
if [[ "$PHASE" != "before" && "$PHASE" != "after" ]]; then
  echo "❌ Invalid phase: $PHASE (expected before or after)"
  exit 1
fi

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROM_URL=${PROM_URL:-http://localhost:9090}
EXPORT_WINDOW=${EXPORT_WINDOW:-10}
OUTPUT_BASE=${OUTPUT_BASE:-reports/replay/single_cycle}
SPREAD_FORCE=${SPREAD_FORCE:-1}
AUTO_FORCE_REDEPLOY=${AUTO_FORCE_REDEPLOY:-1}

mkdir -p "$OUTPUT_BASE"
echo "🚀 Single-cycle replay → phase=$PHASE, output=$OUTPUT_BASE"
echo "🔗 Prometheus: $PROM_URL (window=${EXPORT_WINDOW}m)"

rm -f logs/cache/replay_spread_samples.json \
      logs/cache/replay_manual_samples.json \
      logs/cache/replay_auto_weighted_samples.json \
      logs/cache/excel_samples.json 2>/dev/null || true

SPREAD_ARGS=()
if [[ "$SPREAD_FORCE" != "0" ]]; then
  SPREAD_ARGS+=(--force)
fi

PROM_URL="$PROM_URL" \
EXPORT_WINDOW="$EXPORT_WINDOW" \
OUTPUT_BASE="$OUTPUT_BASE" \
"$ROOT_DIR/run_strategy.sh" spread "$PHASE" "${SPREAD_ARGS[@]}"

PROM_URL="$PROM_URL" \
EXPORT_WINDOW="$EXPORT_WINDOW" \
OUTPUT_BASE="$OUTPUT_BASE" \
"$ROOT_DIR/run_strategy.sh" manual "$PHASE"

PROM_URL="$PROM_URL" \
EXPORT_WINDOW="$EXPORT_WINDOW" \
OUTPUT_BASE="$OUTPUT_BASE" \
AUTO_FORCE_REDEPLOY="$AUTO_FORCE_REDEPLOY" \
"$ROOT_DIR/run_strategy.sh" auto "$PHASE"

echo "✅ Single-cycle replay completed. Review Excel files under $OUTPUT_BASE/$PHASE"
