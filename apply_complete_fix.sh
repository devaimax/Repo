#!/bin/bash

# Complete Fix for Prometheus Monitoring Stack
# This script applies all necessary fixes including:
# - Correct DNS names (tasks.monitor_*)
# - Proper timeout configuration
# - Alert rules configuration
# - DNS cache refresh

set -e

echo "═══════════════════════════════════════════════════════════"
echo "     Prometheus Complete Fix - All Issues"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Issues Being Fixed:${NC}"
echo "  ✓ DNS names with correct 'monitor_' prefix"
echo "  ✓ Proper timeout configuration (scrape_timeout < scrape_interval)"
echo "  ✓ Alert rules configuration mounting"
echo "  ✓ DNS cache refresh"
echo ""

echo -e "${YELLOW}Prerequisites Check:${NC}"

# Check if running on manager node
if ! docker node ls &> /dev/null; then
    echo -e "${RED}✗${NC} This script must be run on a Docker Swarm manager node"
    exit 1
fi
echo -e "${GREEN}✓${NC} Running on Swarm manager node"

# Check if required files exist
if [ ! -f "prometheus.yml" ]; then
    echo -e "${RED}✗${NC} prometheus.yml not found"
    exit 1
fi
echo -e "${GREEN}✓${NC} prometheus.yml found"

if [ ! -f "alert.rules.yml" ]; then
    echo -e "${RED}✗${NC} alert.rules.yml not found"
    exit 1
fi
echo -e "${GREEN}✓${NC} alert.rules.yml found"

if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}✗${NC} docker-compose.yml not found"
    exit 1
fi
echo -e "${GREEN}✓${NC} docker-compose.yml found"

# Verify prometheus.yml has correct DNS names
if grep -q "tasks.monitor_cadvisor" prometheus.yml && \
   grep -q "tasks.monitor_node-exporter" prometheus.yml && \
   grep -q "tasks.monitor_fact_100k" prometheus.yml; then
    echo -e "${GREEN}✓${NC} prometheus.yml has correct DNS names"
else
    echo -e "${RED}✗${NC} prometheus.yml needs correct DNS names"
    exit 1
fi

# Verify docker-compose.yml has alert rules config
if grep -q "alert_rules_config" docker-compose.yml; then
    echo -e "${GREEN}✓${NC} docker-compose.yml has alert rules configuration"
else
    echo -e "${RED}✗${NC} docker-compose.yml missing alert rules configuration"
    exit 1
fi

echo ""
echo -e "${YELLOW}Current Stack Status:${NC}"
if docker stack ls | grep -q "monitor"; then
    echo -e "${GREEN}✓${NC} Monitor stack is deployed"
    docker service ls | grep monitor_ || true
else
    echo -e "${YELLOW}⚠${NC} Monitor stack not deployed yet"
fi

echo ""
read -p "Press Enter to apply the fix or Ctrl+C to cancel..."
echo ""

# Step 1: Remove old stack first (this will release the configs)
echo "Step 1: Removing old monitor stack..."
if docker stack ls | grep -q "monitor"; then
    docker stack rm monitor
    echo -e "${GREEN}✓${NC} Stack removed"
    echo "Waiting for services to stop and configs to be released..."
    sleep 20
else
    echo -e "${YELLOW}⚠${NC} Stack not deployed (OK)"
fi

# Step 2: Remove old configs if they exist (including stack-prefixed ones)
echo ""
echo "Step 2: Cleaning up old configurations..."
docker config rm prometheus_config 2>/dev/null && echo -e "${GREEN}✓${NC} Removed old prometheus_config" || echo -e "${YELLOW}⚠${NC} prometheus_config doesn't exist (OK)"
docker config rm alert_rules_config 2>/dev/null && echo -e "${GREEN}✓${NC} Removed old alert_rules_config" || echo -e "${YELLOW}⚠${NC} alert_rules_config doesn't exist (OK)"
docker config rm monitor_prometheus_config 2>/dev/null && echo -e "${GREEN}✓${NC} Removed old monitor_prometheus_config" || echo -e "${YELLOW}⚠${NC} monitor_prometheus_config doesn't exist (OK)"
docker config rm monitor_alert_rules_config 2>/dev/null && echo -e "${GREEN}✓${NC} Removed old monitor_alert_rules_config" || echo -e "${YELLOW}⚠${NC} monitor_alert_rules_config doesn't exist (OK)"
sleep 2

# Step 3: Create new configs
echo ""
echo "Step 3: Creating new configurations..."
docker config create prometheus_config prometheus.yml
echo -e "${GREEN}✓${NC} Created prometheus_config"

