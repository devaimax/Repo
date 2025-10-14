"""Manual weighted placement helper for Docker Swarm.

This script extends the algorithm from Ramavat & Patel (2024) with three
quality-of-life features needed for experiment automation:

* Optional Prometheus integration to fetch live node utilisation data.
* Direct application of node constraints to Swarm services when requested.
* Convenience defaults for the factorial and matrix workloads used in this
  repository.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from prometheus_api_client import PrometheusConnect
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    pass


if __package__ is None or __package__ == "":  # pragma: no cover - script execution
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from collector.result_exporter import export_strategy_results, DEFAULT_METRICS  # type: ignore
    from collector.cache import store_json, load_json  # type: ignore
else:  # pragma: no cover - normal package import
    from .result_exporter import export_strategy_results, DEFAULT_METRICS
    from .cache import store_json, load_json

# قائمة الخدمات التي نعيد استهدافها بشكل افتراضي عند التشغيل التلقائي
DEFAULT_SERVICE_PATTERNS = [
    "fact_100k",
    "fact_200k",
    "fact_300k",
    "fact_400k",
    "fact_500k",
    "matrix_4k",
    "matrix_5k",
    "matrix_6k",
    "matrix_7k",
    "matrix_8k",
]

# Factorial services are CPU bound; matrix services are memory bound. Keeping
# these ratios inline with the paper ensures comparable behaviour out of the box.
# الأوزان الافتراضية كما وردت في الورقة (CPU, MEM) لكل خدمة
DEFAULT_WEIGHTS: Dict[str, tuple[float, float]] = {
    "fact_100k": (0.7, 0.3),
    "fact_200k": (0.7, 0.3),
    "fact_300k": (0.7, 0.3),
    "fact_400k": (0.7, 0.3),
    "fact_500k": (0.7, 0.3),
    "matrix_4k": (0.3, 0.7),
    "matrix_5k": (0.3, 0.7),
    "matrix_6k": (0.3, 0.7),
    "matrix_7k": (0.3, 0.7),
    "matrix_8k": (0.3, 0.7),
}

NODE_CACHE_FILE = Path("manual_nodes.json")


@dataclass
class NodeMetrics:
    # يمثل استخدام الموارد لكل عقدة يتم احتسابها في الخوارزمية
    """Container for per-node utilisation percentages."""

    name: str
    cpu_usage_percent: float
    memory_usage_percent: float
    hostname: str | None = None

    def clamp(self) -> "NodeMetrics":
        """Return a copy with utilisation constrained to [0, 100]."""

        return NodeMetrics(
            name=self.name,
            cpu_usage_percent=min(max(self.cpu_usage_percent, 0.0), 100.0),
            memory_usage_percent=min(max(self.memory_usage_percent, 0.0), 100.0),
            hostname=self.hostname,
        )


def compute_score(node: NodeMetrics, cpu_weight: float, mem_weight: float) -> float:
    # تحويل نسب الاستهلاك إلى درجة تفضيل باستخدام الأوزان الحالية
    """Compute the weighted availability score for a node."""

    clamped = node.clamp()
    available_cpu = 100.0 - clamped.cpu_usage_percent
    available_mem = 100.0 - clamped.memory_usage_percent
    return (cpu_weight * available_cpu) + (mem_weight * available_mem)


def rank_nodes(nodes: Sequence[NodeMetrics], cpu_weight: float, mem_weight: float) -> List[tuple[NodeMetrics, float]]:
    # فرز العقد تنازليًا حسب الدرجة حتى نحدد العقد الأكثر جاهزية
    """Return nodes sorted by score descending."""

    scored = [(node, compute_score(node, cpu_weight, mem_weight)) for node in nodes]
    return sorted(scored, key=lambda item: item[1], reverse=True)


def parse_nodes_csv(path: Path) -> List[NodeMetrics]:
    # قراءة ملف CSV محلي بدل Prometheus لاستخدامه في الاختبارات أو التشغيل دون شبكة
    """Load node metrics from a CSV file."""

    nodes: List[NodeMetrics] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"node", "cpu_usage_percent", "memory_usage_percent"}
        if not required.issubset(reader.fieldnames or set()):
            raise ValueError(
                f"CSV must contain headers {sorted(required)} but found {reader.fieldnames}"
            )
        for row in reader:
            try:
                nodes.append(
                    NodeMetrics(
                        name=row["node"],
                        cpu_usage_percent=float(row["cpu_usage_percent"]),
                        memory_usage_percent=float(row["memory_usage_percent"]),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid numeric value in row {row}") from exc
    return nodes


def parse_node_arguments(raw_nodes: Iterable[str]) -> List[NodeMetrics]:
    # دعم تمرير القيم مباشرة من سطر الأوامر بصيغة name,cpu,mem
    """Parse --node arguments formatted as name,cpu_percent,mem_percent."""

    parsed: List[NodeMetrics] = []
    for raw in raw_nodes:
        parts = [part.strip() for part in raw.split(",")]
        if len(parts) != 3:
            raise ValueError(f"Expected --node name,cpu,mem but got: {raw}")
        name, cpu_str, mem_str = parts
        try:
            parsed.append(
                NodeMetrics(
                    name=name,
                    cpu_usage_percent=float(cpu_str),
                    memory_usage_percent=float(mem_str),
                )
            )
        except ValueError as exc:
            raise ValueError(f"Invalid utilisation numbers in --node {raw}") from exc
    return parsed


def normalise_weights(cpu_weight: float, mem_weight: float) -> tuple[float, float]:
    # تأكيد أن مجموع الأوزان = 1 لتبسيط الحسابات
    """Normalise weights so they sum to 1 unless both are zero."""

    total = cpu_weight + mem_weight
    if total <= 0:
        raise ValueError("At least one weight must be positive")
    return cpu_weight / total, mem_weight / total


def prompt_weight(label: str) -> float:
    """Interactively request a non-negative weight from the user."""

    while True:
        raw = input(f"Enter {label} weight (>= 0): ").strip()
        try:
            value = float(raw)
        except ValueError:
            print("❌ Invalid number, try again.")
            continue
        if value < 0:
            print("❌ Weight must be non-negative.")
            continue
        return value


def build_argument_parser() -> argparse.ArgumentParser:
    # تعريف واجهة سطر الأوامر للتحكم في الخوارزمية والخيارات الإضافية
    parser = argparse.ArgumentParser(
        description="Compute node scores using the manual weighted resource optimisation algorithm.",
    )
    parser.add_argument("--cpu-weight", type=float, default=None, help="Manual weight for CPU (>= 0)")
    parser.add_argument("--mem-weight", type=float, default=None, help="Manual weight for memory (>= 0)")
    parser.add_argument(
        "--nodes-csv",
        type=Path,
        help="CSV file containing node,cpu_usage_percent,memory_usage_percent",
    )
    parser.add_argument(
        "--node",
        action="append",
        default=[],
        metavar="NAME,CPU_USAGE,MEM_USAGE",
        help="Inline node definition (can be repeated)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=0,
        help="Show only the top N nodes (0 shows all nodes)",
    )
    parser.add_argument(
        "--prom-url",
        default=None,
        help="Fetch node metrics directly from Prometheus instead of CSV/inline nodes",
    )
    parser.add_argument(
        "--services",
        nargs="+",
        default=None,
        help="Service name patterns to manage (defaults to factorial/matrix workloads)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply placement decisions to the selected services",
    )
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="Restart services after updating constraints to let Spread honour the decision immediately",
    )
    parser.add_argument(
        "--export-excel",
        action="store_true",
        help="Export Prometheus samples for this strategy into reports/manual_results.xlsx",
    )
    parser.add_argument(
        "--export-window",
        type=int,
        default=10,
        help="Sampling window in minutes when exporting Excel results (default: 10)",
    )
    parser.add_argument(
        "--export-metrics",
        nargs="+",
        default=None,
        help="Override metric names for the Excel export",
    )
    parser.add_argument(
        "--export-out",
        default=None,
        help="Custom Excel path (default: reports/manual_results.xlsx)",
    )
    return parser


def _env_aliases() -> Dict[str, str]:
    """Read NODE_ALIAS_MAP (ip=hostname pairs)."""

    mapping: Dict[str, str] = {}
    # يسمح بربط عناوين overlay بأسماء العقد الحقيقية عند التشغيل من خارج السوارم
    alias_env = os.getenv("NODE_ALIAS_MAP")
    if not alias_env:
        return mapping
    for entry in alias_env.split(","):
        if not entry.strip() or "=" not in entry:
            continue
        ip, alias = entry.split("=", 1)
        ip = ip.strip()
        alias = alias.strip()
        if ip and alias:
            mapping[ip] = alias
    return mapping


def node_alias_map() -> Dict[str, str]:
    """Return a mapping of advertise IPs, node IDs, and aliases to hostnames."""

    mapping: Dict[str, str] = _env_aliases()

    try:
        # نجمع بيانات إضافية من docker node inspect حتى نتعامل مع كل حالات التسمية
        node_ids_result = subprocess.run(
            ["docker", "node", "ls", "-q"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return mapping

    node_ids = [nid.strip() for nid in node_ids_result.stdout.splitlines() if nid.strip()]
    if not node_ids:
        return mapping

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
    except subprocess.CalledProcessError:
        return mapping

    for line in inspect_result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        hostname = (
            data.get("Description", {}).get("Hostname")
            or data.get("Spec", {}).get("Name")
            or data.get("Hostname")
        )
        node_id = data.get("ID")
        if not hostname:
            continue

        if node_id:
            mapping[node_id] = hostname
            mapping[node_id[:12]] = hostname

        status_addr = (
            data.get("Status", {}).get("Addr")
            if isinstance(data.get("Status"), dict)
            else None
        )
        if status_addr:
            mapping[status_addr.split(":")[0]] = hostname

        manager_status = data.get("ManagerStatus")
        if isinstance(manager_status, dict):
            manager_addr = manager_status.get("Addr")
            if manager_addr:
                mapping[manager_addr.split(":")[0]] = hostname

    try:
        ls_raw = subprocess.run(
            ["docker", "node", "ls", "--format", "{{.ID}} {{.Hostname}} {{.Spec.Name}} {{.Status.Addr}}"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in ls_raw.stdout.splitlines():
            parts = line.split()
            if not parts:
                continue
            node_id = parts[0]
            host = parts[1] if len(parts) > 1 else ""
            spec_name = parts[2] if len(parts) > 2 else ""
            addr = parts[3] if len(parts) > 3 else ""
            canonical = spec_name or host or mapping.get(node_id)
            if not canonical:
                continue
            if node_id:
                mapping.setdefault(node_id, canonical)
                mapping.setdefault(node_id[:12], canonical)
            if host:
                mapping.setdefault(host, canonical)
            if addr:
                mapping.setdefault(addr.split(":")[0], canonical)
    except subprocess.CalledProcessError:
        pass

    return mapping

def _resolve_hostname(token: str, aliases: Dict[str, str], hostnames: List[str]) -> str | None:
    env_aliases = _env_aliases()
    candidates: List[str] = []
    cand = aliases.get(token)
    if cand:
        candidates.append(cand)
    cand = env_aliases.get(token)
    if cand:
        candidates.append(cand)
    for key, value in aliases.items():
        if not value:
            continue
        if token == value and value not in candidates:
            candidates.append(value)
        if key.startswith(token) and value not in candidates:
            candidates.append(value)
    for value in env_aliases.values():
        if value == token and value not in candidates:
            candidates.append(value)
    try:
        result = subprocess.run(
            ["docker", "node", "inspect", token, "--format", "{{.Description.Hostname}}"],
            capture_output=True,
            text=True,
            check=True,
        )
        inspected = result.stdout.strip()
        if inspected:
            candidates.append(inspected)
    except subprocess.CalledProcessError:
        pass
    for cand in candidates:
        if cand and cand in hostnames:
            return cand
    return None


def load_nodes_from_prom(prom_url: str) -> List[NodeMetrics]:
    """Pull node utilisation directly from Prometheus targets."""

    prom = PrometheusConnect(url=prom_url, disable_ssl=not prom_url.startswith("https"))

    # استعلامات PromQL تحسب استهلاك CPU/MEM كنسبة مئوية خلال الدقيقة الماضية
    cpu_query = '100 - (avg by (instance)(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)'
    mem_query = '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100'

    cpu_data = prom.custom_query(cpu_query)
    mem_data = prom.custom_query(mem_query)

    node_info_map: Dict[str, str] = {}
    try:
        node_info = prom.custom_query("node_uname_info")
        for item in node_info:
            labels = item.get("metric", {})
            instance = labels.get("instance")
            nodename = labels.get("nodename")
            if instance and nodename:
                node_info_map[instance.split(":")[0]] = nodename
    except Exception:
        pass

    cpu_map = {item["metric"]["instance"]: float(item["value"][1]) for item in cpu_data}
    mem_map = {item["metric"]["instance"]: float(item["value"][1]) for item in mem_data}

    aliases = node_alias_map()

    nodes: List[NodeMetrics] = []
    for instance in sorted(set(cpu_map) | set(mem_map)):
        ip = instance.split(":")[0]
        nodes.append(
            NodeMetrics(
                name=ip,
                cpu_usage_percent=cpu_map.get(instance, 0.0),
                memory_usage_percent=mem_map.get(instance, 0.0),
                hostname=aliases.get(ip) or node_info_map.get(ip),
            )
        )
    store_json([asdict(node) for node in nodes], NODE_CACHE_FILE)
    return nodes


def load_nodes(args: argparse.Namespace) -> List[NodeMetrics]:
    """Load nodes from Prometheus, CSV, and/or --node arguments."""

    nodes: List[NodeMetrics] = []
    prom_error = False
    if args.prom_url:
        try:
            nodes.extend(load_nodes_from_prom(args.prom_url))
        except Exception as exc:  # noqa: BLE001 - network failures vary
            prom_error = True
            cached = load_json(NODE_CACHE_FILE)
            if cached:
                print(
                    "⚠️ Prometheus unreachable; using cached node metrics.")
                nodes.extend(NodeMetrics(**entry) for entry in cached)
            else:
                print(
                    f"⚠️ Prometheus unreachable ({exc}); no cached node metrics found.")
    if args.nodes_csv:
        nodes.extend(parse_nodes_csv(args.nodes_csv))
    if args.node:
        nodes.extend(parse_node_arguments(args.node))
    if not nodes:
        cached = load_json(NODE_CACHE_FILE)
        if cached:
            print("⚠️ Using cached node metrics as a fallback source.")
            nodes.extend(NodeMetrics(**entry) for entry in cached)
        elif prom_error:
            raise ValueError("Prometheus unreachable and no fallback node metrics available")
    unique: Dict[str, NodeMetrics] = {node.name: node for node in nodes}
    return list(unique.values())


def format_table(rows: Sequence[tuple[NodeMetrics, float]]) -> str:
    """Return a simple table of node scores."""

    header = f"{'Node':<20} {'CPU%':>8} {'MEM%':>8} {'Score':>10}"
    lines = [header]
    for node, score in rows:
        label = node.hostname or node.name
        lines.append(
            f"{label:<20} "
            f"{node.cpu_usage_percent:8.2f} "
            f"{node.memory_usage_percent:8.2f} "
            f"{score:10.2f}"
        )
    return "\n".join(lines)


def list_services() -> List[str]:
    """Return the current Docker Swarm services."""

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


def resolve_services(patterns: List[str] | None) -> List[str]:
    """Match requested patterns against running services for convenience."""

    available = list_services()
    if not available:
        return []

    patterns = patterns or DEFAULT_SERVICE_PATTERNS
    resolved: List[str] = []
    for pattern in patterns:
        matches = [svc for svc in available if pattern in svc]
        if matches:
            resolved.extend(matches)
        elif pattern in available:
            resolved.append(pattern)

    return sorted(set(resolved))


def service_weights(service: str) -> tuple[float, float]:
    """Get default weights for the requested service pattern."""

    for pattern, weights in DEFAULT_WEIGHTS.items():
        if pattern in service:
            return weights
    return (0.5, 0.5)


def known_hostnames() -> List[str]:
    """Enumerate Swarm node hostnames for constraint cleanup."""

    try:
        result = subprocess.run(
            ["docker", "node", "ls", "--format", "{{.Hostname}}"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def hostname_constraints(service: str) -> List[str]:
    """Return existing node.hostname constraints for the service."""

    try:
        result = subprocess.run(
            [
                "docker",
                "service",
                "inspect",
                "--format",
                "{{json .Spec.TaskTemplate.Placement.Constraints}}",
                service,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

    payload = result.stdout.strip()
    if not payload or payload in {"<no value>", "null"}:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []

    constraints: List[str] = []
    for item in data:
        if not isinstance(item, str):
            continue
        if item.replace(" ", "").startswith("node.hostname=="):
            constraints.append(item)
    return constraints


def apply_constraint(service: str, node: NodeMetrics, force: bool) -> None:
    """Pin a service to the selected node using Swarm constraints."""

    aliases = node_alias_map()
    hostnames = known_hostnames()

    target = node.hostname or aliases.get(node.name) or node.name

    # Remove any previous hostname constraints, even if they referenced raw IPs.
    for constraint in hostname_constraints(service):
        subprocess.run(
            [
                "docker",
                "service",
                "update",
                "--detach=true",
                "--constraint-rm",
                constraint,
                service,
            ],
            check=False,
        )

    if target not in hostnames:
        resolved = _resolve_hostname(target, aliases, hostnames)
        if resolved:
            target = resolved
        else:
            print(
                f"⚠️ {service}: no Docker node named '{target}'. Leaving service unconstrained (Spread fallback).",
            )
            return

    try:
        subprocess.run(
            [
                "docker",
                "service",
                "update",
                "--detach=true",
                "--constraint-add",
                f"node.hostname=={target}",
                service,
            ],
            check=True,
        )
        if force:
            subprocess.run(
                ["docker", "service", "update", "--detach=true", "--force", service],
                check=True,
            )
        print(f"✅ {service} pinned to {target}")
    except subprocess.CalledProcessError as exc:
        print(f"❌ Failed to update {service}: {exc}")


def describe_distribution(service: str) -> None:
    """Summarise where the service replicas are currently running."""

    try:
        result = subprocess.run(
            [
                "docker",
                "service",
                "ps",
                service,
                "--format",
                "{{.ID}}\t{{.Node}}\t{{.DesiredState}}\t{{.CurrentState}}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        print(f"⚠️ Could not inspect service {service}")
        return

    print(f"📌 Distribution for {service}:")
    for line in result.stdout.splitlines():
        print(f"   {line}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    if args.cpu_weight is None:
        args.cpu_weight = prompt_weight("CPU")
    if args.mem_weight is None:
        args.mem_weight = prompt_weight("memory")

    try:
        cpu_weight, mem_weight = normalise_weights(args.cpu_weight, args.mem_weight)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        nodes = load_nodes(args)
    except ValueError as exc:
        parser.error(str(exc))

    ranked: List[tuple[NodeMetrics, float]] = []
    if nodes:
        ranked = rank_nodes(nodes, cpu_weight, mem_weight)
        top_n = args.top if args.top and args.top > 0 else len(ranked)
        output = format_table(ranked[:top_n])
        print(output)

        best_node, best_score = ranked[0]
        print(
            "\nSelected node:",
            f"{best_node.name} (score={best_score:.2f}, cpu={best_node.cpu_usage_percent:.2f}%, mem={best_node.memory_usage_percent:.2f}%)",
        )
    elif args.apply:
        parser.error("No nodes provided. Use --prom-url, --nodes-csv or --node.")

    if not args.apply and not args.export_excel:
        return 0

    if args.apply:
        services = resolve_services(args.services)
        if not services:
            print("⚠️ No services matched the provided patterns; nothing to update.")
        else:
            print("\n🚀 Applying manual placement decisions:")
            for service in services:
                svc_cpu, svc_mem = service_weights(service)
                by_service = rank_nodes(nodes, svc_cpu, svc_mem)
                target, score = by_service[0]
                print(
                    f" - {service}: CPU weight={svc_cpu:.2f}, MEM weight={svc_mem:.2f} → "
                    f"target={target.name} (score={score:.2f})"
                )
                apply_constraint(service, target, args.force_update)
                describe_distribution(service)

    if args.export_excel:
        prom_url = args.prom_url or "http://localhost:9090"
        metrics = args.export_metrics or DEFAULT_METRICS
        out_path = Path(args.export_out) if args.export_out else Path("reports") / "manual_results.xlsx"
        export_strategy_results(
            method="manual",
            prom_url=prom_url,
            window_minutes=args.export_window,
            metrics=metrics,
            out_path=out_path,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
