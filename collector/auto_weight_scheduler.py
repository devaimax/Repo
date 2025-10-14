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
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Sequence

from prometheus_api_client import PrometheusConnect
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    pass


if __package__ is None or __package__ == "":  # pragma: no cover - script invocation fallback
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from collector.log_utils import append_log, init_logs  # type: ignore
    from collector.notifier import notify  # type: ignore
    from collector.plotting import generate_plots  # type: ignore
    from collector.reporting import generate_pdf  # type: ignore
    from collector.cache import store_json, load_json  # type: ignore
    from collector.result_exporter import export_strategy_results, DEFAULT_METRICS  # type: ignore
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
    from .result_exporter import export_strategy_results, DEFAULT_METRICS
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
# رابط Prometheus المستخدم لجلب القياسات أثناء التشغيل الآلي
PROM_URL = os.getenv("PROM_URL", "http://localhost:9090")
# عند تعيين INTERVAL>0 تتحول الأداة لخدمة دورية
INTERVAL = int(os.getenv("SCHEDULER_INTERVAL", "0"))
# اختيار الاستراتيجية يؤثر على توزيع الخدمات بعد حساب الأوزان
STRATEGY = os.getenv("SCHEDULER_STRATEGY", "weighted")  # weighted | round_robin | least_loaded
SIMULATION = int(os.getenv("SIMULATION_MODE", "0"))
# عند تفعيل AUTO_FORCE_REDEPLOY نعيد نشر الخدمة بعد تحديث القيود لضمان حاويات جديدة
FORCE_REDEPLOY = os.getenv("AUTO_FORCE_REDEPLOY", "").strip().lower() in {"1", "true", "yes", "on"}

FALLBACK_BASE = Path.home() / ".docker-swarm-project"
FALLBACK_ARTIFACT_ROOT = FALLBACK_BASE / "logs"


def _ensure_writable_path(candidate: Path, fallback_name: str, purpose: str) -> Path:
    """Make sure we can write to the desired path; fall back to user space if needed."""

    candidate = candidate.expanduser()
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        if candidate.exists():
            with candidate.open("a"):
                pass
        else:
            with candidate.open("x"):
                pass
            candidate.unlink(missing_ok=True)
        return candidate
    except (OSError, PermissionError) as exc:
        fallback_path = (FALLBACK_ARTIFACT_ROOT / fallback_name).expanduser()
        try:
            candidate_resolved = candidate.resolve()
            fallback_resolved = fallback_path.resolve()
        except OSError:
            candidate_resolved = candidate.absolute()
            fallback_resolved = fallback_path.absolute()
        if candidate_resolved == fallback_resolved:
            raise RuntimeError(
                f"{purpose.capitalize()} destination {candidate} is not writable and no fallback is available."
            ) from exc

        print(
            f"⚠️ {purpose.capitalize()} destination {candidate} not writable ({exc}); "
            f"using {fallback_path}"
        )
        try:
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            if fallback_path.exists():
                with fallback_path.open("a"):
                    pass
            else:
                with fallback_path.open("x"):
                    pass
                fallback_path.unlink(missing_ok=True)
        except (OSError, PermissionError) as fallback_exc:
            raise RuntimeError(
                f"Unable to prepare fallback path {fallback_path} for {purpose}. "
                "Adjust permissions or set LOG_FILE_PATH/DB_FILE_PATH."
            ) from fallback_exc
        return fallback_path


def _ensure_writable_dir(candidate: Path, fallback_subdir: str, purpose: str) -> Path:
    """Verify we can create files inside a directory, otherwise redirect to user space."""

    candidate = candidate.expanduser()
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        probe = candidate / ".write_probe"
        with probe.open("w"):
            pass
        probe.unlink(missing_ok=True)
        return candidate
    except (OSError, PermissionError) as exc:
        fallback_path = (FALLBACK_BASE / fallback_subdir).expanduser()
        try:
            candidate_resolved = candidate.resolve()
            fallback_resolved = fallback_path.resolve()
        except OSError:
            candidate_resolved = candidate.absolute()
            fallback_resolved = fallback_path.absolute()
        if candidate_resolved == fallback_resolved:
            raise RuntimeError(
                f"{purpose.capitalize()} directory {candidate} is not writable and no fallback is available."
            ) from exc
        print(
            f"⚠️ {purpose.capitalize()} directory {candidate} not writable ({exc}); "
            f"using {fallback_path}"
        )
        try:
            fallback_path.mkdir(parents=True, exist_ok=True)
            probe = fallback_path / ".write_probe"
            with probe.open("w"):
                pass
            probe.unlink(missing_ok=True)
        except (OSError, PermissionError) as fallback_exc:
            raise RuntimeError(
                f"Unable to prepare fallback directory {fallback_path} for {purpose}. "
                "Adjust permissions or set REPORT_DIR."
            ) from fallback_exc
        return fallback_path


