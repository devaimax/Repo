# Prometheus Target Timeout Fix Summary

## Problem Analysis

You were experiencing "context deadline exceeded" errors on multiple Prometheus targets:
- **cadvisor**: 2 out of 3 targets DOWN
- **custom_services**: All 5 targets DOWN  
- **node-exporter**: 2 out of 3 targets DOWN

### Root Causes

1. **Invalid Timeout Configuration**: `scrape_timeout` was set to 30s, which equals `scrape_interval` (30s)
   - Prometheus requires: `scrape_timeout < scrape_interval`
   - This causes immediate timeouts and conflicts

2. **Network/Performance Issues**: Some services couldn't respond within the timeout period
   - cAdvisor can be slow when collecting container metrics
   - Custom services might be under heavy CPU load (factorial/matrix calculations)
   - Network latency between Docker Swarm nodes

3. **DNS Resolution Delays**: DNS service discovery might be slow without proper refresh intervals

## Changes Made

### 1. Updated `prometheus.yml`

**Global Configuration:**
```yaml
global:
  scrape_interval: 30s
  evaluation_interval: 30s
  scrape_timeout: 25s  # NEW: Default timeout, must be less than scrape_interval
```

**Per-Job Timeouts (optimized for each service type):**
- **prometheus**: 10s (fast, local metrics)
- **cadvisor**: 25s (can be slow, needs more time)
- **node-exporter**: 20s (usually fast)
- **custom_services**: 15s (should respond quickly)

**Added DNS Refresh Intervals:**
```yaml
dns_sd_configs:
  - names: ['tasks.monitor_cadvisor']
    type: 'A'
    port: 8080
    refresh_interval: 30s  # NEW: Improves DNS resolution
```

### 2. Updated `prometheus.enhanced.yml`

Applied the same timeout fixes to the enhanced configuration file for consistency.

### 3. Created Diagnostic Script

Created `fix_prometheus_targets.sh` to help diagnose and fix issues:
- Checks service status
- Tests network connectivity
- Validates DNS resolution
- Verifies Prometheus configuration
- Provides actionable recommendations

## How to Apply the Fix

### Option 1: Automated Fix (Recommended)

Run the diagnostic and fix script:
```bash
./fix_prometheus_targets.sh
```

This will:
1. Check all services and connectivity
2. Show detailed diagnostics
3. Offer to redeploy Prometheus automatically

### Option 2: Manual Redeployment

```bash
# For standard configuration
./redeploy_monitor.sh

# For enhanced configuration (if using static IPs)
./redeploy_monitor.sh --enhanced
```

### Option 3: Manual Steps

```bash
# 1. Remove the old stack
docker stack rm monitor

# 2. Wait for services to stop
sleep 10

# 3. Remove old config
docker config rm monitor_prometheus_config

# 4. Create new config with fixed prometheus.yml
docker config create monitor_prometheus_config ./prometheus.yml

# 5. Redeploy the stack
docker stack deploy -c docker-compose.yml monitor
```

## Verification

After redeployment, wait 30-60 seconds, then check:

### 1. Via Prometheus UI
```
http://<manager-ip>:9090/targets
```

### 2. Via Python Script
```bash
python3 check_targets.py
```

### 3. Via Docker Commands
```bash
# Check service status
docker service ls

# Check Prometheus logs
docker service logs monitor_prometheus

# Check specific service logs
docker service logs monitor_cadvisor
docker service logs monitor_fact_100k
```

## Expected Results

After applying the fix:
- ✅ All targets should show "UP" status
- ✅ Scrape duration should be well under the timeout
- ✅ No more "context deadline exceeded" errors
- ✅ Metrics collection should be consistent

## If Issues Persist

If some targets still show DOWN after the fix:

### 1. Check Node Health
```bash
# Check node status
docker node ls

# Check node resources
docker node inspect <node-name>
```

### 2. Check Service Placement
```bash
# See where services are running
docker service ps monitor_cadvisor
docker service ps monitor_fact_100k
```

### 3. Check Network Connectivity
```bash
# Test connectivity from Prometheus container
docker exec -it $(docker ps -q -f name=monitor_prometheus) sh
wget -O- http://tasks.monitor_cadvisor:8080/metrics
```

### 4. Check Service Logs
```bash
# Check for errors in service logs
docker service logs monitor_cadvisor --tail 50
docker service logs monitor_fact_100k --tail 50
```

### 5. Increase Timeouts Further (if needed)

If your network is slow or nodes are under heavy load, you may need to increase timeouts:

```yaml
# In prometheus.yml
global:
  scrape_interval: 60s  # Increase interval
  scrape_timeout: 50s   # Increase timeout

scrape_configs:
  - job_name: 'cadvisor'
    scrape_timeout: 50s
    scrape_interval: 60s
```

### 6. Check for Resource Constraints

Heavy CPU load from factorial/matrix calculations might slow down metrics endpoints:

```bash
# Check CPU usage on nodes
docker stats

# Consider reducing service load or adding more nodes
```

## Additional Optimizations

### 1. Reduce Scrape Frequency for Heavy Services
```yaml
- job_name: 'cadvisor'
  scrape_interval: 60s  # Less frequent scraping
  scrape_timeout: 50s
```

### 2. Use Static Targets Instead of DNS SD

If DNS resolution is problematic, switch to static IPs (see `prometheus.enhanced.yml`):
```yaml
- job_name: 'cadvisor'
  static_configs:
    - targets: ['10.0.1.40:8080', '10.0.1.38:8080', '10.0.1.9:8080']
```

### 3. Add Retry Logic

Consider adding Prometheus relabeling to mark slow targets:
```yaml
relabel_configs:
  - source_labels: [__address__]
    target_label: __param_timeout
    replacement: 30s
```

## Monitoring Best Practices

1. **Regular Health Checks**: Run `check_targets.py` periodically
2. **Alert on Target Down**: Configure Prometheus alerts for down targets
3. **Monitor Scrape Duration**: Watch for increasing scrape times
4. **Load Balancing**: Distribute services across nodes evenly
5. **Resource Monitoring**: Keep an eye on node CPU/memory usage

## Files Modified

- ✅ `prometheus.yml` - Main Prometheus configuration
- ✅ `prometheus.enhanced.yml` - Enhanced configuration with static targets
- ✅ `fix_prometheus_targets.sh` - New diagnostic and fix script (created)
- ✅ `PROMETHEUS_FIX_SUMMARY.md` - This documentation (created)

## Support

If you continue to experience issues:
1. Run the diagnostic script: `./fix_prometheus_targets.sh`
2. Check the output for specific errors
3. Review service logs for detailed error messages
4. Consider network latency and node performance issues

---

**Last Updated**: $(date)
**Status**: Ready to deploy