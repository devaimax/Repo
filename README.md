# Docker Swarm Scheduling Experiments

This repository hosts a reproducible environment for evaluating three Docker Swarm
placement strategies:

1. **Spread (baseline)** – the default Swarm policy with no resource awareness.
2. **Manual weighting** – the Ramavat & Patel (2024) algorithm using user-supplied
   CPU/Memory weights.
3. **Automatic weighting** – our telemetry-driven implementation that derives
   weights from live Prometheus metrics.

The monitoring stack (Prometheus, Grafana, Elasticsearch, cAdvisor, Node
Exporter) is deployed via `docker-compose.yml` as Swarm stack `monitor`. The
factorial and matrix services expose execution time metrics that are captured in
CSV/Prometheus for analysis, while Elasticsearch offers an optional search store
for enhanced scenarios.

## Deploy or refresh the monitoring stack

### Baseline (matches the paper)

This uses pure overlay networking and Prometheus DNS discovery, exactly like
the weighted-placement paper describes:

```bash
./deploy_monitoring.sh
# …or, if you only need to refresh configs…
./redeploy_monitor.sh
```

### Enhanced host-aware mode

If you prefer the tuned variant with host networking, fixed ports
(`18000+`), and static Prometheus targets, add `--enhanced`:

```bash
./deploy_monitoring.sh --enhanced
# …or…
./redeploy_monitor.sh --enhanced
```

The enhanced mode stacks `docker-compose.enhanced.yml` on top of the baseline
compose file and swaps in `prometheus.enhanced.yml` for the config. In this mode
Elasticsearch is reachable on the manager via `http://<manager-ip>:9200/`.

Ensure all targets are healthy before running experiments (`check_services.sh`
and `check_targets.py` are available for quick verification).

## 1. Spread baseline

Clear any host constraints so Swarm falls back to Spread, then inspect task
placement:

```bash
python3 collector/spread_reset.py --force
```

The script removes `node.hostname==…` constraints for the factorial/matrix
services, triggers a rolling update, and prints `docker service ps` summaries so
node distribution is explicit.

## 2. Manual weighting (paper replication)

Apply the paper’s manual weights directly from live Prometheus metrics:

```bash
python3 collector/manual_weight_scheduler.py \
  --prom-url http://localhost:9090 \
  --apply --force-update
```

The script fetches node utilisation, prints a ranking table, and pins each
service to the node with the highest weighted score (CPU-heavy factorial vs
memory-heavy matrix). Use `--services` to target specific services or
`--cpu-weight/--mem-weight` to override the defaults. Adding `--force-update`
forces Swarm to restart tasks immediately so the new placement takes effect.

## 3. Automatic weighting (telemetry-driven)

Run the automatic scheduler once to derive weights from Prometheus and redeploy
services accordingly:

```bash
PROM_URL=http://localhost:9090 \
SCHEDULER_STRATEGY=weighted \
python3 collector/auto_weight_scheduler.py
```

Set `SIMULATION_MODE=1` to dry-run without touching services. The scheduler logs
assignments to `logs/auto_scheduler_log.csv` and updates plots under
`reports/plots/`.

## Tips for consistent measurements

- After switching strategies, give Prometheus a short window (≈2 scrape
  intervals) before exporting metrics to capture the new steady state.
- Use `collector/manual_weight_scheduler.py --apply --services monitor_fact_500k`
  to pin a single service when testing individual scenarios.

- All strategy helpers accept an `--export-excel` flag (or `EXPORT_EXCEL=1` for
  the automatic scheduler) to capture the latest Prometheus samples into
  `reports/<strategy>_results.xlsx` with raw and summary sheets.

All scripts emit the current task-to-node mapping so comparisons between
strategies stay traceable.

## Batch replay across strategies

When you need fresh CSVs after changing node resources, run the automation
helper to reset Spread, apply manual weighting, and execute the auto scheduler:

```bash
python3 collector/replay_strategies.py \
  --prom-url http://localhost:9090 \
  --settle-seconds 180 \
  --window-minutes 10
```

The script waits between runs so Prometheus captures new samples, then writes
per-strategy outputs under `reports/replay/` (e.g. `spread_results_metrics.csv`,
`manual_results_metrics.csv`, `auto_weighted_results_metrics.csv`, مع ملفات
الوزن المرافقة). استخدم `--services` لتقييد التشغيل على خدمات محددة، و
`--skip-*` لتجاوز مراحل، و`--auto-strategy` لتجربة البدائل الأخرى.

When running helper scripts from machines that cannot query the Swarm manager
directly, provide hostname aliases so scheduling decisions map overlay IPs back
to Docker node names:

```bash
export NODE_ALIAS_MAP=10.0.2.16=node-01,10.0.2.17=node-02
python3 collector/replay_strategies.py --prom-url http://localhost:9090 --skip-spread
```

`NODE_ALIAS_MAP` is honoured by both the manual and automatic schedulers.

Both schedulers and the CSV exporter also cache the last successful Prometheus
snapshot under `logs/cache/`. If Prometheus is temporarily unreachable, the
helper reuses that cached data instead of aborting, so automation can continue
until connectivity is restored.
