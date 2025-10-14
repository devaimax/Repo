#!/bin/bash
# Wrapper: deploy realistic (5-node) monitoring stack from repository root.

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "🚀 Deploying realistic (5-node) monitoring stack"

# Ensure heterogeneous workers are active before deployment kicks off
docker node update --availability active node-03 || true
docker node update --availability active node-04 || true

"$ROOT_DIR/scenarios/realistic_5node/scripts/deploy.sh" "$@"

echo "✅ Realistic scenario deployment finished"
