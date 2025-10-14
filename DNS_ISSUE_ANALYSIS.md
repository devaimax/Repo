# Prometheus DNS Issue - Root Cause Analysis

## Executive Summary

The Prometheus monitoring targets were failing due to **Docker Swarm DNS caching stale IP addresses** from previous deployments, combined with an initial misconfiguration where DNS names were missing the stack prefix.

## Timeline of Issues

### Issue #1: Invalid Timeout Configuration (RESOLVED)
- **Problem**: `scrape_timeout` was set to 30s, equal to `scrape_interval` (30s)
- **Impact**: Prometheus requires `scrape_timeout < scrape_interval`
- **Solution**: Reduced timeouts appropriately (25s default, with service-specific tuning)
- **Status**: ✅ FIXED

### Issue #2: DNS Name Misconfiguration (IDENTIFIED & FIXED)
- **Problem**: Prometheus config was using incorrect DNS names
  - Used: `tasks.cadvisor`, `tasks.node-exporter`, `tasks.fact_100k`
  - Should be: `tasks.monitor_cadvisor`, `tasks.monitor_node-exporter`, `tasks.monitor_fact_100k`
- **Root Cause**: When deploying with `docker stack deploy -c docker-compose.yml monitor`, Docker adds the stack name (`monitor`) as a prefix to all service names
- **Impact**: DNS queries were failing or returning stale IPs
- **Solution**: Updated all DNS names to include `monitor_` prefix
- **Status**: ✅ FIXED

### Issue #3: Docker Swarm DNS Caching (IDENTIFIED & SOLUTION PROVIDED)
- **Problem**: Docker Swarm's internal DNS (127.0.0.11) was caching old IP addresses from previous deployments
- **Evidence**:
  ```
  Current IPs (from docker inspect):
  - fact_100k: 10.0.1.46
  - cadvisor: 10.0.1.60, 10.0.1.61, 10.0.1.62
  - node-exporter: 10.0.1.66, 10.0.1.67, 10.0.1.68
  
  DNS was returning:
  - fact_100k: 10.0.1.5 (STALE!)
  - Other services: No answer or stale IPs
  ```
- **Impact**: Prometheus was trying to scrape metrics from non-existent or old container IPs, causing timeouts
- **Solution**: Force DNS cache refresh by restarting Prometheus service
- **Status**: ⚠️ SOLUTION READY (needs to be applied)

## Technical Deep Dive

### How Docker Swarm DNS Works

1. **Service Names**: When you deploy a stack named `monitor` with a service `cadvisor`, the full service name becomes `monitor_cadvisor`

2. **DNS Resolution**:
   - `monitor_cadvisor` → VIP (Virtual IP) for load balancing
   - `tasks.monitor_cadvisor` → All task IPs (for service discovery)

3. **DNS Caching**: Docker's embedded DNS server (127.0.0.11) caches DNS responses, which can become stale after:
   - Service updates
   - Container restarts
   - Network reconfigurations

### Why Targets Were Failing

```
Prometheus Config (WRONG):
  dns_sd_configs:
    - names: ['tasks.cadvisor']  # Missing 'monitor_' prefix!

Docker Service Name: monitor_cadvisor
DNS Name: tasks.monitor_cadvisor

Result: DNS query fails or returns stale IPs
```

### The Fix

```yaml
# CORRECT Configuration
dns_sd_configs:
  - names: ['tasks.monitor_cadvisor']  # Includes stack prefix
    type: 'A'
    port: 8080
    refresh_interval: 30s

relabel_configs:
  - source_labels: [__meta_dns_name]
    regex: 'tasks\\.monitor_(.+)'  # Strip 'monitor_' for display
    replacement: '$1'
    target_label: instance
```

## Verification Steps

### 1. Check Service Names
```bash
docker service ls | grep monitor
```
Output should show: `monitor_cadvisor`, `monitor_node-exporter`, etc.

