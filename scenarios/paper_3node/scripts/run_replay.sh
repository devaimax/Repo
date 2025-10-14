#!/bin/bash
# Wrapper for the paper (3-node) scenario replay
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
SCENARIO=paper RUN_BASE="reports/paper_3node" "$ROOT_DIR/run_three_node_strategy.sh" "$@"
