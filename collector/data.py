from prometheus_api_client import PrometheusConnect
from datetime import datetime, timedelta
import pandas as pd
import os
import time

def get_available_metrics(prom):
    return set(prom.all_metrics())

def find_first_existing_metric(possible_metrics, available_metrics):
    for metric in possible_metrics:
        if metric in available_metrics:
            return metric
    return None

def collect_metric_range(prom, query, start_time, end_time, step, label):
    print(f"[+] Collecting data for query: {query}")
    try:
        data = prom.custom_query_range(
            query=query,
            start_time=start_time,
            end_time=end_time,
            step=step
        )
    except Exception as e:
        print(f"[!] Error querying Prometheus: {e}")
        return pd.DataFrame()

    if not data:
        print(f"[!] No data for: {query}")
        return pd.DataFrame()

    records = []
    for result in data:
        labels = result.get("metric", {})
        node = labels.get("instance")
        container = labels.get("container") or labels.get("name")
        task = labels.get("task")
        process = labels.get("process") or labels.get("comm")

        for ts, val in result["values"]:
            try:
                records.append({
                    "timestamp": datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d %H:%M:%S'),
                    "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "end_time": end_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "node": node,
                    "container": container,
                    "task_name": task,
                    "process_name": process,
                    label: float(val)
                })
            except Exception:
                continue

    return pd.DataFrame(records)

def main():
    prom = PrometheusConnect(url="http://localhost:9090", disable_ssl=True)

    while True:
        print(f"\n=== Collecting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=1)
        step = "15s"

        available_metrics = get_available_metrics(prom)

        cpu_candidates = [
            'rate(container_cpu_usage_seconds_total[1m])',
            'process_cpu_seconds_total',
            'node_cpu_seconds_total',
        ]
        mem_candidates = [
            'container_memory_usage_bytes',
            'process_resident_memory_bytes',
            'node_memory_MemAvailable_bytes',
        ]

        all_data = []

        # CPU
        cpu_metric = find_first_existing_metric(
            [q.split('(')[-1].rstrip(')') if 'rate(' in q else q for q in cpu_candidates],
            available_metrics
        )
        if cpu_metric:
            full_cpu_query = next(q for q in cpu_candidates if cpu_metric in q)
            cpu_df = collect_metric_range(prom, full_cpu_query, start_time, end_time, step, "cpu_usage")
            if not cpu_df.empty:
                all_data.append(cpu_df)

        # Memory
        mem_metric = find_first_existing_metric(mem_candidates, available_metrics)
        if mem_metric:
            mem_df = collect_metric_range(prom, mem_metric, start_time, end_time, step, "memory_usage")
            if not mem_df.empty:
                all_data.append(mem_df)

        if all_data:
            merged_df = all_data[0]
            for df in all_data[1:]:
                merged_df = pd.merge(
                    merged_df, df,
                    on=["timestamp", "node", "container", "task_name", "process_name", "start_time", "end_time"],
                    how="outer"
                )

            # Clean and prepare
            merged_df = merged_df.drop_duplicates().sort_values("timestamp")    
            merged_df["cpu_usage"] = merged_df["cpu_usage"].fillna(0).astype(float)
            merged_df["memory_usage"] = merged_df["memory_usage"].fillna(0).astype(float)
            merged_df["duration_sec"] = (
                pd.to_datetime(merged_df["end_time"]) - pd.to_datetime(merged_df["start_time"])
            ).dt.total_seconds()

            merged_df["high_pressure"] = (
                (merged_df["cpu_usage"] > 0.8) | (merged_df["memory_usage"] > 900_000_000)
            ).astype(int)

            # Save
            output_file = "mydata_Set07.csv"
            file_exists = os.path.isfile(output_file)
            merged_df.to_csv(output_file, index=False, mode="a", header=not file_exists)
            print(f"[✔] Appended {len(merged_df)} rows to {output_file}")
        else:
            print("[!] No usable data collected this round.")

        time.sleep(60)

if __name__ == "__main__":
    main()
