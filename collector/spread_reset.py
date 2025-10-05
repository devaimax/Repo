"""Reset Swarm services so that the default Spread strategy can rebalance them.

The script removes node.hostname constraints for the selected services, optionally
forces a rolling update, and finally prints the placement of each replica. This
makes it easy to record a clean baseline before applying weighted scheduling.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import List
import json

if __package__ is None or __package__ == "":  # pragma: no cover - script execution
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from collector.result_exporter import export_strategy_results, DEFAULT_METRICS  # type: ignore
else:  # pragma: no cover - normal package import
    from .result_exporter import export_strategy_results, DEFAULT_METRICS

DEFAULT_PATTERNS = [
    "fact_100k",
    "fact_300k",
    "fact_500k",
    "matrix_4k",
    "matrix_5k",
]


def list_services() -> List[str]:
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
    available = list_services()
    if not available:
        return []

    patterns = patterns or DEFAULT_PATTERNS
    resolved: List[str] = []
    for pattern in patterns:
        matches = [svc for svc in available if pattern in svc]
        if matches:
            resolved.extend(matches)
        elif pattern in available:
            resolved.append(pattern)
    return sorted(set(resolved))


def known_hostnames() -> List[str]:
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



def clear_constraints(service: str, hosts: List[str]) -> None:
    for host in hosts:
        subprocess.run(
            [
                "docker",
                "service",
                "update",
                "--constraint-rm",
                f"node.hostname=={host}",
                service,
            ],
            check=False,
        )
    for constraint in hostname_constraints(service):
        subprocess.run(
            [
                "docker",
                "service",
                "update",
                "--constraint-rm",
                constraint,
                service,
            ],
            check=False,
        )


def describe_distribution(service: str) -> None:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset services to the Spread baseline")
    parser.add_argument("--services", nargs="+", default=None, help="Service name patterns to reset")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Trigger a rolling update after clearing constraints",
    )
    parser.add_argument(
        "--export-excel",
        action="store_true",
        help="Export Prometheus samples after reset into reports/spread_results.xlsx",
    )
    parser.add_argument(
        "--prom-url",
        default="http://localhost:9090",
        help="Prometheus base URL for the optional export",
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
        help="Custom Excel path (default: reports/spread_results.xlsx)",
    )
    args = parser.parse_args()

    services = resolve_services(args.services)
    if not services:
        print("⚠️ No services matched the provided patterns; nothing to reset.")
        return 0

    hosts = known_hostnames()
    print(f"🔁 Resetting {len(services)} services to the Spread strategy...")
    for service in services:
        clear_constraints(service, hosts)
        if args.force:
            subprocess.run(
                ["docker", "service", "update", "--force", service],
                check=False,
            )
        describe_distribution(service)

    if args.export_excel:
        metrics = args.export_metrics or DEFAULT_METRICS
        out_path = Path(args.export_out) if args.export_out else Path("reports") / "spread_results.xlsx"
        export_strategy_results(
            method="spread",
            prom_url=args.prom_url,
            window_minutes=args.export_window,
            metrics=metrics,
            out_path=out_path,
        )

    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
