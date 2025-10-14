# 🔧 Prometheus Timeout Errors - Complete Fix Guide

## 🚨 The Problem

Your Prometheus monitoring is showing timeout errors:

```
❌ cadvisor (1/3 up) - "context deadline exceeded"
❌ custom_services (0/5 up) - "context deadline exceeded"
❌ node-exporter (1/3 up) - "context deadline exceeded"
```

## ✅ The Solution (Already Implemented!)

The configuration files have been fixed. Now you just need to apply the changes.

---

## 🎯 Quick Fix (Recommended)

### One Command to Fix Everything:

```bash
./apply_fix.sh
```

This automated script will:
1. ✅ Check your Swarm status
2. ✅ Show current problems
3. ✅ Remove old configuration
4. ✅ Apply fixed configuration
5. ✅ Redeploy services
6. ✅ Verify everything works

**Time required**: ~3 minutes

---

## 📋 Alternative Methods

### Method 1: Interactive Diagnostics + Fix
```bash
./fix_prometheus_targets.sh
```
- Shows detailed diagnostics
- Tests connectivity
- Checks DNS resolution
- Offers to apply fix

### Method 2: Manual Redeployment
```bash
./redeploy_monitor.sh
```
- Quick redeploy with fixed config
- Use `--enhanced` flag for static IPs

### Method 3: Quick Status Check Only
```bash
./quick_status_check.sh
```
- Just checks current status
- No changes made
- Good for monitoring after fix

---

## 🔍 What Was Fixed?

### The Root Cause
```yaml
# ❌ BEFORE (Broken)
global:
  scrape_interval: 30s

scrape_configs:
  - job_name: 'cadvisor'
    scrape_timeout: 30s  # ❌ WRONG: timeout = interval
```

**Problem**: When `scrape_timeout` equals `scrape_interval`, Prometheus can't complete scrapes in time.

### The Fix
```yaml
# ✅ AFTER (Fixed)
global:
  scrape_interval: 30s
  scrape_timeout: 25s  # ✅ CORRECT: timeout < interval

scrape_configs:
  - job_name: 'cadvisor'
    scrape_timeout: 25s  # ✅ Optimized per service
    scrape_interval: 30s
    dns_sd_configs:
      - refresh_interval: 30s  # ✅ Better DNS resolution
```

### Timeout Values Applied

| Service | Timeout | Reason |
|---------|---------|--------|
| **Global Default** | 25s | Safe default for all services |
| **Prometheus** | 10s | Fast, local metrics |
| **cAdvisor** | 25s | Can be slow, needs more time |
| **Node Exporter** | 20s | Usually fast |
| **Custom Services** | 15s | Should respond quickly |

---

## 📊 Verification

After applying the fix, verify with any of these methods:

### 1. Quick Status Script
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

### 2. Prometheus Web UI
```
http://<manager-ip>:9090/targets
```

All targets should show:
- **State**: UP (green)
- **Scrape Duration**: < timeout value
- **Error**: (empty)

### 3. Python Check Script
```bash
python3 check_targets.py
```

### 4. Docker Commands
```bash
# Check services
docker service ls

# Check Prometheus logs
docker service logs monitor_prometheus --tail 50

# Check specific service
docker service logs monitor_cadvisor --tail 20
```

---

## 🛠️ Troubleshooting

### Issue: Some targets still DOWN after fix

**Wait longer**: Services need 1-2 minutes to stabilize
```bash
sleep 60
./quick_status_check.sh
```

**Check service status**:
```bash
docker service ls | grep monitor
docker service ps monitor_cadvisor
```

**Check logs**:
```bash
docker service logs monitor_cadvisor --tail 50
docker service logs monitor_fact_100k --tail 50
```

### Issue: DNS resolution failing

**Solution 1**: Increase DNS refresh interval
```yaml
# In prometheus.yml
dns_sd_configs:
  - refresh_interval: 60s  # Increase from 30s
```

**Solution 2**: Use static IPs instead
```bash
./redeploy_monitor.sh --enhanced
```

### Issue: High CPU load causing timeouts

**Check node resources**:
```bash
docker stats
docker node ls
```

