#!/bin/bash
# Wrapper for the realistic five-node scenario replay
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
SCENARIO=realistic RUN_BASE="scenarios/realistic_5node/reports" "$ROOT_DIR/run_five_node_strategy.sh" "$@"
