#!/bin/bash

# Quick fix for DNS naming issue in Prometheus configuration

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

clear

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║        Prometheus DNS Configuration Fix                   ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

STACK_NAME="monitor"

echo -e "${YELLOW}Issue Found:${NC}"
echo "  Prometheus was looking for DNS names with 'monitor_' prefix"
echo "  But Docker Swarm DNS uses service names without stack prefix"
echo ""
echo -e "${GREEN}Fix Applied:${NC}"
echo "  ❌ tasks.monitor_cadvisor  →  ✅ tasks.cadvisor"
echo "  ❌ tasks.monitor_fact_100k →  ✅ tasks.fact_100k"
echo "  ❌ tasks.monitor_fact_300k →  ✅ tasks.fact_300k"
echo "  ❌ tasks.monitor_fact_500k →  ✅ tasks.fact_500k"
echo "  ❌ tasks.monitor_matrix_4k →  ✅ tasks.matrix_4k"
echo "  ❌ tasks.monitor_matrix_5k →  ✅ tasks.matrix_5k"
echo ""

echo -n "Apply this fix now? (y/n): "
read -r response

if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "Fix cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}[1/4]${NC} Removing old Prometheus config..."
docker config rm ${STACK_NAME}_prometheus_config 2>/dev/null || true
echo -e "${GREEN}✓ Done${NC}"

echo ""
echo -e "${BLUE}[2/4]${NC} Creating new Prometheus config with correct DNS names..."
docker config create ${STACK_NAME}_prometheus_config ./prometheus.yml
echo -e "${GREEN}✓ Config created${NC}"

echo ""
echo -e "${BLUE}[3/4]${NC} Restarting Prometheus service..."
docker service update --config-rm ${STACK_NAME}_prometheus_config --config-add source=${STACK_NAME}_prometheus_config,target=/etc/prometheus/prometheus.yml ${STACK_NAME}_prometheus 2>/dev/null || {
    echo -e "${YELLOW}⚠ Config update failed, forcing service update...${NC}"
    docker service update --force ${STACK_NAME}_prometheus
}
echo -e "${GREEN}✓ Prometheus restarted${NC}"

echo ""
echo -e "${BLUE}[4/4]${NC} Waiting for Prometheus to reload configuration..."
sleep 10

# Wait for Prometheus to be healthy
for i in {1..6}; do
    if curl -s http://localhost:9090/-/healthy >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Prometheus is healthy${NC}"
        break
    fi
    echo "  Waiting... ${i}0s"
    sleep 10
done

echo ""
echo "═══════════════════════════════════════════════════════════"
echo -e "${GREEN}              DNS FIX APPLIED!                         ${NC}"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Wait a bit for targets to be discovered
echo "Waiting 30s for target discovery..."
sleep 30

echo ""
echo "Checking target status..."
echo ""

if [ -f "quick_status_check.sh" ]; then
    ./quick_status_check.sh
else
    echo "Run: ./quick_status_check.sh to verify"
fi

echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo "  1. Check Prometheus targets: ${YELLOW}http://<manager-ip>:9090/targets${NC}"
echo "  2. All targets should now be UP"
echo "  3. If issues persist, check service logs"
echo ""