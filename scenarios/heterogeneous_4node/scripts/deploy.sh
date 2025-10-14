#!/bin/bash
# Deploy monitoring stack for the heterogeneous 4-node scenario.
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
CONFIG_ROOT="$ROOT_DIR/scenarios/heterogeneous_4node/compose"

SERVICES_TO_REMOVE=(
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
  monitor_prometheus
  monitor_grafana
  monitor_cadvisor
  monitor_node-exporter
)

for svc in "${SERVICES_TO_REMOVE[@]}"; do
  if docker service ls --format "{{.Name}}" | grep -Fxq "${svc}"; then
    echo "🧹 Removing stale service ${svc}"
    docker service rm "${svc}" || true
  fi
done

CONFIG_ROOT="$CONFIG_ROOT" "$ROOT_DIR/deploy_monitoring.sh" --enhanced "$@"
