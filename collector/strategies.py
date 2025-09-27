from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple


@dataclass
class NodeMetrics:
    name: str  # Typically the node IP address
    cpu_usage_percent: float
    memory_usage_percent: float
    hostname: str | None = None

    def clamp(self) -> "NodeMetrics":
        return NodeMetrics(
            name=self.name,
            cpu_usage_percent=min(max(self.cpu_usage_percent, 0.0), 100.0),
            memory_usage_percent=min(max(self.memory_usage_percent, 0.0), 100.0),
            hostname=self.hostname,
        )


def auto_weights(nodes: Sequence[NodeMetrics]) -> Tuple[float, float, float, float]:
    """Derive CPU/MEM weights from current utilisation averages."""

    if not nodes:
        return 0.5, 0.5, 0.0, 0.0

    avg_cpu = sum(node.cpu_usage_percent for node in nodes) / len(nodes)
    avg_mem = sum(node.memory_usage_percent for node in nodes) / len(nodes)

    cpu_weight = 1 / max(avg_cpu, 1e-6)
    mem_weight = 1 / max(avg_mem, 1e-6)

    total = cpu_weight + mem_weight
    return cpu_weight / total, mem_weight / total, avg_cpu, avg_mem


def compute_score(node: NodeMetrics, cpu_weight: float, mem_weight: float) -> float:
    clamped = node.clamp()
    available_cpu = 100.0 - clamped.cpu_usage_percent
    available_mem = 100.0 - clamped.memory_usage_percent
    return (cpu_weight * available_cpu) + (mem_weight * available_mem)


def rank_nodes(nodes: Sequence[NodeMetrics], cpu_weight: float, mem_weight: float) -> List[tuple[NodeMetrics, float]]:
    return sorted(
        ((node, compute_score(node, cpu_weight, mem_weight)) for node in nodes),
        key=lambda item: item[1],
        reverse=True,
    )


def distribute_weighted(services: Sequence[str], ranked_nodes: Sequence[tuple[NodeMetrics, float]]) -> List[tuple[str, NodeMetrics]]:
    total_score = sum(score for _, score in ranked_nodes)
    allocation: List[tuple[NodeMetrics, int]] = []
    remaining = len(services)

    for node, score in ranked_nodes:
        share = int(round((score / total_score) * len(services))) if total_score > 0 else 0
        allocation.append((node, share))
        remaining -= share

    index = 0
    while remaining > 0 and allocation:
        node, share = allocation[index]
        allocation[index] = (node, share + 1)
        remaining -= 1
        index = (index + 1) % len(allocation)

    assignments: List[tuple[str, NodeMetrics]] = []
    service_index = 0
    for node, count in allocation:
        for _ in range(count):
            if service_index >= len(services):
                break
            assignments.append((services[service_index], node))
            service_index += 1

    return assignments


def distribute_round_robin(services: Sequence[str], ranked_nodes: Sequence[tuple[NodeMetrics, float]]) -> List[tuple[str, NodeMetrics]]:
    assignments: List[tuple[str, NodeMetrics]] = []
    if not ranked_nodes:
        return assignments
    for idx, service in enumerate(services):
        node = ranked_nodes[idx % len(ranked_nodes)][0]
        assignments.append((service, node))
    return assignments


def distribute_least_loaded(services: Sequence[str], ranked_nodes: Sequence[tuple[NodeMetrics, float]]) -> List[tuple[str, NodeMetrics]]:
    if not ranked_nodes:
        return []

    least_loaded_node = min(ranked_nodes, key=lambda item: item[0].cpu_usage_percent)[0]
    return [(service, least_loaded_node) for service in services]
