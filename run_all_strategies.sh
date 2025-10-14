#!/bin/bash
# Script: run_all_strategies.sh
# يجمع الاستراتيجيات الثلاث (Spread, Manual, Auto) ويصدر النتائج في مجلد واحد
# مع ملف CSV موحد لجميع الخدمات (القديمة والجديدة).

set -euo pipefail

PROM_URL=${PROM_URL:-http://localhost:9090}
EXPORT_WINDOW=${EXPORT_WINDOW:-1}
SETTLE_SECONDS=${SETTLE_SECONDS:-30}
RESTART_ITERATIONS=${RESTART_ITERATIONS:-0}
RESTART_INTERVAL=${RESTART_INTERVAL:-30}

# القائمة الافتراضية للخدمات (factorial + matrix بكامل الإصدارات)
SERVICES=(
  monitor_fact_100k
  monitor_fact_200k
  monitor_fact_300k
  monitor_fact_400k
  monitor_fact_500k
  monitor_matrix_4k
  monitor_matrix_5k
  monitor_matrix_6k
  monitor_matrix_7k
  monitor_matrix_8k
)

# تمكين المستخدم من تمرير قائمة مختلفة عبر متغير البيئة CUSTOM_SERVICES
if [[ -n "${CUSTOM_SERVICES:-}" ]]; then
  # shellcheck disable=SC2206
  SERVICES=(${CUSTOM_SERVICES})
fi

TIMESTAMP=$(date +%F_%H%M%S)
RUN_BASE=${RUN_BASE:-"reports/replay"}
RUN_DIR=${RUN_DIR:-"${RUN_BASE}/full_run_${TIMESTAMP}"}
mkdir -p "$RUN_DIR"

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEFAULT_PYTHON="$ROOT_DIR/venv/bin/python3"
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

echo "🚀 Running full strategy replay (Spread → Manual → Auto)"

# حذف أي ملفات كاش سابقة لضمان جمع عينات جديدة من Prometheus فقط
rm -f logs/cache/replay_spread_samples.json \
      logs/cache/replay_manual_samples.json \
      logs/cache/replay_auto_weighted_samples.json \
      logs/cache/excel_samples.json 2>/dev/null || true

"$PYTHON_BIN" collector/replay_strategies.py \
  --prom-url "$PROM_URL" \
  --window-minutes "$EXPORT_WINDOW" \
  --settle-seconds "$SETTLE_SECONDS" \
  --restart-iterations "$RESTART_ITERATIONS" \
  --restart-interval "$RESTART_INTERVAL" \
  --output-dir "$RUN_DIR" \
  --services "${SERVICES[@]}"

echo "📦 Exported per-strategy CSV files into $RUN_DIR"

RUN_DIR_ENV="$RUN_DIR" "$PYTHON_BIN" - <<'PY'
import os
import pandas as pd
from pathlib import Path

run_dir = Path(os.environ["RUN_DIR_ENV"])

results_files = {
    "spread_results_metrics.csv": "spread",
    "manual_results_metrics.csv": "manual",
    "auto_weighted_results_metrics.csv": "auto",
}

weights_files = {
    "spread_weights_metrics.csv": "spread",
    "manual_weights_metrics.csv": "manual",
    "auto_weighted_weights_metrics.csv": "auto",
}

def combine(files_map, output_name):
    frames = []
    for filename, strategy in files_map.items():
        path = run_dir / filename
        if not path.exists():
            print(f"⚠️ Missing {filename}; skipping in combined output")
            continue
        df = pd.read_csv(path)
        df.insert(0, "strategy", strategy)
        frames.append(df)
    if not frames:
        print(f"⚠️ No data available to write {output_name}")
        return
    combined = pd.concat(frames, ignore_index=True)
    out_path = run_dir / output_name
    combined.to_csv(out_path, index=False)
    print(f"✅ Wrote {out_path}")

combine(results_files, "combined_strategy_results.csv")
combine(weights_files, "combined_strategy_weights.csv")
PY

echo "🏁 Full replay complete. Review combined CSV files inside $RUN_DIR"