**Solution**: Reduce scrape frequency
```yaml
# In prometheus.yml
global:
  scrape_interval: 60s  # Increase from 30s
  scrape_timeout: 50s
```

### Issue: Network latency between nodes

**Test connectivity**:
```bash
# From Prometheus container
docker exec -it $(docker ps -q -f name=monitor_prometheus) sh
wget -O- http://tasks.monitor_cadvisor:8080/metrics
```

**Solution**: Increase timeouts
```yaml
scrape_configs:
  - job_name: 'cadvisor'
    scrape_timeout: 40s  # Increase for slow networks
```

---

## 📁 Files Reference

### Configuration Files (Modified)
- ✅ `prometheus.yml` - Main config with fixed timeouts
- ✅ `prometheus.enhanced.yml` - Enhanced config with static IPs

### Scripts (New)
- 🆕 `apply_fix.sh` - **One-command automated fix** ⭐
- 🆕 `fix_prometheus_targets.sh` - Diagnostics + interactive fix
- 🆕 `quick_status_check.sh` - Quick status verification
- ✅ `redeploy_monitor.sh` - Manual redeployment (existing)
- ✅ `check_targets.py` - Python status checker (existing)

### Documentation (New)
- 📝 `FIX_README.md` - This file (quick reference)
- 📝 `QUICK_START_FIX.md` - Quick start guide
- 📝 `PROMETHEUS_FIX_SUMMARY.md` - Detailed technical docs

---

## 🎓 Understanding the Fix

### Why This Happens

1. **Timeout Configuration Error**: Most common cause
   - `scrape_timeout` must be less than `scrape_interval`
   - Prometheus needs time between scrapes to process data

2. **Service Performance**: Secondary cause
   - cAdvisor collects many container metrics (slow)
   - Custom services under heavy CPU load (factorial/matrix)
   - Network latency between Docker Swarm nodes

3. **DNS Resolution**: Contributing factor
   - DNS service discovery can be slow
   - Without refresh intervals, stale DNS entries

### How the Fix Works

1. **Proper Timeout Hierarchy**:
   ```
   scrape_interval (30s)
   └─> scrape_timeout (25s) ✅ 5s buffer
       └─> actual scrape (varies)
   ```

2. **Service-Specific Optimization**:
   - Fast services (Prometheus): 10s timeout
   - Slow services (cAdvisor): 25s timeout
   - Medium services (Node Exporter): 20s timeout

3. **Better DNS Resolution**:
   - Added `refresh_interval: 30s`
   - Prevents stale DNS entries
   - Faster target discovery

---

## 🚀 Quick Command Reference

```bash
# Apply the complete fix (recommended)
./apply_fix.sh

# Run diagnostics and fix interactively
./fix_prometheus_targets.sh

# Check status after fix
./quick_status_check.sh

# Manual redeploy
./redeploy_monitor.sh

# Check with Python script
python3 check_targets.py

# View Prometheus UI
# http://<manager-ip>:9090/targets

# Check Docker services
docker service ls
docker service logs monitor_prometheus
docker service ps monitor_cadvisor

# Check node health
docker node ls
docker stats
```

---

## 📞 Support

If you continue to experience issues:

1. **Run full diagnostics**:
   ```bash
   ./fix_prometheus_targets.sh
   ```

2. **Check detailed logs**:
   ```bash
   docker service logs monitor_prometheus --tail 100
   docker service logs monitor_cadvisor --tail 100
   ```

3. **Review detailed documentation**:
   ```bash
   cat PROMETHEUS_FIX_SUMMARY.md
   ```

4. **Check network and resources**:
   ```bash
   docker node ls
   docker stats
   docker network inspect monitor-net
   ```

---

## ✨ Summary

| Step | Command | Time |
|------|---------|------|
| 1. Apply fix | `./apply_fix.sh` | 3 min |
| 2. Verify | `./quick_status_check.sh` | 10 sec |
| 3. Monitor | Open Prometheus UI | - |

**Expected Result**: All targets UP, no timeout errors! 🎉

---

**Last Updated**: $(date)
**Status**: ✅ Ready to apply
**Difficulty**: 🟢 Easy (automated)