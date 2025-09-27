"""Manual weighting algorithm from the weighted resource optimization paper.

This module implements the node scoring approach described in
"Docker Container Placement in Docker Swarm Cluster by Using Weighted Resource
Optimization Approach" (Ramavat & Patel, 2024).

Example usage:

    python manual_weight_scheduler.py \
        --cpu-weight 0.7 --mem-weight 0.3 \
        --node manager,35,42 \
        --node worker-1,55,40 \
        --node worker-2,20,65

or by loading node metrics from a CSV file with headers
``node,cpu_usage_percent,memory_usage_percent``:

    python manual_weight_scheduler.py --cpu-weight 0.6 --mem-weight 0.4 \
        --nodes-csv node_metrics.csv
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


@dataclass
class NodeMetrics:
    """Container for per-node utilisation percentages."""

    name: str
    cpu_usage_percent: float
    memory_usage_percent: float

    def clamp(self) -> "NodeMetrics":
        """Return a copy with utilisation constrained to [0, 100]."""

        return NodeMetrics(
            name=self.name,
            cpu_usage_percent=min(max(self.cpu_usage_percent, 0.0), 100.0),
            memory_usage_percent=min(max(self.memory_usage_percent, 0.0), 100.0),
        )


def compute_score(node: NodeMetrics, cpu_weight: float, mem_weight: float) -> float:
    """Compute the weighted availability score for a node."""

    clamped = node.clamp()
    available_cpu = 100.0 - clamped.cpu_usage_percent
    available_mem = 100.0 - clamped.memory_usage_percent
    return (cpu_weight * available_cpu) + (mem_weight * available_mem)


def rank_nodes(nodes: Sequence[NodeMetrics], cpu_weight: float, mem_weight: float) -> List[tuple[NodeMetrics, float]]:
    """Return nodes sorted by score descending."""

    scored = [(node, compute_score(node, cpu_weight, mem_weight)) for node in nodes]
    return sorted(scored, key=lambda item: item[1], reverse=True)


def select_best_node(nodes: Sequence[NodeMetrics], cpu_weight: float, mem_weight: float) -> tuple[NodeMetrics, float]:
    """Return the node with the highest weighted availability score."""

    ranked = rank_nodes(nodes, cpu_weight, mem_weight)
    if not ranked:
        raise ValueError("No nodes provided")
    return ranked[0]


def parse_nodes_csv(path: Path) -> List[NodeMetrics]:
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
    return parser


def load_nodes(args: argparse.Namespace) -> List[NodeMetrics]:
    """Load nodes from CSV and/or --node arguments."""

    nodes: List[NodeMetrics] = []
    if args.nodes_csv:
        nodes.extend(parse_nodes_csv(args.nodes_csv))
    if args.node:
        nodes.extend(parse_node_arguments(args.node))
    # Deduplicate by name keeping last occurrence to allow overrides.
    unique: dict[str, NodeMetrics] = {node.name: node for node in nodes}
    return list(unique.values())


def format_table(rows: Sequence[tuple[NodeMetrics, float]]) -> str:
    """Return a simple table of node scores."""

    header = f"{'Node':<20} {'CPU%':>8} {'MEM%':>8} {'Score':>10}"
    lines = [header]
    for node, score in rows:
        lines.append(
            f"{node.name:<20} "
            f"{node.cpu_usage_percent:8.2f} "
            f"{node.memory_usage_percent:8.2f} "
            f"{score:10.2f}"
        )
    return "\n".join(lines)


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

    if not nodes:
        parser.error("No nodes provided. Use --nodes-csv or --node.")

    ranked = rank_nodes(nodes, cpu_weight, mem_weight)
    top_n = args.top if args.top and args.top > 0 else len(ranked)
    output = format_table(ranked[:top_n])
    print(output)

    best_node, best_score = ranked[0]
    print(
        "\nSelected node:",
        f"{best_node.name} (score={best_score:.2f}, cpu={best_node.cpu_usage_percent:.2f}%, mem={best_node.memory_usage_percent:.2f}%)",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
