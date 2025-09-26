import argparse
import datetime as dt
from typing import List

import pandas as pd
from prometheus_api_client import PrometheusConnect


def collect_samples(prom: PrometheusConnect, metrics: List[str], minutes: int) -> pd.DataFrame:
    """Fetch raw samples from Prometheus for the requested window."""
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(minutes=minutes)

    print(f"📊 DEBUG: start={start}, end={end}")  # للتأكد أن start < end

    rows = []

    for metric in metrics:
        try:
            data = prom.custom_query_range(
                query=metric,
                start_time=start,
                end_time=end,
                step="30s",
            )
        except Exception as e:
            print(f"❌ Error fetching {metric}: {e}")
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
                    service_type = "factorial" if "factorial" in metric else "matrix" if "matrix" in metric else "other"
                    container = labels.get("container_id") or labels.get("container") or labels.get("pod") or "unknown"
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
                except Exception as ex:
                    print(f"⚠️ Skipped invalid sample for {metric}: {ex}")
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


def compute_weights(df: pd.DataFrame) -> pd.DataFrame:
    """Produce automatic weights per (metric, service) based on inverse mean."""
    if df.empty:
        return pd.DataFrame(
            columns=["service_type", "metric", "service", "weight", "mean", "std", "samples"]
        )

    summary = (
        df.groupby(["service_type", "metric", "service"], dropna=False)
        .agg(
            mean=("duration_seconds", "mean"),
            std=("duration_seconds", "std"),
            samples=("duration_seconds", "size"),
        )
        .reset_index()
    )

    # Avoid division by zero and normalise per-metric to sum to one.
    summary["raw_weight"] = 1.0 / summary["mean"].clip(lower=1e-9)
    summary["weight"] = summary["raw_weight"] / summary.groupby("metric")["raw_weight"].transform("sum")

    return summary[["service_type", "metric", "service", "weight", "mean", "std", "samples"]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Prometheus samples with automatic weighting")
    parser.add_argument(
        "--prom-url",
        default="http://localhost:9090",
        help="Prometheus base URL (default: http://localhost:9090)",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=["factorial_execution_time_seconds", "matrix_multiplication_time_seconds"],
        help="Metric names to export",
    )
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=10,
        help="Lookback window size in minutes (default: 10)",
    )
    parser.add_argument(
        "--results-out",
        default="results.csv",
        help="Path for raw samples CSV output (default: results.csv)",
    )
    parser.add_argument(
        "--weights-out",
        default="service_weights.csv",
        help="Path for aggregated weights CSV output (default: service_weights.csv)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    prom = PrometheusConnect(url=args.prom_url, disable_ssl=not args.prom_url.startswith("https"))

    samples = collect_samples(prom, args.metrics, args.window_minutes)
    samples.to_csv(args.results_out, index=False)

    weights = compute_weights(samples)
    weights.to_csv(args.weights_out, index=False)

    if samples.empty:
        print("⚠️ No samples retrieved; produced empty CSV files.")
        return

    unique_services = samples["service"].nunique(dropna=False)
    unique_nodes = samples["node"].nunique(dropna=False)
    window_start = samples["started_at"].min()
    window_end = samples["completed_at"].max()

    print(
        "📈 Captured "
        f"{len(samples)} samples across {unique_services} services spanning {unique_nodes} nodes "
        f"({window_start.isoformat()} → {window_end.isoformat()})."
    )

    if weights.empty:
        print("⚠️ No usable samples for computing weights; check metric coverage.")
    else:
        print(f"✅ Saved {args.results_out} and {args.weights_out} with automatic weights.")


if __name__ == "__main__":
    main()
