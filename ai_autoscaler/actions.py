"""Cluster actions executed by the autoscaler."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from .config import AutoscalerConfig
from .state import NodeObservation


@dataclass
class ActionOutcome:
    action: str
    details: str
    success: bool


class ClusterActions:
    def __init__(self, config: AutoscalerConfig) -> None:
        self.config = config

    def _docker(self, *args: str) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                ["docker", *args],
                check=True,
                capture_output=True,
                text=True,
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            return False, exc.stderr.strip()

    def migrate_services(self, overloaded: NodeObservation, target: NodeObservation) -> ActionOutcome:
        commands: List[Tuple[str, Tuple[str, ...]]] = []
        for service in overloaded.running_services:
            commands.append(
                (
                    f"Pin {service} to {target.hostname}",
                    (
                        "service",
                        "update",
                        "--constraint-add",
                        f"node.hostname=={target.hostname}",
                        service,
                    ),
                )
            )
        for description, cmd in commands:
            ok, message = self._docker(*cmd)
            if not ok:
                return ActionOutcome("rebalance", f"{description}: {message}", False)
        return ActionOutcome(
            "rebalance",
            f"Migrated {len(commands)} services from {overloaded.hostname} to {target.hostname}",
            True,
        )

    def power_on_node(self, node_name: str) -> ActionOutcome:
        # Placeholder hook for ESXi integration
        # TODO: Implement actual ESXi API calls
        return ActionOutcome("power_on", f"Requested power on for {node_name}", True)

    def power_off_node(self, node_name: str) -> ActionOutcome:
        # Placeholder hook for ESXi integration
        # TODO: Implement actual ESXi API calls
        return ActionOutcome("power_off", f"Requested power off for {node_name}", True)

    def execute(self, action: str, observations: Iterable[NodeObservation]) -> ActionOutcome:
        overloaded = sorted(
            observations,
            key=lambda obs: (obs.load_score if obs.load_score == obs.load_score else 0.0),
            reverse=True,
        )
        idle = [obs for obs in observations if obs.load_score < self.config.idle_threshold]
        high = [obs for obs in observations if obs.load_score >= self.config.load_threshold]

        if action == "rebalance" and high and idle:
            return self.migrate_services(high[0], idle[0])
        if action == "power_on":
            candidate = self._next_available_node()
            if candidate:
                return self.power_on_node(candidate)
            return ActionOutcome("power_on", "No standby nodes configured", False)
        if action == "power_off" and idle:
            return self.power_off_node(idle[0].hostname)
        return ActionOutcome(action, "No operation performed", True)

    def _next_available_node(self) -> str | None:
        # Placeholder for integration with inventory/ESXi
        return None