DEFAULT_LOG_PATH = Path("logs/auto_scheduler_log.csv")
DEFAULT_DB_PATH = Path("logs/auto_scheduler.db")

CSV_FILE = _ensure_writable_path(
    Path(os.getenv("LOG_FILE_PATH", str(DEFAULT_LOG_PATH))),
    fallback_name="auto_scheduler_log.csv",
    purpose="log",
)
DB_FILE = _ensure_writable_path(
    Path(os.getenv("DB_FILE_PATH", str(DEFAULT_DB_PATH))),
    fallback_name="auto_scheduler.db",
    purpose="database",
)

REPORT_ROOT = Path(os.getenv("REPORT_DIR", "reports"))
REPORT_DIR = _ensure_writable_dir(REPORT_ROOT, "reports", "report output")
PLOT_DIR = _ensure_writable_dir(REPORT_DIR / "plots", "reports/plots", "plot output")

# نخزن آخر لقطة لقياسات العقد لاستعمالها عند انقطاع Prometheus
NODE_CACHE_FILE = Path("auto_nodes.json")

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")

EXPORT_EXCEL = os.getenv("EXPORT_EXCEL", "0") == "1"
EXPORT_EXCEL_OUT = os.getenv("EXPORT_EXCEL_OUT")
EXPORT_EXCEL_WINDOW = int(os.getenv("EXPORT_EXCEL_WINDOW", "10"))
EXPORT_EXCEL_METRICS = tuple(
    metric.strip()
    for metric in os.getenv("EXPORT_EXCEL_METRICS", "").split(",")
    if metric.strip()
) or DEFAULT_METRICS
def load_node_host_map() -> Dict[str, str]:
    """Return a mapping of node identifiers (IP/ID) to hostnames."""

    mapping: Dict[str, str] = {}

    try:
        # نعتمد على docker node ls/inspect لبناء جدول تحويل شامل
        node_ids_result = subprocess.run(
            ["docker", "node", "ls", "-q"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"⚠️ Could not list Docker nodes: {exc}")
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
    except subprocess.CalledProcessError as exc:
        print(f"⚠️ Could not inspect Docker nodes: {exc}")
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

        status = data.get("Status") if isinstance(data.get("Status"), dict) else {}
        status_addr = status.get("Addr") if isinstance(status, dict) else None
        if status_addr:
            mapping[status_addr.split(":")[0]] = hostname

        manager_status = data.get("ManagerStatus") or {}
        manager_addr = manager_status.get("Addr") if isinstance(manager_status, dict) else None
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
    except subprocess.CalledProcessError as exc:
        print(f"⚠️ Could not list Docker nodes (fallback): {exc}")

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

    # استعلامات PromQL تحوّل معلومات node_exporter إلى نسب استعمال
    cpu_query = '100 - (avg by (instance)(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)'
    mem_query = '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100'

    cpu_data = prom.custom_query(cpu_query)
    mem_data = prom.custom_query(mem_query)

    node_info_map: Dict[str, str] = {}
    try:
        # نحاول إضافة أسماء العقد من node_uname_info كمرجع إضافي
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
    store_json([asdict(node) for node in nodes], NODE_CACHE_FILE)
    return nodes


# =====================================================================
# Docker helpers
# =====================================================================
def list_services() -> List[str]:
    """Return Swarm service names (best-effort)."""

    try:
        # نعتمد على docker service ls للحصول على قائمة الخدمات الحالية
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
        # نعرض label "hostname (ip)" لتسهيل قراءة السجلات
        return f"{node.hostname} ({node.name})"
    return node.name


def hostname_constraints(service: str) -> List[str]:
    """Return existing node.hostname constraints for a service."""

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
    if not payload or payload in {"null", "<no value>"}:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, str) and item.startswith("node.hostname==")]


