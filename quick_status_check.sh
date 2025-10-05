#!/bin/bash

# Quick status check for Prometheus targets
# Run this after redeploying to verify the fix

echo "🔍 Quick Prometheus Targets Status Check"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROMETHEUS_URL="http://localhost:9090"

# Check if Prometheus is accessible
echo -n "Checking Prometheus accessibility... "
if curl -s "${PROMETHEUS_URL}/-/healthy" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Prometheus is running${NC}"
else
    echo -e "${RED}✗ Prometheus is not accessible${NC}"
    echo "Make sure Prometheus is running and accessible at ${PROMETHEUS_URL}"
    exit 1
fi

echo ""
echo "Fetching target status from Prometheus API..."
echo ""

# Fetch targets and parse
targets_json=$(curl -s "${PROMETHEUS_URL}/api/v1/targets")

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to fetch targets from Prometheus${NC}"
    exit 1
fi

# Parse and display results
echo "$targets_json" | python3 -c "
import sys
import json
from datetime import datetime

try:
    data = json.load(sys.stdin)
    targets = data.get('data', {}).get('activeTargets', [])
    
    if not targets:
        print('⚠️  No active targets found')
        sys.exit(0)
    
    # Group by job
    jobs = {}
    for target in targets:
        job = target.get('labels', {}).get('job', 'unknown')
        if job not in jobs:
            jobs[job] = {'up': 0, 'down': 0, 'targets': []}
        
        health = target.get('health', 'unknown')
        instance = target.get('labels', {}).get('instance', 'unknown')
        last_error = target.get('lastError', '')
        scrape_duration = target.get('lastScrapeDuration', 0)
        
        if health == 'up':
            jobs[job]['up'] += 1
            status = '✓'
            color = '\033[0;32m'  # Green
        else:
            jobs[job]['down'] += 1
            status = '✗'
            color = '\033[0;31m'  # Red
        
        jobs[job]['targets'].append({
            'instance': instance,
            'health': health,
            'status': status,
            'color': color,
            'error': last_error,
            'duration': scrape_duration
        })
    
    # Display results
    total_up = 0
    total_down = 0
    
    for job_name, job_data in sorted(jobs.items()):
        up = job_data['up']
        down = job_data['down']
        total = up + down
        total_up += up
        total_down += down
        
        if down == 0:
            job_color = '\033[0;32m'  # Green
            job_status = '✓'
        elif up == 0:
            job_color = '\033[0;31m'  # Red
            job_status = '✗'
        else:
            job_color = '\033[1;33m'  # Yellow
            job_status = '⚠'
        
        print(f'{job_color}{job_status} {job_name}: {up}/{total} UP\033[0m')
        
        for target in job_data['targets']:
            duration_ms = target['duration'] * 1000
            print(f\"  {target['color']}{target['status']}\033[0m {target['instance']} - {duration_ms:.1f}ms\", end='')
            
            if target['error']:
                # Truncate long errors
                error = target['error']
                if len(error) > 60:
                    error = error[:60] + '...'
                print(f\" - \033[0;31m{error}\033[0m\")
            else:
                print()
    
    print()
    print('=' * 50)
    
    if total_down == 0:
        print(f'\033[0;32m✓ All targets are UP ({total_up}/{total_up + total_down})\033[0m')
        sys.exit(0)
    else:
        print(f'\033[1;33m⚠ Summary: {total_up} UP, {total_down} DOWN (Total: {total_up + total_down})\033[0m')
        sys.exit(1)

except Exception as e:
    print(f'Error parsing targets: {e}')
    sys.exit(1)
"

exit_code=$?

echo ""

if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}✅ All targets are healthy!${NC}"
    echo ""
    echo "Next steps:"
    echo "  - View metrics in Grafana: http://<manager-ip>:3000"
    echo "  - View Prometheus UI: http://<manager-ip>:9090"
else
    echo -e "${YELLOW}⚠️  Some targets are still down${NC}"
    echo ""
    echo "Troubleshooting steps:"
    echo "  1. Wait 30-60 seconds and run this script again"
    echo "  2. Check service logs: docker service logs monitor_<service-name>"
    echo "  3. Run full diagnostics: ./fix_prometheus_targets.sh"
    echo "  4. Check network connectivity between nodes"
    echo "  5. Verify services are running: docker service ls"
fi

echo ""
echo "For detailed diagnostics, run: ./fix_prometheus_targets.sh"