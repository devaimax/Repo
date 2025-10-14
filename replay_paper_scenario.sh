#!/bin/bash
# Wrapper: run the paper (3-node) replay from repository root.

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "▶ Running paper (3-node) replay"
"$ROOT_DIR/scenarios/paper_3node/scripts/run_replay.sh" "$@"

echo "✅ Paper replay finished"