docker config create alert_rules_config alert.rules.yml
echo -e "${GREEN}✓${NC} Created alert_rules_config"

# Step 4: Verify network exists
echo ""
echo "Step 4: Verifying monitor-net network..."
if docker network ls | grep -q "monitor-net"; then
    echo -e "${GREEN}✓${NC} Network monitor-net exists"
else
    echo "Creating monitor-net network..."
    docker network create --driver overlay --attachable monitor-net
    echo -e "${GREEN}✓${NC} Network created"
fi

# Step 5: Deploy the stack
echo ""
echo "Step 5: Deploying monitor stack with fixed configuration..."
docker stack deploy -c docker-compose.yml monitor
echo -e "${GREEN}✓${NC} Stack deployed"

# Step 6: Wait for services to start
echo ""
echo "Step 6: Waiting for services to start..."
echo "This may take 30-60 seconds..."
sleep 30

# Step 7: Check service status
echo ""
echo "Step 7: Checking service status..."
echo ""
docker service ls | grep monitor_

# Step 8: Wait for Prometheus to be ready
echo ""
echo "Step 8: Waiting for Prometheus to be ready..."
for i in {1..60}; do
    if curl -s http://localhost:9090/-/ready > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Prometheus is ready!"
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

# Step 9: Wait for DNS to refresh and targets to be discovered
echo ""
echo "Step 9: Waiting for DNS cache to refresh and targets to be discovered..."
echo "Waiting 30 seconds..."
sleep 30

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "                    FIX APPLIED!"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Step 10: Check target status
echo "Step 10: Verifying target status..."
echo ""

if command -v python3 &> /dev/null; then
    echo "Fetching target status from Prometheus API..."
    TARGETS_JSON=$(curl -s http://localhost:9090/api/v1/targets)

    echo "$TARGETS_JSON" | python3 <<'PY' || echo "Could not parse target status"
import sys
import json

try:
    data = json.load(sys.stdin)
except json.JSONDecodeError as exc:
    print(f'Error parsing response: {exc}')
    sys.exit(1)

if data.get('status') != 'success':
    print('Failed to fetch targets')
    sys.exit(0)

active_targets = data.get('data', {}).get('activeTargets', [])
jobs = {}
for target in active_targets:
    job = target.get('labels', {}).get('job', 'unknown')
    stats = jobs.setdefault(job, {'up': 0, 'down': 0})
    if target.get('health') == 'up':
        stats['up'] += 1
    else:
        stats['down'] += 1

print('Target Status Summary:')
print('-' * 50)

if not jobs:
    print('No targets reported yet. Give it a little more time.')
else:
    all_up = True
    for job in sorted(jobs):
        counts = jobs[job]
        total = counts['up'] + counts['down']
        status = '✓' if counts['down'] == 0 else '✗'
        print(f"{status} {job}: {counts['up']}/{total} UP")
        if counts['down']:
            all_up = False

    print('-' * 50)
    if all_up:
        print('✅ All targets are healthy!')
    else:
        print('⚠️  Some targets are still down. Wait 30-60 seconds and check again.')
PY
else
    echo "Python3 not available, checking manually..."
    curl -s http://localhost:9090/api/v1/targets | grep -E '"health"|"job"' | head -20
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "                   VERIFICATION"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "1. View Prometheus targets in web UI:"
echo -e "   ${YELLOW}http://localhost:9090/targets${NC}"
echo ""
echo "2. View Grafana dashboard:"
echo -e "   ${YELLOW}http://localhost:3000${NC}"
echo "   Username: admin"
echo "   Password: your_secure_password"
echo ""
echo "3. Check service logs if needed:"
echo "   docker service logs monitor_prometheus --tail 50"
echo "   docker service logs monitor_cadvisor --tail 50"
echo "   docker service logs monitor_fact_100k --tail 50"
echo ""
echo "4. Verify DNS resolution from Prometheus container:"
echo "   PROM=\$(docker ps --filter 'name=monitor_prometheus' --format '{{.ID}}' | head -1)"
echo "   docker exec \$PROM nslookup tasks.monitor_cadvisor"
echo ""
echo "5. Check all services are running:"
echo "   docker service ls | grep monitor_"
echo ""

echo "═══════════════════════════════════════════════════════════"
echo ""
echo -e "${GREEN}✅ Complete fix applied successfully!${NC}"
echo ""
echo "If some targets are still down:"
echo "  - Wait another 30-60 seconds for DNS to fully refresh"
echo "  - Run this script again to check status"
echo "  - Check service logs for specific errors"
echo ""
