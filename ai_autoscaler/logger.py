"""Logging utilities for the autoscaler."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .config import AutoscalerConfig
from .state import NodeObservation
from .agent import ACTIONS, RLAgent


class AutoscalerLogger:
    def __init__(self, config: AutoscalerConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.events_csv = self.config.log_dir / "events.csv"
        self.qtable_json = self.config.log_dir / "q_table.json"
        if not self.events_csv.exists():
            with self.events_csv.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "timestamp",
                        "action",
                        "result",
                        "reward",
                        "details",
                        "state_high",
                        "state_normal",
                        "state_idle",
                    ]
                )

    def log_event(
        self,
        timestamp: float,
        action: str,
        result: bool,
        reward: float,
        details: str,
        state_key: tuple[int, int, int],
    ) -> None:
        with self.events_csv.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([timestamp, action, int(result), reward, details, *state_key])

    def dump_q_table(self, agent: RLAgent) -> None:
        data = agent.dump()
        self.qtable_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
