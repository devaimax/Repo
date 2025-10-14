#!/bin/bash
# Wrapper for the heterogeneous four-node scenario replay
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
RUN_BASE="scenarios/heterogeneous_4node/reports" "$ROOT_DIR/run_four_node_strategy.sh" "$@"
