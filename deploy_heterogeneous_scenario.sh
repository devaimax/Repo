#!/bin/bash
# Wrapper: deploy heterogeneous (4-node) monitoring stack from repository root.

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "🚀 Deploying heterogeneous (4-node) monitoring stack"

# Guarantee all worker nodes are active before deployment
docker node update --availability active node-01 || true
docker node update --availability active node-02 || true
docker node update --availability active node-03 || true
docker node update --availability active node-04 || true

"$ROOT_DIR/scenarios/heterogeneous_4node/scripts/deploy.sh" "$@"

echo "✅ Heterogeneous scenario deployment finished"
