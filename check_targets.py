import requests
import pandas as pd
from datetime import datetime

PROMETHEUS_URL = "http://localhost:9090"

def fetch_targets():
    url = f"{PROMETHEUS_URL}/api/v1/targets"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()["data"]["activeTargets"]

def check_targets():
    targets = fetch_targets()
    results = []
    for t in targets:
        job = t["labels"].get("job", "unknown")
        instance = t["labels"].get("instance", "unknown")
        state = t.get("health", "unknown")
        last_scrape = t.get("lastScrape", "never")
        results.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "job": job,
            "instance": instance,
            "state": state,
            "last_scrape": last_scrape
        })
    return pd.DataFrame(results)

if __name__ == "__main__":
    df = check_targets()
    print(df.to_string(index=False))

    # حفظ النتائج في CSV
    df.to_csv("targets_status.csv", mode="a", index=False, header=False)
    print("\n✅ Saved to targets_status.csv")
