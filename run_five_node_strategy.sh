#!/bin/bash
# Script: run_five_node_strategy.sh
# Purpose: Replay strategies for the full five-node heterogeneous cluster.

set -euo pipefail

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

if [[ -n "${CUSTOM_SERVICES:-}" ]]; then
  # shellcheck disable=SC2206
  SERVICES=(${CUSTOM_SERVICES})
fi

PROM_URL=${PROM_URL:-http://localhost:9090}
EXPORT_WINDOW=${EXPORT_WINDOW:-10}
SETTLE_SECONDS=${SETTLE_SECONDS:-120}
RESTART_ITERATIONS=${RESTART_ITERATIONS:-1}
RESTART_INTERVAL=${RESTART_INTERVAL:-70}

TIMESTAMP=$(date +%F_%H%M%S)
RUN_DIR=${RUN_DIR:-"scenarios/realistic_5node/reports/replay/five_node_run_${TIMESTAMP}"}

echo "🚀 Five-node heterogeneous replay → ${RUN_DIR}"

# Ensure compose/prometheus configuration is deployed for this scenario
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [[ ${DEPLOY_SCENARIO:-1} -eq 1 ]]; then
  echo "📦 Redeploying monitoring stack for realistic scenario"
  "$ROOT_DIR/scenarios/realistic_5node/scripts/deploy.sh"
fi

# Ensure the additional workers are active before running the scenario
ACTIVATE_NODES=${ACTIVATE_NODES:-"node-03 node-04"}
for NODE in $ACTIVATE_NODES; do
  echo "✅ Activating $NODE"
  docker node update --availability active "$NODE" || true
done

CUSTOM_SERVICES="${SERVICES[*]}" \
PROM_URL="$PROM_URL" \
EXPORT_WINDOW="$EXPORT_WINDOW" \
SETTLE_SECONDS="$SETTLE_SECONDS" \
RESTART_ITERATIONS="$RESTART_ITERATIONS" \
RESTART_INTERVAL="$RESTART_INTERVAL" \
RUN_DIR="$RUN_DIR" \
RUN_BASE="scenarios/realistic_5node/reports" \
./run_all_strategies.sh

echo "✅ Five-node replay complete. Outputs stored under ${RUN_DIR}"
