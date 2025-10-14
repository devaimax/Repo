"""Replay each scheduling strategy and export fresh CSV measurements.

This helper resets the cluster to Spread, applies the manual weighting policy,
then runs the auto-weight scheduler. After each placement it waits for metrics to
stabilise and exports raw Prometheus samples plus derived weights to dedicated
CSV files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List

import pandas as pd
from prometheus_api_client import PrometheusConnect

if __package__ is None or __package__ == "":  # pragma: no cover - script execution
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from collector.cache import load_json, store_json  # type: ignore
else:  # pragma: no cover - package import
    from .cache import load_json, store_json

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
DEFAULT_METRICS = (
    "factorial_execution_time_seconds",
    "matrix_multiplication_time_seconds",
)


def run_command(cmd: List[str], *, env: dict[str, str] | None = None, label: str) -> None:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    print(f"\n➡️  {label}\n   $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=str(ROOT), env=full_env)


def list_services() -> List[str]:
    """Return all Docker Swarm service names (best effort)."""

    try:
        result = subprocess.run(
            ["docker", "service", "ls", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def resolve_service_names(patterns: List[str] | None) -> List[str]:
    """Resolve the requested service patterns to concrete service names."""

    available = list_services()
    if not available:
        return []

    if not patterns:
        return available

    resolved: set[str] = set()
    for pattern in patterns:
        matches = [svc for svc in available if pattern in svc]
        if matches:
            resolved.update(matches)
        elif pattern in available:
            resolved.add(pattern)
    return sorted(resolved)


def restart_services(services: List[str], iterations: int, interval: int) -> None:
    """Force-restart the specified services multiple times to gather fresh samples."""

    if iterations <= 0 or not services:
        return

    for cycle in range(1, iterations + 1):
        print(f"🔁 Restart cycle {cycle}/{iterations}")
        for service in services:
            print(f"   ↻ docker service update --force {service}")
            subprocess.run(
                ["docker", "service", "update", "--force", service],
                check=True,
                cwd=str(ROOT),
            )
        if cycle < iterations:
            print(f"   ⏳ Waiting {interval}s before next cycle…")
            time.sleep(interval)


def _collect_samples(prom: PrometheusConnect, metrics: List[str], minutes: int) -> pd.DataFrame:
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(minutes=minutes)

    rows = []
    for metric in metrics:
        try:
            data = prom.custom_query_range(
                query=metric,
                start_time=start,
                end_time=end,
                step="30s",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Error fetching {metric}: {exc}")
            continue

        if not data:
            print(f"⚠️ No series returned for {metric} in the selected window.")
            continue

        for series in data:
            labels = series["metric"]
            for ts, val in series["values"]:
                try:
                    completed_at = dt.datetime.fromtimestamp(float(ts), tz=dt.timezone.utc)
                    duration = float(val)
                    service_label = labels.get("service_name", "unknown")
                    service_type = (
                        "factorial"
                        if "factorial" in metric
                        else "matrix"
                        if "matrix" in metric
                        else "other"
                    )
                    container = (
                        labels.get("container_id")
                        or labels.get("container")
                        or labels.get("pod")
                        or "unknown"
                    )
                    node = labels.get("node_name") or labels.get("instance") or "unknown"
                    task = labels.get("task") or labels.get("swarm_task") or "unknown"

                    rows.append(
                        {
                            "metric": metric,
                            "service": service_label,
                            "service_type": service_type,
                            "node": node,
                            "container": container,
                            "task": task,
                            "job": labels.get("job", "unknown"),
                            "instance": labels.get("instance", "unknown"),
                            "address": labels.get("__address__", labels.get("instance", "unknown")),
                            "duration_seconds": duration,
                            "completed_at": completed_at,
                            "started_at": completed_at - dt.timedelta(seconds=duration),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"⚠️ Skipped invalid sample for {metric}: {exc}")
                    continue

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["duration_seconds"] = df["duration_seconds"].astype(float)
    df["completed_at"] = pd.to_datetime(df["completed_at"], utc=True)
    df["started_at"] = pd.to_datetime(df["started_at"], utc=True)
    df.sort_values("completed_at", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def _compute_weights(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=["service_type", "metric", "service", "weight", "mean", "std", "samples"]
        )

    summary = (
        df.groupby(["service_type", "metric", "service"], dropna=False)["duration_seconds"]
        .agg(["mean", "std", "size"])
        .reset_index()
        .rename(columns={"size": "samples"})
    )
    summary["raw_weight"] = 1.0 / summary["mean"].clip(lower=1e-9)
    summary["weight"] = summary["raw_weight"] / summary.groupby("metric")["raw_weight"].transform("sum")
    return summary[["service_type", "metric", "service", "weight", "mean", "std", "samples"]]


def _prepare_samples(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure datetime columns are timezone-aware and sorted."""

    if df.empty:
        return df

    for col in ("completed_at", "started_at"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    df.sort_values("completed_at", inplace=True, ignore_index=True)
    return df


def export_prometheus_csv(
    strategy: str,
    prom_url: str,
    window_minutes: int,
    results_path: Path,
    weights_path: Path,
    metrics: List[str] | None = None,
) -> None:
    print(f"\n➡️  Export metrics ({strategy}) → {results_path.name}")
    metrics = metrics or list(DEFAULT_METRICS)
    prom = PrometheusConnect(url=prom_url, disable_ssl=not prom_url.startswith("https"))
    cache_key = Path(f"replay_{strategy}_samples.json")

    try:
        samples = _collect_samples(prom, metrics, window_minutes)
    except Exception as exc:  # noqa: BLE001
        cached = load_json(cache_key)
        if cached:
            print(
                f"⚠️ Prometheus query failed ({exc}); using cached samples for {strategy}."
            )
            samples = pd.DataFrame(cached)
            samples = _prepare_samples(samples)
        else:
            raise

    if samples.empty:
        cached = load_json(cache_key)
        if cached:
            print(f"⚠️ No fresh samples; reusing cached dataset for {strategy}.")
            samples = pd.DataFrame(cached)
            samples = _prepare_samples(samples)
        else:
            print(f"⚠️ No samples retrieved for {strategy}; writing empty CSV files.")
            samples.to_csv(results_path, index=False)
            weights = _compute_weights(samples)
            weights.to_csv(weights_path, index=False)
            return
    else:
        store_json(samples.to_dict(orient="records"), cache_key)

    samples = _prepare_samples(samples)

    samples.to_csv(results_path, index=False)
    weights = _compute_weights(samples)
    weights.to_csv(weights_path, index=False)

    unique_services = samples["service"].nunique(dropna=False)
    unique_nodes = samples["node"].nunique(dropna=False)
    window_start = samples["started_at"].min()
    window_end = samples["completed_at"].max()
    print(
        f"📈 {strategy}: captured {len(samples)} samples across {unique_services} services "
        f"on {unique_nodes} nodes ({window_start.isoformat()} → {window_end.isoformat()})."
    )


def apply_spread(prom_url: str, services: List[str] | None) -> None:
    cmd = [PYTHON, str(ROOT / "collector" / "spread_reset.py"), "--force"]
    if services:
        cmd.extend(["--services", *services])
    run_command(cmd, label="Reset services to Spread placement")


def apply_manual(prom_url: str, services: List[str] | None, cpu_weight: float, mem_weight: float) -> None:
    cmd = [
        PYTHON,
        str(ROOT / "collector" / "manual_weight_scheduler.py"),
        "--prom-url",
        prom_url,
        "--cpu-weight",
        str(cpu_weight),
        "--mem-weight",
        str(mem_weight),
        "--apply",
        "--force-update",
    ]
    if services:
        cmd.extend(["--services", *services])
    run_command(cmd, label="Apply manual weighting placement")


def apply_auto(prom_url: str, strategy: str) -> None:
    env = {
        "PROM_URL": prom_url,
        "SCHEDULER_STRATEGY": strategy,
        "SCHEDULER_INTERVAL": "0",
    }
    cmd = [PYTHON, str(ROOT / "collector" / "auto_weight_scheduler.py")]
    run_command(cmd, env=env, label=f"Run auto scheduler ({strategy})")


def wait_for_metrics(seconds: int) -> None:
    if seconds <= 0:
        return
    print(f"⏳ Waiting {seconds}s for Prometheus to collect fresh samples…")
    time.sleep(seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay Spread, manual, and auto scheduling strategies with CSV exports.",
    )
    parser.add_argument(
        "--prom-url",
        default="http://localhost:9090",
        help="Prometheus base URL (default: http://localhost:9090)",
    )
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=10,
        help="Lookback window in minutes when exporting metrics (default: 10)",
    )
    parser.add_argument(
        "--settle-seconds",
        type=int,
        default=120,
        help="Delay after each placement change before sampling metrics (default: 120)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports") / "replay",
        help="Directory for per-strategy CSV exports (default: reports/replay)",
    )
    parser.add_argument(
        "--services",
        nargs="+",
        default=None,
        help="Optional list of service name patterns to restrict the replay",
    )
    parser.add_argument(
        "--restart-iterations",
        type=int,
        default=0,
        help="Number of forced restarts per service before exporting metrics (default: 0)",
    )
    parser.add_argument(
        "--restart-interval",
        type=int,
        default=70,
        help="Delay in seconds between restart cycles when --restart-iterations > 0 (default: 70)",
    )
    parser.add_argument(
        "--manual-cpu-weight",
        type=float,
        default=0.7,
        help="CPU weight used when ranking nodes in the manual step (default: 0.7)",
    )
    parser.add_argument(
        "--manual-mem-weight",
        type=float,
        default=0.3,
        help="Memory weight used when ranking nodes in the manual step (default: 0.3)",
    )
    parser.add_argument(
        "--auto-strategy",
        default="weighted",
        choices=("weighted", "round_robin", "least_loaded"),
        help="Auto scheduler strategy to execute (default: weighted)",
    )
    parser.add_argument("--skip-spread", action="store_true", help="Skip the Spread replay step")
    parser.add_argument("--skip-manual", action="store_true", help="Skip the manual weighting step")
    parser.add_argument("--skip-auto", action="store_true", help="Skip the auto scheduler step")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    service_patterns = args.services
    resolved_services = resolve_service_names(service_patterns)
    if args.restart_iterations > 0:
        if not resolved_services:
            print("⚠️ No matching services found for restart cycles; service restarts will be skipped.")
        else:
            print(f"🗂️  Restart target services: {', '.join(resolved_services)}")

    if not args.skip_spread:
        apply_spread(args.prom_url, service_patterns)
        restart_services(resolved_services, args.restart_iterations, args.restart_interval)
        wait_for_metrics(args.settle_seconds)
        export_prometheus_csv(
            strategy="spread",
            prom_url=args.prom_url,
            window_minutes=args.window_minutes,
            results_path=output_dir / "spread_results_metrics.csv",
            weights_path=output_dir / "spread_weights_metrics.csv",
        )

    if not args.skip_manual:
        apply_manual(args.prom_url, service_patterns, args.manual_cpu_weight, args.manual_mem_weight)
        restart_services(resolved_services, args.restart_iterations, args.restart_interval)
        wait_for_metrics(args.settle_seconds)
        export_prometheus_csv(
            strategy="manual",
            prom_url=args.prom_url,
            window_minutes=args.window_minutes,
            results_path=output_dir / "manual_results_metrics.csv",
            weights_path=output_dir / "manual_weights_metrics.csv",
        )

    if not args.skip_auto:
        apply_auto(args.prom_url, args.auto_strategy)
        restart_services(resolved_services, args.restart_iterations, args.restart_interval)
        wait_for_metrics(args.settle_seconds)
        export_prometheus_csv(
            strategy=f"auto_{args.auto_strategy}",
            prom_url=args.prom_url,
            window_minutes=args.window_minutes,
            results_path=output_dir / f"auto_{args.auto_strategy}_results_metrics.csv",
            weights_path=output_dir / f"auto_{args.auto_strategy}_weights_metrics.csv",
        )

    print("\n✅ Replay complete. CSV outputs stored under", output_dir)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
