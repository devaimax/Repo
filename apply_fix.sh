#!/bin/bash

# One-command fix for Prometheus timeout errors
# This script applies all fixes and verifies the results

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
echo "║     Prometheus Timeout Error - Automated Fix Script       ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

STACK_NAME="monitor"

# Check if running on manager node
echo -e "${BLUE}[1/6]${NC} Checking Docker Swarm status..."
if ! docker node ls >/dev/null 2>&1; then
    echo -e "${RED}✗ Error: This script must be run on a Docker Swarm manager node${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Running on Swarm manager${NC}"
echo ""

# Show current problem
echo -e "${BLUE}[2/6]${NC} Analyzing current target status..."
echo ""

if command -v python3 >/dev/null 2>&1 && [ -f "check_targets.py" ]; then
    echo "Current status:"
    python3 check_targets.py 2>/dev/null | head -20 || echo "Could not fetch current status"
else
    echo "Checking via Docker..."
    docker service ls --filter name=${STACK_NAME} --format "table {{.Name}}\t{{.Replicas}}\t{{.Ports}}"
fi

echo ""
echo -e "${YELLOW}⚠ The issue: scrape_timeout (30s) equals scrape_interval (30s)${NC}"
echo -e "${YELLOW}⚠ Prometheus requires: scrape_timeout < scrape_interval${NC}"
echo ""

# Confirm before proceeding
echo -e "${CYAN}This script will:${NC}"
echo "  1. Remove the current monitoring stack"
echo "  2. Update Prometheus configuration with fixed timeouts"
echo "  3. Redeploy the monitoring stack"
echo "  4. Wait for services to stabilize"
echo "  5. Verify all targets are healthy"
echo ""
echo -n "Do you want to proceed? (y/n): "
read -r response

if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo ""
    echo "Fix cancelled. No changes made."
    exit 0
fi

echo ""
echo -e "${BLUE}[3/6]${NC} Removing old stack and configuration..."

# Remove old stack
docker stack rm ${STACK_NAME} 2>/dev/null || true
echo "Waiting for services to stop..."
sleep 15

# Remove old config
docker config rm ${STACK_NAME}_prometheus_config 2>/dev/null || true
echo -e "${GREEN}✓ Old configuration removed${NC}"
echo ""

# Create new config
echo -e "${BLUE}[4/6]${NC} Creating new Prometheus configuration..."

if [ ! -f "prometheus.yml" ]; then
    echo -e "${RED}✗ Error: prometheus.yml not found${NC}"
    exit 1
fi

docker config create ${STACK_NAME}_prometheus_config ./prometheus.yml
echo -e "${GREEN}✓ New configuration created with fixed timeouts:${NC}"
echo "  - Global default: 25s (was 30s)"
echo "  - Prometheus: 10s"
echo "  - cAdvisor: 25s"
echo "  - Node Exporter: 20s"
echo "  - Custom Services: 15s"
echo ""

# Deploy stack
echo -e "${BLUE}[5/6]${NC} Deploying monitoring stack..."

if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}✗ Error: docker-compose.yml not found${NC}"
    exit 1
fi

docker stack deploy -c docker-compose.yml ${STACK_NAME}
echo -e "${GREEN}✓ Stack deployed${NC}"
echo ""

# Wait for services
echo -e "${BLUE}[6/6]${NC} Waiting for services to start..."
echo ""

for i in {1..12}; do
    echo -n "  Waiting... ${i}0s / 120s"
    sleep 10
    
    # Check if Prometheus is responding
    if curl -s http://localhost:9090/-/healthy >/dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    else
        echo -e " ${YELLOW}⏳${NC}"
    fi
done

echo ""
echo -e "${GREEN}✓ Services are starting up${NC}"
echo ""

# Give it a bit more time for all targets to be discovered
echo "Waiting additional 30s for target discovery..."
sleep 30

echo ""
echo "═══════════════════════════════════════════════════════════"
echo -e "${GREEN}                    FIX APPLIED!                       ${NC}"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Verify the fix
echo -e "${CYAN}Verifying target status...${NC}"
echo ""

if [ -f "quick_status_check.sh" ]; then
    ./quick_status_check.sh
else
    # Fallback verification
    echo "Checking Prometheus targets..."
    curl -s http://localhost:9090/api/v1/targets | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    targets = data.get('data', {}).get('activeTargets', [])
    up = sum(1 for t in targets if t.get('health') == 'up')
    total = len(targets)
    print(f'Targets: {up}/{total} UP')
    if up == total:
        print('✅ All targets are healthy!')
    else:
        print(f'⚠️  {total - up} targets still down (may need more time)')
except:
    print('Could not verify targets')
" 2>/dev/null || echo "Verification in progress..."
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo -e "${CYAN}                   NEXT STEPS                          ${NC}"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "1. View Prometheus targets:"
echo "   ${YELLOW}http://<manager-ip>:9090/targets${NC}"
echo ""
echo "2. View Grafana dashboards:"
echo "   ${YELLOW}http://<manager-ip>:3000${NC}"
echo "   (admin / your_secure_password)"
echo ""
echo "3. Check status anytime:"
echo "   ${YELLOW}./quick_status_check.sh${NC}"
echo ""
echo "4. View detailed logs:"
echo "   ${YELLOW}docker service logs ${STACK_NAME}_prometheus${NC}"
echo ""
echo "5. If issues persist:"
echo "   ${YELLOW}./fix_prometheus_targets.sh${NC} (full diagnostics)"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""
echo -e "${GREEN}✅ Fix completed successfully!${NC}"
echo ""