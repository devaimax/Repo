# Docker Swarm Scheduling Experiments

This repository now contains two fully isolated scenarios built on the same
collector and service code:

* **paper_3node** – an exact reproduction of the Ramavat & Patel (2024) baseline
  using only the manager + node‑01 + node‑02. Outputs live under
  `scenarios/paper_3node/reports` and the tailored compose/Prometheus files live
  in `scenarios/paper_3node/compose`.
* **realistic_5node** – the heterogeneous five-node lab with extra factorial and
  matrix workloads. All configuration sits under
  `scenarios/realistic_5node/compose`, and metrics are written to
  `scenarios/realistic_5node/reports`.

Shared Python tooling (manual/auto schedulers, exporters, cache helpers) remains
in `collector/`, while Docker images stay under `services/`. Use the scenario
scripts to avoid mixing configurations.

```
scenarios/
  paper_3node/
    compose/        # minimal compose + Prometheus files
    scripts/        # deploy + replay helpers
    reports/        # generated Word/Excel outputs per run
  realistic_5node/
    compose/
    scripts/
    reports/
```

Top-level helpers:

* `run_three_node_strategy.sh` – drains node‑03/node‑04, redeploys the paper
  stack, and replays Spread → Manual → Auto.
* `run_five_node_strategy.sh` – reactivates node‑03/node‑04, redeploys the
  realistic stack, and replays the same strategies.
* `run_complete_workflow.sh` – sequentially runs both scenarios (deploy + replay).

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
and `check_targets.py` are available for quick verification). Scenario deploy
scripts call `deploy_monitoring.sh`/`redeploy_monitor.sh` with the appropriate
`CONFIG_ROOT`, so you rarely need to invoke those scripts directly.

## Node & service layout (current scenario)

The stack now targets a manager plus four heterogeneous workers:

- `Master` (`192.168.20.35`): Swarm manager + monitoring stack only.
- `node-01` (`192.168.20.5`): `fact_100k` → `18000`, `matrix_4k` → `18030`.
- `node-02` (`192.168.20.6`): `fact_300k` → `18010`, `matrix_5k` → `18040`.
- `node-03` (`192.168.20.7`): `fact_200k` → `18060`, `matrix_6k` → `18080`, `matrix_8k` → `18100`.
- `node-04` (`192.168.20.8`): `fact_400k` → `18070`, `fact_500k` → `18020`, `matrix_7k` → `18090`.

Prometheus configs (baseline and enhanced) scrape these static endpoints, so
update IPs/hostnames here if nodes change.

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
export NODE_ALIAS_MAP=192.168.20.5=node-01,192.168.20.6=node-02,192.168.20.7=node-03,192.168.20.8=node-04
python3 collector/replay_strategies.py --prom-url http://localhost:9090 --skip-spread
```

`NODE_ALIAS_MAP` is honoured by both the manual and automatic schedulers.

Both schedulers and the CSV exporter also cache the last successful Prometheus
snapshot under `logs/cache/`. If Prometheus is temporarily unreachable, the
helper reuses that cached data instead of aborting, so automation can continue
until connectivity is restored.
