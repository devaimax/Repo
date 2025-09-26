import datetime as dt

def collect_samples(prom, metrics, minutes):
    """Fetch raw samples from Prometheus for the requested window."""
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(minutes=minutes)
    rows = []

    for metric in metrics:
        data = prom.get_metric_range_data(
            metric,
            start_time=start,
            end_time=end,
            chunk_size=dt.timedelta(minutes=1),
        )
        for series in data:
            labels = series["metric"]
            for ts, val in series["values"]:
                rows.append(
                    {
                        "metric": metric,
                        "service": labels.get("service_name", "unknown"),
                        "node": labels.get("node_name", "unknown"),
                        "container": labels.get("container_id", "unknown"),
                        "timestamp": dt.datetime.fromtimestamp(float(ts), tz=dt.timezone.utc),
                        "value": float(val),
                    }
                )
    return pd.DataFrame(rows)
