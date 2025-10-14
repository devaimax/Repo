#!/bin/bash
# Wrapper: run the realistic (5-node) replay from repository root.

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "▶ Running realistic (5-node) replay"
"$ROOT_DIR/run_five_node_strategy.sh" "$@"

echo "✅ Realistic replay finished"