def deploy_service(service: str, node: NodeMetrics, reason: str, cpu_weight: float, mem_weight: float, score: float) -> None:
    """Apply node constraints to a Swarm service and log the decision."""

    # نحدّث قيود الخدمة ثم نسجل السبب بهدف التتبع/التقرير
    label = format_node_label(node)
    constraint_target = node.hostname or node.name

    aliases = load_node_host_map()
    env_alias = os.getenv("NODE_ALIAS_MAP", "")
    env_map = dict(
        entry.split("=", 1) for entry in env_alias.split(",") if "=" in entry
    ) if env_alias else {}
    if constraint_target not in aliases.values():
        resolved = aliases.get(constraint_target) or env_map.get(constraint_target)
        if not resolved:
            for key, value in aliases.items():
                if key.startswith(constraint_target):
                    resolved = value
                    break
        if resolved:
            constraint_target = resolved

    print(f"\n🚀 Deploying '{service}' → {label}")
    print(f"   ↳ Reason: {reason}")

    if not SIMULATION:
        try:
            existing = hostname_constraints(service)
            for constraint in existing:
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

            subprocess.run(
                [
                    "docker",
                    "service",
                    "update",
                    "--detach=true",
                    "--constraint-add",
                    f"node.hostname=={constraint_target}",
                    service,
                ],
                check=True,
            )
            if FORCE_REDEPLOY:
                subprocess.run(
                    [
                        "docker",
                        "service",
                        "update",
                        "--detach=true",
                        "--force",
                        service,
                    ],
                    check=True,
                )
                print("   ↳ Forced redeploy triggered (AUTO_FORCE_REDEPLOY enabled)")
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
    # تنفيذ دورة جدولة واحدة تتضمن الجلب، الحساب، التوزيع، 
    try:
        nodes = fetch_node_metrics(PROM_URL)
    except Exception as exc:  # noqa: BLE001 - Prometheus/network failures vary
        cached = load_json(NODE_CACHE_FILE)
        if cached:
            print(
                "⚠️ Prometheus unreachable; using cached node metrics.")
            nodes = [NodeMetrics(**entry) for entry in cached]
        else:
            print(f"⚠️ Prometheus unreachable ({exc}); no cached node metrics available.")
            return
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

    # طباعة القرار النهائي قبل التنفيذ يساعد في مراجعة النتائج الحية
    print("\n📦 Service Distribution:")
    for service, node in assignments:
        score = compute_score(node, cpu_weight, mem_weight)
        label = format_node_label(node)
        reason = f"Node '{label}' selected by {STRATEGY} strategy"
        print(f"  - {service} → {label} ({reason}, score={score:.2f})")
        deploy_service(service, node, reason, cpu_weight, mem_weight, score)

    plot_outputs = generate_plots(CSV_FILE, PLOT_DIR)
    generate_pdf(REPORT_DIR, PLOT_DIR, plot_outputs)
    notify(
        message=(
            f"Scheduler run completed with strategy={STRATEGY}, "
            f"{len(assignments)} services placed."
        ),
        slack_webhook=SLACK_WEBHOOK,
        telegram_token=TG_TOKEN,
        telegram_chat_id=TG_CHAT,
    )

    if EXPORT_EXCEL:
        destination = (
            Path(EXPORT_EXCEL_OUT).expanduser()
            if EXPORT_EXCEL_OUT
            else REPORT_DIR / "auto_results.xlsx"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        export_strategy_results(
            method="auto",
            prom_url=PROM_URL,
            window_minutes=EXPORT_EXCEL_WINDOW,
            metrics=EXPORT_EXCEL_METRICS,
            out_path=destination,
        )


# =====================================================================
# Main entrypoint
# =====================================================================
def main(argv: Sequence[str] | None = None) -> int:  # noqa: ARG001 - argparse not used yet
    # تهيئة ملفات السجل ثم تشغيل الدورة الواحدة أو الحلقات المتكررة
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
