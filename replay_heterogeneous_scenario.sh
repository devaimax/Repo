#!/bin/bash
# Wrapper: run the heterogeneous (4-node) replay from repository root.

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "▶ Running heterogeneous (4-node) replay"
"$ROOT_DIR/run_four_node_strategy.sh" "$@"

echo "✅ Heterogeneous replay finished"
