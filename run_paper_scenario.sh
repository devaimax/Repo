#!/bin/bash
# Convenience wrapper to deploy and replay the paper (3-node) scenario.
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "🚀 Deploying paper (3-node) stack"
"$ROOT_DIR/scenarios/paper_3node/scripts/deploy.sh" "$@"

echo "▶ Running paper (3-node) replay"
"$ROOT_DIR/scenarios/paper_3node/scripts/run_replay.sh" "$@"

echo "✅ Paper scenario completed"
