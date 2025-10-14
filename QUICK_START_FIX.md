# 🚀 Quick Start: Fix Prometheus Timeout Errors

## The Problem
```
❌ cadvisor (1/3 up) - "context deadline exceeded"
❌ custom_services (0/5 up) - "context deadline exceeded"  
❌ node-exporter (1/3 up) - "context deadline exceeded"
```

## The Solution (Already Applied! ✅)

### What Was Wrong?
- `scrape_timeout` was 30s (same as `scrape_interval`)
- Prometheus requires: **scrape_timeout < scrape_interval**
- This caused immediate timeouts

### What Was Fixed?

| Job | Old Timeout | New Timeout | Reason |
|-----|-------------|-------------|--------|
| **Global Default** | 30s | 25s | Must be < scrape_interval |
| **prometheus** | 30s | 10s | Fast local metrics |
| **cadvisor** | 30s | 25s | Slow, needs more time |
| **node-exporter** | 30s | 20s | Usually fast |
| **custom_services** | 30s | 15s | Should respond quickly |

## 🎯 Apply the Fix (3 Simple Steps)

### Step 1: Run the Fix Script
```bash
./fix_prometheus_targets.sh
```
This will:
- ✅ Diagnose all issues
- ✅ Show connectivity status
- ✅ Offer to redeploy automatically

### Step 2: Wait for Services to Start
```bash
# Wait 30-60 seconds for services to stabilize
sleep 60
```

### Step 3: Verify the Fix
```bash
./quick_status_check.sh
```

Expected output:
```
✓ prometheus: 1/1 UP
✓ cadvisor: 3/3 UP
✓ node-exporter: 3/3 UP
✓ custom_services: 5/5 UP

✅ All targets are healthy!
```

## 📊 Alternative: Manual Verification

### Via Prometheus UI
```
http://<manager-ip>:9090/targets
```

### Via Python Script
```bash
python3 check_targets.py
```

### Via Docker Commands
```bash
# Check services
docker service ls

# Check Prometheus logs
docker service logs monitor_prometheus --tail 50
```

## 🔧 If Issues Persist

### Quick Checks
```bash
# 1. Check all services are running
docker service ls | grep monitor

# 2. Check network
docker network ls | grep monitor-net

# 3. Check specific service
docker service ps monitor_cadvisor
docker service logs monitor_cadvisor --tail 20
```

### Common Issues & Solutions

#### Issue: Services still timing out
**Solution**: Increase timeouts further
```yaml
# Edit prometheus.yml
global:
  scrape_interval: 60s
  scrape_timeout: 50s
```

#### Issue: DNS resolution failing
**Solution**: Use static IPs instead
```bash
./redeploy_monitor.sh --enhanced
```

#### Issue: High CPU load on nodes
**Solution**: Check node resources
```bash
docker stats
# Consider reducing service load or adding nodes
```

## 📁 Files Modified

- ✅ `prometheus.yml` - Fixed timeout configuration
- ✅ `prometheus.enhanced.yml` - Fixed enhanced config
- 🆕 `fix_prometheus_targets.sh` - Diagnostic & fix script
- 🆕 `quick_status_check.sh` - Quick status checker
- 📝 `PROMETHEUS_FIX_SUMMARY.md` - Detailed documentation

## 🎓 Understanding the Fix

### Before (❌ Broken)
```yaml
global:
  scrape_interval: 30s
  
scrape_configs:
  - job_name: 'cadvisor'
    scrape_timeout: 30s  # ❌ Same as interval!
```

### After (✅ Fixed)
```yaml
global:
  scrape_interval: 30s
  scrape_timeout: 25s  # ✅ Less than interval
  
scrape_configs:
  - job_name: 'cadvisor'
    scrape_timeout: 25s  # ✅ Optimized per service
    scrape_interval: 30s
    dns_sd_configs:
      - refresh_interval: 30s  # ✅ Better DNS resolution
```

## 🚦 Status Indicators

After running `quick_status_check.sh`:

- 🟢 **Green ✓** = Target is UP and healthy
- 🔴 **Red ✗** = Target is DOWN (needs attention)
- 🟡 **Yellow ⚠** = Partial (some targets up, some down)

## 📞 Need Help?

1. **Run diagnostics**: `./fix_prometheus_targets.sh`
2. **Check logs**: `docker service logs monitor_<service>`
3. **View detailed docs**: `cat PROMETHEUS_FIX_SUMMARY.md`

---

**TL;DR**: Run `./fix_prometheus_targets.sh` and follow the prompts! 🎉