#!/bin/bash

# Script to fix Prometheus target connectivity issues
# This script will help diagnose and resolve timeout errors

set -e

echo "🔍 Prometheus Target Connectivity Fix Script"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

STACK_NAME="monitor"

# Function to check if a service is running
check_service() {
    local service_name=$1
    echo -n "Checking $service_name... "
    
    replicas=$(docker service ls --filter name=${STACK_NAME}_${service_name} --format "{{.Replicas}}" 2>/dev/null || echo "0/0")
    
    if [[ "$replicas" == *"/"* ]]; then
        running=$(echo $replicas | cut -d'/' -f1)
        desired=$(echo $replicas | cut -d'/' -f2)
        
        if [[ "$running" == "$desired" ]] && [[ "$running" != "0" ]]; then
            echo -e "${GREEN}✓ Running ($replicas)${NC}"
            return 0
        else
            echo -e "${RED}✗ Not fully running ($replicas)${NC}"
            return 1
        fi
    else
        echo -e "${RED}✗ Service not found${NC}"
        return 1
    fi
}

# Function to test connectivity to a service
test_connectivity() {
    local service_name=$1
    local port=$2
    
    echo ""
    echo "Testing connectivity to ${service_name} on port ${port}..."
    
    # Get all task IPs for the service
    task_ips=$(docker service ps ${STACK_NAME}_${service_name} --filter "desired-state=running" --format "{{.Name}}" 2>/dev/null | while read task; do
        docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ${task}.$(docker service ps ${STACK_NAME}_${service_name} --filter "name=${task}" --format "{{.ID}}" --no-trunc | head -1) 2>/dev/null || echo ""
    done)
    
    if [ -z "$task_ips" ]; then
        echo -e "${YELLOW}⚠ Could not find running tasks for ${service_name}${NC}"
        return 1
    fi
    
    for ip in $task_ips; do
        if [ ! -z "$ip" ]; then
            echo -n "  Testing $ip:$port... "
            if timeout 5 bash -c "echo > /dev/tcp/$ip/$port" 2>/dev/null; then
                echo -e "${GREEN}✓ Reachable${NC}"
            else
                echo -e "${RED}✗ Unreachable${NC}"
            fi
        fi
    done
}

echo "Step 1: Checking service status"
echo "--------------------------------"
check_service "prometheus"
check_service "cadvisor"
check_service "node-exporter"
check_service "fact_100k"
check_service "fact_200k"
check_service "fact_300k"
check_service "fact_400k"
check_service "fact_500k"
check_service "matrix_4k"
check_service "matrix_5k"
check_service "matrix_6k"
check_service "matrix_7k"
check_service "matrix_8k"

echo ""
echo "Step 2: Testing network connectivity"
echo "-------------------------------------"
test_connectivity "cadvisor" "8080"
test_connectivity "node-exporter" "9100"
test_connectivity "fact_100k" "8000"
test_connectivity "fact_200k" "8000"
test_connectivity "fact_300k" "8000"
test_connectivity "fact_400k" "8000"
test_connectivity "fact_500k" "8000"
test_connectivity "matrix_4k" "8000"
test_connectivity "matrix_5k" "8000"
test_connectivity "matrix_6k" "8000"
test_connectivity "matrix_7k" "8000"
test_connectivity "matrix_8k" "8000"

echo ""
echo "Step 3: Checking DNS resolution"
echo "--------------------------------"
for service in cadvisor node-exporter fact_100k fact_200k fact_300k fact_400k fact_500k matrix_4k matrix_5k matrix_6k matrix_7k matrix_8k; do
    echo -n "Resolving tasks.${STACK_NAME}_${service}... "
    if docker run --rm --network ${STACK_NAME}-net alpine nslookup tasks.${STACK_NAME}_${service} >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Resolved${NC}"
    else
        echo -e "${RED}✗ Failed${NC}"
    fi
done

echo ""
echo "Step 4: Checking Prometheus configuration"
echo "------------------------------------------"
if docker config inspect ${STACK_NAME}_prometheus_config >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Prometheus config exists${NC}"
    
    # Check if scrape_timeout is properly configured
    echo "Checking scrape timeout configuration..."
    docker config inspect ${STACK_NAME}_prometheus_config --format '{{.Spec.Data}}' | base64 -d | grep -E "scrape_timeout|scrape_interval" || echo "Could not extract config"
else
    echo -e "${RED}✗ Prometheus config not found${NC}"
fi

echo ""
echo "Step 5: Recommendations"
echo "-----------------------"
echo "Based on the errors you're seeing, here are the fixes applied:"
echo ""
echo "1. ✓ Updated scrape_timeout to be less than scrape_interval"
echo "   - Global default: 25s (was 30s)"
echo "   - Prometheus: 10s"
echo "   - cAdvisor: 25s (can be slow due to container metrics)"
echo "   - Node Exporter: 20s"
echo "   - Custom Services: 15s"
echo ""
echo "2. ✓ Added DNS refresh intervals for better service discovery"
echo ""
echo "3. To apply these changes, run:"
echo "   ${YELLOW}./redeploy_monitor.sh${NC}"
echo ""
echo "4. If issues persist, check:"
echo "   - Network latency between nodes"
echo "   - CPU/Memory load on worker nodes"
echo "   - Docker daemon logs: journalctl -u docker -f"
echo ""
echo "5. Monitor the targets after redeployment:"
echo "   - Prometheus UI: http://<manager-ip>:9090/targets"
echo "   - Or run: python3 check_targets.py"
echo ""

echo "Would you like to redeploy Prometheus now with the fixed configuration? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo ""
    echo "🚀 Redeploying Prometheus with fixed configuration..."
    ./redeploy_monitor.sh
    echo ""
    echo "✅ Redeployment complete! Wait 30-60 seconds and check targets."
else
    echo ""
    echo "Skipping redeployment. Run './redeploy_monitor.sh' when ready."
fi
