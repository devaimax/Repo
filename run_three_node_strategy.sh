#!/bin/bash
# Script: run_three_node_strategy.sh
# Purpose: Replay Spread/Manual/Auto strategies for the 3-node scenario (paper baseline).

set -euo pipefail

# Baseline services from the original paper scenario (manager + two workers)
SERVICES=(
  monitor_fact_100k
  monitor_fact_300k
  monitor_fact_500k
  monitor_matrix_4k
  monitor_matrix_5k
)

# Allow overriding via environment variable if needed
if [[ -n "${CUSTOM_SERVICES:-}" ]]; then
  # shellcheck disable=SC2206
  SERVICES=(${CUSTOM_SERVICES})
fi

# Default configuration mirrors the research replay options
PROM_URL=${PROM_URL:-http://localhost:9090}
EXPORT_WINDOW=${EXPORT_WINDOW:-10}
SETTLE_SECONDS=${SETTLE_SECONDS:-120}
RESTART_ITERATIONS=${RESTART_ITERATIONS:-1}
RESTART_INTERVAL=${RESTART_INTERVAL:-70}

TIMESTAMP=$(date +%F_%H%M%S)
RUN_DIR=${RUN_DIR:-"scenarios/paper_3node/reports/replay/three_node_run_${TIMESTAMP}"}

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEPLOY_SCENARIO=${DEPLOY_SCENARIO:-1}

echo "🚀 Three-node baseline replay → ${RUN_DIR}"

# Drain extra workers so that only manager + node-01 + node-02 participate
DRAIN_NODES=${DRAIN_NODES:-"node-03 node-04"}
for NODE in $DRAIN_NODES; do
  echo "🛑 Draining $NODE"
  docker node update --availability drain "$NODE" || true
done

if [[ "$DEPLOY_SCENARIO" -eq 1 ]]; then
  echo "📦 Redeploying monitoring stack for paper scenario"
  "$ROOT_DIR/scenarios/paper_3node/scripts/deploy.sh"
fi

echo "🧹 Clearing legacy node constraints (node-03/node-04)"
docker service update --constraint-rm 'node.hostname==node-04' monitor_fact_500k || true
docker service update --constraint-rm 'node.hostname==node-03' monitor_fact_200k || true
docker service update --constraint-rm 'node.hostname==node-03' monitor_matrix_6k || true
docker service update --constraint-rm 'node.hostname==node-03' monitor_matrix_8k || true
docker service update --constraint-rm 'node.hostname==node-04' monitor_matrix_7k || true

CUSTOM_SERVICES="${SERVICES[*]}" \
PROM_URL="$PROM_URL" \
EXPORT_WINDOW="$EXPORT_WINDOW" \
SETTLE_SECONDS="$SETTLE_SECONDS" \
RESTART_ITERATIONS="$RESTART_ITERATIONS" \
RESTART_INTERVAL="$RESTART_INTERVAL" \
RUN_DIR="$RUN_DIR" \
RUN_BASE="scenarios/paper_3node/reports" \
./run_all_strategies.sh

echo "✅ Three-node replay complete. Outputs stored under ${RUN_DIR}"
