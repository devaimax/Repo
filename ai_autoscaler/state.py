"""State collection utilities for the autoscaler."""

from __future__ import annotations

import json
import math
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests

from .config import AutoscalerConfig


@dataclass
class NodeObservation:
    hostname: str
    cpu_util: float
    mem_util: float
    running_services: List[str]
    timestamp: float = field(default_factory=time.time)

    @property
    def load_score(self) -> float:
        return max(self.cpu_util, self.mem_util)


class StateCollector:
    """Collects node/service telemetry using Prometheus with optional CLI fallback."""

    def __init__(self, config: AutoscalerConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.timeout = self.config.prom_timeout

    def fetch_node_metrics(self) -> Optional[Dict[str, Dict[str, float]]]:
        base = self.config.prom_url.rstrip("/")
        queries = {
            "cpu": "100 - (avg by (instance)(rate(node_cpu_seconds_total{mode=\"idle\"}[1m])) * 100)",
            "mem": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
        }
        results: Dict[str, Dict[str, float]] = {"cpu": {}, "mem": {}}
        for key, query in queries.items():
            try:
                resp = self.session.get(
                    f"{base}/api/v1/query",
                    params={"query": query},
                    timeout=self.config.prom_timeout,
                )
                resp.raise_for_status()
                payload = resp.json()
            except Exception:
                return None
            for item in payload.get("data", {}).get("result", []):
                instance = item.get("metric", {}).get("instance")
                value = item.get("value", [None, None])[1]
                if not instance or value is None:
                    continue
                ip = instance.split(":")[0]
                try:
                    results[key][ip] = float(value)
                except ValueError:
                    continue
        return results

    def list_services(self) -> Dict[str, List[str]]:
        try:
            output = subprocess.check_output(
                ["docker", "service", "ps", "--format", "{{.Service}} {{.Node}}", "--no-trunc"],
                text=True,
            )
        except subprocess.CalledProcessError:
            return {}
        mapping: Dict[str, List[str]] = {}
        for line in output.splitlines():
            if not line.strip():
                continue
            service, node = line.split(maxsplit=1)
            mapping.setdefault(node.strip(), []).append(service.strip())
        return mapping

    def inspect_nodes(self) -> Dict[str, str]:
        try:
            output = subprocess.check_output(
                ["docker", "node", "ls", "--format", "{{.Hostname}} {{.Status.Addr}}"],
                text=True,
            )
        except subprocess.CalledProcessError:
            return {}
        return {
            line.split()[1].split(":")[0]: line.split()[0]
            for line in output.splitlines()
            if line.strip() and len(line.split()) >= 2
        }

    def collect(self) -> List[NodeObservation]:
        prom_metrics = self.fetch_node_metrics()
        ip_to_host = self.inspect_nodes()
        services = self.list_services()

        observations: List[NodeObservation] = []

        if prom_metrics:
            for ip, hostname in ip_to_host.items():
                cpu = prom_metrics["cpu"].get(ip, 0.0) / 100.0
                mem = prom_metrics["mem"].get(ip, 0.0) / 100.0
                observations.append(
                    NodeObservation(
                        hostname=hostname,
                        cpu_util=min(max(cpu, 0.0), 1.0),
                        mem_util=min(max(mem, 0.0), 1.0),
                        running_services=services.get(hostname, []),
                    )
                )
            if observations:
                return observations

        # Fallback: only docker CLI (no percentages available)
        for hostname, svc in services.items():
            observations.append(
                NodeObservation(
                    hostname=hostname,
                    cpu_util=math.nan,
                    mem_util=math.nan,
                    running_services=svc,
                )
            )
        return observations

    def dump_snapshot(self, observations: Iterable[NodeObservation], destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        serializable = [
            {
                "hostname": obs.hostname,
                "cpu_util": obs.cpu_util,
                "mem_util": obs.mem_util,
                "running_services": obs.running_services,
                "timestamp": obs.timestamp,
            }
            for obs in observations
        ]
        destination.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