### 2. Check DNS Resolution from Prometheus Container
```bash
PROM=$(docker ps --filter 'name=monitor_prometheus' --format '{{.ID}}' | head -1)
docker exec $PROM nslookup tasks.monitor_cadvisor
```
Should return current task IPs (10.0.1.60, 10.0.1.61, 10.0.1.62)

### 3. Check Actual Task IPs
```bash
docker service ps monitor_cadvisor -q | xargs -I {} docker inspect {} \
  --format '{{range .NetworksAttachments}}{{.Addresses}}{{end}}'
```

### 4. Test Connectivity
```bash
PROM=$(docker ps --filter 'name=monitor_prometheus' --format '{{.ID}}' | head -1)
docker exec $PROM wget -qO- --timeout=2 http://10.0.1.62:8080/metrics | head -5
```

## Solution Implementation

### Option 1: Apply DNS Fix (Recommended)
```bash
./apply_final_fix.sh
```

This script will:
1. ✅ Verify prometheus.yml has correct DNS names
2. ✅ Remove old config from Prometheus service
3. ✅ Delete old Docker config object
4. ✅ Create new config with corrected DNS names
5. ✅ Attach new config to Prometheus service
6. ✅ Force service restart to clear DNS cache
7. ✅ Wait for DNS refresh and verify targets

### Option 2: Use Static IPs (Alternative)
If DNS issues persist, use `prometheus.enhanced.yml` which uses static IPs:

```bash
# Update docker-compose.yml to use enhanced config
sed -i 's/prometheus_config/prometheus_enhanced_config/g' docker-compose.yml
sed -i 's/prometheus.yml/prometheus.enhanced.yml/g' docker-compose.yml

# Redeploy
docker stack deploy -c docker-compose.yml monitor
```

## Lessons Learned

1. **Stack Prefix Matters**: Always include the stack name in DNS queries for Docker Swarm services
2. **DNS Caching**: Docker Swarm DNS can cache stale IPs; service restarts force refresh
3. **Timeout Configuration**: `scrape_timeout` must be less than `scrape_interval` with adequate buffer
4. **Service Discovery**: Use `tasks.<stack>_<service>` for DNS-based service discovery in Swarm
5. **Verification**: Always verify DNS resolution from within the container that needs to connect

## Files Modified

- ✅ `prometheus.yml` - Fixed DNS names and timeouts
- ✅ `prometheus.enhanced.yml` - Fixed timeouts (uses static IPs)
- ✅ `apply_final_fix.sh` - Automated fix script
- ✅ `quick_status_check.sh` - Status verification tool
- ✅ `fix_prometheus_targets.sh` - Diagnostic tool

## Current Status

- ✅ Configuration files corrected
- ✅ Fix script created and ready
- ⏳ Waiting for user to apply fix with `./apply_final_fix.sh`

## Expected Outcome

After applying the fix:
- All cadvisor targets (3/3) should be UP
- All node-exporter targets (3/3) should be UP
- All custom_services targets (5/5) should be UP
- Scrape durations should be well below timeout values
- No more "context deadline exceeded" errors

## Troubleshooting

If targets are still down after applying the fix:

1. **Wait longer**: DNS cache can take 60-90 seconds to fully refresh
2. **Check service health**: `docker service ps monitor_<service-name>`
3. **Check logs**: `docker service logs monitor_<service-name>`
4. **Verify network**: Ensure all services are on `monitor-net` network
5. **Test connectivity**: Use wget/curl from Prometheus container to test direct IP access
6. **Consider static IPs**: Switch to `prometheus.enhanced.yml` if DNS continues to be problematic

## References

- Docker Swarm DNS: https://docs.docker.com/engine/swarm/networking/#use-swarm-mode-service-discovery
- Prometheus DNS SD: https://prometheus.io/docs/prometheus/latest/configuration/configuration/#dns_sd_config
- Docker Config Management: https://docs.docker.com/engine/swarm/configs/