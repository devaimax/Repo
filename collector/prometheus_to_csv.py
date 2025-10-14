"""Export Prometheus time-series samples to CSV.

This utility predates the richer `datat-Gatharing-promth.py` script, but now it
shares the same best practices: timezone-aware timestamps, explicit PromQL
queries using `custom_query_range`, and a small CLI for ad-hoc exports.
"""

from __future__ import annotations

import argparse
import datetime as dt
from typing import Iterable, List

import pandas as pd
from prometheus_api_client import PrometheusConnect


def collect_samples(
    prom: PrometheusConnect,
    metrics: Iterable[str],
    minutes: int,
    step: str = "30s",
) -> pd.DataFrame:
    """Fetch raw samples for each metric over the requested time window."""

    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(minutes=minutes)

    rows: List[dict] = []

    for metric in metrics:
        try:
            data = prom.custom_query_range(
                query=metric,
                start_time=start,
                end_time=end,
                step=step,
            )
        except Exception as exc:
            print(f"❌ Failed to fetch {metric}: {exc}")
            continue

        if not data:
            print(f"⚠️ No series returned for metric {metric} in the selected window")
            continue

        for series in data:
            labels = series.get("metric", {})
            for ts, val in series.get("values", []):
                try:
                    rows.append(
                        {
                            "metric": metric,
                            "service": labels.get("service_name", "unknown"),
                            "node": labels.get("node_name") or labels.get("instance", "unknown"),
                            "container": labels.get("container_id") or labels.get("container", "unknown"),
                            "timestamp": dt.datetime.fromtimestamp(float(ts), tz=dt.timezone.utc),
                            "value": float(val),
                        }
                    )
                except (TypeError, ValueError) as exc:
                    print(f"⚠️ Skipped invalid sample for {metric}: {exc}")
                    continue

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Prometheus metrics to CSV for quick analysis",
    )
    parser.add_argument(
        "--prom-url",
        default="http://localhost:9090",
        help="Prometheus base URL (default: http://localhost:9090)",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=["factorial_execution_time_seconds", "matrix_multiplication_time_seconds"],
        help="PromQL metrics or expressions to export",
    )
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=10,
        help="Lookback window size in minutes (default: 10)",
    )
    parser.add_argument(
        "--step",
        default="30s",
        help="Resolution step passed to query_range (default: 30s)",
    )
    parser.add_argument(
        "--out",
        default="prometheus_results.csv",
        help="Destination CSV path (default: prometheus_results.csv)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    prom = PrometheusConnect(url=args.prom_url, disable_ssl=not args.prom_url.startswith("https"))

    samples = collect_samples(prom, args.metrics, args.window_minutes, step=args.step)
    samples.to_csv(args.out, index=False)

    if samples.empty:
        print("⚠️ Export completed, but no samples were retrieved.")
        return

    unique_metrics = samples["metric"].nunique()
    unique_services = samples["service"].nunique(dropna=False)
    window_start = samples["timestamp"].min().isoformat()
    window_end = samples["timestamp"].max().isoformat()

    print(
        "✅ Exported "
        f"{len(samples)} samples for {unique_metrics} metrics across {unique_services} services "
        f"into {args.out} ({window_start} → {window_end})."
    )


if __name__ == "__main__":
    main()

