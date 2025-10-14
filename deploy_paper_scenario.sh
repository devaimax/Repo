#!/bin/bash
# Wrapper: deploy paper (3-node) monitoring stack from repository root.

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "🚀 Deploying paper (3-node) monitoring stack"
"$ROOT_DIR/scenarios/paper_3node/scripts/deploy.sh" "$@"

echo "✅ Paper scenario deployment finished"
