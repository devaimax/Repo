#!/bin/bash

# Final Fix for Prometheus DNS Issues
# This script fixes the DNS names and forces DNS cache refresh

set -e

echo "═══════════════════════════════════════════════════════════"
echo "     Prometheus DNS Fix - Final Solution"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Issue Identified:${NC}"
echo "  - Docker Swarm DNS was caching stale IPs from previous deployments"
echo "  - Service names need 'monitor_' prefix (e.g., tasks.monitor_cadvisor)"
echo "  - DNS cache needs to be cleared by restarting Prometheus"
echo ""

echo -e "${YELLOW}Solution:${NC}"
echo "  1. Update prometheus.yml with correct DNS names (tasks.monitor_*)"
echo "  2. Remove old Prometheus config from Docker"
echo "  3. Create new config with corrected DNS names"
echo "  4. Force Prometheus service restart to clear DNS cache"
echo ""

read -p "Press Enter to continue or Ctrl+C to cancel..."
echo ""

# Step 1: Verify the prometheus.yml has been updated
echo "Step 1: Verifying prometheus.yml configuration..."
if grep -q "tasks.monitor_cadvisor" prometheus.yml && \
   grep -q "tasks.monitor_node-exporter" prometheus.yml && \
   grep -q "tasks.monitor_fact_100k" prometheus.yml; then
    echo -e "${GREEN}✓${NC} prometheus.yml has correct DNS names"
else
    echo -e "${RED}✗${NC} prometheus.yml needs to be updated"
    echo "Please ensure prometheus.yml uses 'tasks.monitor_*' DNS names"
    exit 1
fi

# Step 2: Get current config version
echo ""
echo "Step 2: Checking current Prometheus config..."
CURRENT_CONFIG=$(docker service inspect monitor_prometheus --format '{{range .Spec.TaskTemplate.ContainerSpec.Configs}}{{.ConfigName}}{{end}}' 2>/dev/null || echo "")

if [ -z "$CURRENT_CONFIG" ]; then
    echo -e "${YELLOW}⚠${NC} No config found attached to Prometheus service"
else
    echo -e "${GREEN}✓${NC} Current config: $CURRENT_CONFIG"
fi

# Step 3: Remove config from service
echo ""
echo "Step 3: Removing config from Prometheus service..."
docker service update --config-rm prometheus_config monitor_prometheus 2>/dev/null || echo "Config already removed or doesn't exist"
sleep 2

# Step 4: Delete old config
echo ""
echo "Step 4: Deleting old Docker config..."
docker config rm prometheus_config 2>/dev/null || echo "Config already deleted or doesn't exist"
sleep 1

# Step 5: Create new config
echo ""
echo "Step 5: Creating new Prometheus config with correct DNS names..."
docker config create prometheus_config prometheus.yml
echo -e "${GREEN}✓${NC} New config created"

# Step 6: Add config to service
echo ""
echo "Step 6: Attaching new config to Prometheus service..."
docker service update \
    --config-add source=prometheus_config,target=/etc/prometheus/prometheus.yml \
    monitor_prometheus

echo -e "${GREEN}✓${NC} Config attached to service"

# Step 7: Force service restart to clear DNS cache
echo ""
echo "Step 7: Forcing Prometheus service restart to clear DNS cache..."
docker service update --force monitor_prometheus

echo -e "${GREEN}✓${NC} Service restart initiated"

# Step 8: Wait for service to be ready
echo ""
echo "Step 8: Waiting for Prometheus to be ready..."
echo "This may take 30-60 seconds..."

for i in {1..60}; do
    if curl -s http://localhost:9090/-/ready > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Prometheus is ready!"
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

# Step 9: Wait for DNS to refresh
echo ""
echo "Step 9: Waiting for DNS cache to refresh and targets to be discovered..."
echo "Waiting 30 seconds for DNS refresh..."
sleep 30

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "                    FIX APPLIED!"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Step 10: Check target status
echo "Verifying target status..."
echo ""

if [ -f "./quick_status_check.sh" ]; then
    bash ./quick_status_check.sh
else
    echo "Checking targets manually..."
    curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | grep -E '"health"|"job"' | head -20
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "                   NEXT STEPS"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "1. View Prometheus targets:"
echo -e "   ${YELLOW}http://<manager-ip>:9090/targets${NC}"
echo ""
echo "2. If some targets are still down:"
echo "   - Wait another 30-60 seconds for DNS to fully refresh"
echo "   - Run: ./quick_status_check.sh"
echo "   - Check service logs: docker service logs monitor_<service-name>"
echo ""
echo "3. Verify DNS resolution from Prometheus container:"
echo "   PROM=\$(docker ps --filter 'name=monitor_prometheus' --format '{{.ID}}' | head -1)"
echo "   docker exec \$PROM nslookup tasks.monitor_cadvisor"
echo ""
echo "4. If DNS issues persist, consider using static IPs:"
echo "   - Use prometheus.enhanced.yml instead"
echo "   - Update docker-compose.yml to use prometheus.enhanced.yml"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""
echo -e "${GREEN}✅ Fix completed successfully!${NC}"
echo ""