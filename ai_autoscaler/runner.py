"""Main training loop for the autoscaler."""

from __future__ import annotations

import math
import time
from typing import Iterable, Tuple

from .actions import ClusterActions
from .agent import ACTIONS, RLAgent
from .config import AutoscalerConfig
from .logger import AutoscalerLogger
from .state import NodeObservation, StateCollector


def classify_nodes(config: AutoscalerConfig, observations: Iterable[NodeObservation]) -> Tuple[int, int, int]:
    high = normal = idle = 0
    for obs in observations:
        load = obs.load_score if not math.isnan(obs.load_score) else 0.0
        if load >= config.load_threshold:
            high += 1
        elif load <= config.idle_threshold:
            idle += 1
        else:
            normal += 1
    return high, normal, idle


def compute_reward(config: AutoscalerConfig, observations: Iterable[NodeObservation]) -> float:
    penalty = 0.0
    bonus = 0.0
    for obs in observations:
        load = obs.load_score if not math.isnan(obs.load_score) else 0.0
        if load >= config.load_threshold:
            penalty += load - config.load_threshold
        elif load <= config.idle_threshold:
            bonus += config.idle_threshold - load
    return (bonus - penalty) * config.reward_scale


def run_loop(config: AutoscalerConfig, stop_after: int | None = None) -> None:
    collector = StateCollector(config)
    agent = RLAgent(config)
    actions = ClusterActions(config)
    logger = AutoscalerLogger(config)

    iteration = 0
    while stop_after is None or iteration < stop_after:
        observations = collector.collect()
        if not observations:
            time.sleep(config.scrape_interval)
            continue

        state_tuple = classify_nodes(config, observations)
        state = agent.discretise(*state_tuple)
        if sum(state_tuple) < config.min_samples:
            time.sleep(config.scrape_interval)
            iteration += 1
            continue

        action = agent.select_action(state)
        outcome = actions.execute(action, observations)

        time.sleep(2)  # allow cluster to settle for reward computation
        post_observations = collector.collect()
        reward = compute_reward(config, post_observations)
        next_state = agent.discretise(*classify_nodes(config, post_observations))

        agent.update(state, action, reward, next_state)
        logger.log_event(time.time(), action, outcome.success, reward, outcome.details, state)
        logger.dump_q_table(agent)

        time.sleep(config.scrape_interval)
        iteration += 1
