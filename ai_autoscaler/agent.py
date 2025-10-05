"""Tabular reinforcement-learning agent for autoscaler decisions."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, Tuple

import numpy as np

from .config import AutoscalerConfig

StateKey = Tuple[int, int, int]  # (high_nodes, normal_nodes, idle_nodes)
Action = str

ACTIONS: Tuple[Action, ...] = (
    "noop",
    "rebalance",
    "power_on",
    "power_off",
)


@dataclass
class RLAgent:
    config: AutoscalerConfig
    q_table: Dict[StateKey, np.ndarray] = field(default_factory=dict)

    def discretise(self, high: int, normal: int, idle: int) -> StateKey:
        return (min(high, 9), min(normal, 9), min(idle, 9))

    def ensure_state(self, state: StateKey) -> None:
        if state not in self.q_table:
            self.q_table[state] = np.zeros(len(ACTIONS), dtype=float)

    def select_action(self, state: StateKey) -> Action:
        self.ensure_state(state)
        if random.random() < self.config.epsilon:
            return random.choice(ACTIONS)
        values = self.q_table[state]
        return ACTIONS[int(values.argmax())]

    def update(self, state: StateKey, action: Action, reward: float, next_state: StateKey) -> None:
        self.ensure_state(state)
        self.ensure_state(next_state)
        idx = ACTIONS.index(action)
        best_next = self.q_table[next_state].max()
        current = self.q_table[state][idx]
        target = reward + self.config.gamma * best_next
        self.q_table[state][idx] = current + self.config.alpha * (target - current)

    def dump(self) -> Dict[str, Dict[str, float]]:
        return {
            str(state): {action: float(values[i]) for i, action in enumerate(ACTIONS)}
            for state, values in self.q_table.items()
        }
