"""
Auto Weight Scheduler for Docker Swarm (modular edition).

Responsibilities handled here:
- reading configuration / environment variables
- fetching node metrics from Prometheus
- orchestrating service distribution and deployment
- wiring together helper modules (logging, plotting, reporting, notifications)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Sequence

from prometheus_api_client import PrometheusConnect

if __package__ is None or __package__ == "":  # pragma: no cover - script invocation fallback
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from collector.log_utils import append_log, init_logs  # type: ignore
    from collector.notifier import notify  # type: ignore
    from collector.plotting import generate_plots  # type: ignore
    from collector.reporting import generate_pdf  # type: ignore
    from collector.strategies import (  # type: ignore
        NodeMetrics,
        auto_weights,
        compute_score,
        distribute_least_loaded,
        distribute_round_robin,
        distribute_weighted,
        rank_nodes,
    )
else:  # pragma: no cover - normal package imports
    from .log_utils import append_log, init_logs
    from .notifier import notify
    from .plotting import generate_plots
    from .reporting import generate_pdf
    from .strategies import (
        NodeMetrics,
        auto_weights,
        compute_score,
        distribute_least_loaded,
        distribute_round_robin,
        distribute_weighted,
        rank_nodes,
    )


# =====================================================================
# Configuration
# =====================================================================
PROM_URL = os.getenv("PROM_URL", "http://localhost:9090")
INTERVAL = int(os.getenv("SCHEDULER_INTERVAL", "0"))
STRATEGY = os.getenv("SCHEDULER_STRATEGY", "weighted")  # weighted | round_robin | least_loaded
SIMULATION = int(os.getenv("SIMULATION_MODE", "0"))

CSV_FILE = Path(os.getenv("LOG_FILE_PATH", "logs/auto_scheduler_log.csv"))
DB_FILE = Path(os.getenv("DB_FILE_PATH", "logs/auto_scheduler.db"))
REPORT_DIR = Path("reports")
PLOT_DIR = REPORT_DIR / "plots"

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")


# =====================================================================
# Prometheus helpers
# =====================================================================
def load_node_host_map() -> Dict[str, str]:
    """Return a mapping of node advertise IP -> Docker hostname."""

    try:
        node_ids_result = subprocess.run(
            ["docker", "node", "ls", "-q"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"⚠️ Could not list Docker nodes: {exc}")
        return {}

    node_ids = [nid.strip() for nid in node_ids_result.stdout.splitlines() if nid.strip()]
    if not node_ids:
        return {}

    try:
        inspect_result = subprocess.run(
            [
                "docker",
                "node",
                "inspect",
                "--format",
                "{{json .}}",
                *node_ids,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"⚠️ Could not inspect Docker nodes: {exc}")
        return {}

    mapping: Dict[str, str] = {}
    for line in inspect_result.stdout.splitlines():
        payload = line.strip()
        if not payload:
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue

        hostname = data.get("Description", {}).get("Hostname")
        if not hostname:
            continue

        status_addr = data.get("Status", {}).get("Addr")
        if status_addr:
            mapping[status_addr.split(":")[0]] = hostname

        manager_status = data.get("ManagerStatus") or {}
        manager_addr = manager_status.get("Addr") if isinstance(manager_status, dict) else None
        if manager_addr:
            mapping[manager_addr.split(":")[0]] = hostname

    if not mapping:
        try:
            ls_result = subprocess.run(
                [
                    "docker",
                    "node",
                    "ls",
                    "--format",
                    "{{.Hostname}} {{.Status.Addr}}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in ls_result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    hostname, addr = parts[0], parts[1]
                    mapping[addr.split(":")[0]] = hostname
        except subprocess.CalledProcessError:
            pass

    alias_env = os.getenv("NODE_ALIAS_MAP")
    if alias_env:
        for entry in alias_env.split(","):
            if not entry.strip() or "=" not in entry:
                continue
            ip, alias = entry.split("=", 1)
            if ip.strip() and alias.strip():
                mapping[ip.strip()] = alias.strip()

    return mapping


def fetch_node_metrics(prom_url: str) -> List[NodeMetrics]:
    """Fetch node CPU/MEM utilisation via Prometheus."""

    prom = PrometheusConnect(url=prom_url, disable_ssl=not prom_url.startswith("https"))

    cpu_query = '100 - (avg by (instance)(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)'
    mem_query = '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100'

    cpu_data = prom.custom_query(cpu_query)
    mem_data = prom.custom_query(mem_query)

    node_info_map: Dict[str, str] = {}
    try:
        node_info_data = prom.custom_query("node_uname_info")
        for item in node_info_data:
            labels = item.get("metric", {})
            instance = labels.get("instance")
            nodename = labels.get("nodename")
            if instance and nodename:
                node_info_map[instance.split(":")[0]] = nodename
    except Exception:
        pass

    cpu_map = {item["metric"]["instance"]: float(item["value"][1]) for item in cpu_data}
    mem_map = {item["metric"]["instance"]: float(item["value"][1]) for item in mem_data}

    host_map = load_node_host_map()

    nodes: List[NodeMetrics] = []
    for instance in set(cpu_map.keys()) | set(mem_map.keys()):
        nodes.append(
            NodeMetrics(
                name=instance.split(":")[0],
                cpu_usage_percent=cpu_map.get(instance, 0.0),
                memory_usage_percent=mem_map.get(instance, 0.0),
                hostname=host_map.get(instance.split(":")[0])
                or node_info_map.get(instance.split(":")[0]),
            )
        )
    return nodes


# =====================================================================
# Docker helpers
# =====================================================================
def list_services() -> List[str]:
    """Return Swarm service names (best-effort)."""

    try:
        result = subprocess.run(
            ["docker", "service", "ls", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"❌ Cannot list services: {exc}")
        return []

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def format_node_label(node: NodeMetrics) -> str:
    """Return a human-friendly label showing hostname and IP."""

    if node.hostname and node.hostname != node.name:
        return f"{node.hostname} ({node.name})"
    return node.name


def deploy_service(service: str, node: NodeMetrics, reason: str, cpu_weight: float, mem_weight: float, score: float) -> None:
    """Apply node constraints to a Swarm service and log the decision."""

    label = format_node_label(node)
    constraint_target = node.hostname or node.name

    print(f"\n🚀 Deploying '{service}' → {label}")
    print(f"   ↳ Reason: {reason}")

    if not SIMULATION:
        try:
            cmd = [
                "docker",
                "service",
                "update",
                "--constraint-rm",
                "node.hostname==*",
                "--constraint-add",
                f"node.hostname=={constraint_target}",
                service,
            ]
            subprocess.run(cmd, check=True)
            print(f"✅ Service '{service}' running on '{label}'")
        except subprocess.CalledProcessError as exc:
            print(f"❌ Failed to deploy {service}: {exc}")
    else:
        print("🟡 Simulation mode: no changes applied")

    append_log(CSV_FILE, DB_FILE, service, label, cpu_weight, mem_weight, score, reason)


# =====================================================================
# Orchestration
# =====================================================================
def run_once() -> None:
    nodes = fetch_node_metrics(PROM_URL)
    if not nodes:
        print("⚠️ No node metrics")
        return

    cpu_weight, mem_weight, avg_cpu, avg_mem = auto_weights(nodes)

    print(f"\n=== Run at {dt.datetime.now().isoformat()} ===")
    print(
        f"⚙️ Weights: CPU={cpu_weight:.2f}, MEM={mem_weight:.2f} "
        f"(Avg CPU={avg_cpu:.2f}%, Avg MEM={avg_mem:.2f}%)"
    )

    ranked = rank_nodes(nodes, cpu_weight, mem_weight)
    print("\n📊 Node Scores:")
    for node, score in ranked:
        label = format_node_label(node)
        print(
            f" - {label}: score={score:.2f}, "
            f"cpu={node.cpu_usage_percent:.2f}%, mem={node.memory_usage_percent:.2f}%"
        )

    services = list_services()
    if not services:
        print("⚠️ No services")
        return

    if STRATEGY == "round_robin":
        assignments = distribute_round_robin(services, ranked)
    elif STRATEGY == "least_loaded":
        assignments = distribute_least_loaded(services, ranked)
    else:
        assignments = distribute_weighted(services, ranked)

    print("\n📦 Service Distribution:")
    for service, node in assignments:
        score = compute_score(node, cpu_weight, mem_weight)
        label = format_node_label(node)
        reason = f"Node '{label}' selected by {STRATEGY} strategy"
        print(f"  - {service} → {label} ({reason}, score={score:.2f})")
        deploy_service(service, node, reason, cpu_weight, mem_weight, score)

    generate_plots(CSV_FILE, PLOT_DIR)
    generate_pdf(REPORT_DIR, PLOT_DIR)
    notify(
        message=(
            f"Scheduler run completed with strategy={STRATEGY}, "
            f"{len(assignments)} services placed."
        ),
        slack_webhook=SLACK_WEBHOOK,
        telegram_token=TG_TOKEN,
        telegram_chat_id=TG_CHAT,
    )


# =====================================================================
# Main entrypoint
# =====================================================================
def main(argv: Sequence[str] | None = None) -> int:  # noqa: ARG001 - argparse not used yet
    init_logs(CSV_FILE, DB_FILE)

    if INTERVAL > 0:
        print(f"⏳ Running scheduler every {INTERVAL}s (strategy={STRATEGY}, PROM={PROM_URL})")
        while True:
            run_once()
            print("\n⏱️ Sleeping...\n")
            time.sleep(INTERVAL)
    else:
        print(f"▶ Running scheduler once (strategy={STRATEGY}, PROM={PROM_URL})")
        run_once()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
