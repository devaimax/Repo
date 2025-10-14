#!/bin/bash
# Script: run_complete_workflow.sh
# Purpose: Execute both the paper (3-node) and realistic (5-node) scenarios end-to-end.
# Steps:
#   1. Deploy the 3-node stack and run its replay workflow.
#   2. Deploy the 5-node heterogeneous stack and run its replay workflow.

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "🚀 [1/4] Deploying paper (3-node) stack"
"$ROOT_DIR/scenarios/paper_3node/scripts/deploy.sh"

echo "▶ [2/4] Running paper (3-node) replay"
"$ROOT_DIR/scenarios/paper_3node/scripts/run_replay.sh"

echo "🚀 [3/4] Deploying realistic (5-node) stack"
"$ROOT_DIR/scenarios/realistic_5node/scripts/deploy.sh"

echo "▶ [4/4] Running realistic (5-node) replay"
"$ROOT_DIR/run_five_node_strategy.sh"

echo "✅ Workflow complete"
