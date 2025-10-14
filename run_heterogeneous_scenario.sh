#!/bin/bash
# Convenience wrapper to deploy and replay the heterogeneous four-node scenario.
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "🚀 Deploying heterogeneous (4-node) stack"
"$ROOT_DIR/scenarios/heterogeneous_4node/scripts/deploy.sh" "$@"

echo "▶ Running heterogeneous (4-node) replay"
"$ROOT_DIR/run_four_node_strategy.sh" "$@"

echo "✅ Heterogeneous scenario completed"
