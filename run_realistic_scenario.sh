#!/bin/bash
# Convenience wrapper to deploy and replay the realistic five-node scenario.
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "🚀 Deploying realistic (5-node) stack"
"$ROOT_DIR/scenarios/realistic_5node/scripts/deploy.sh" "$@"

echo "▶ Running realistic (5-node) replay"
"$ROOT_DIR/run_five_node_strategy.sh" "$@"

echo "✅ Realistic scenario completed"
