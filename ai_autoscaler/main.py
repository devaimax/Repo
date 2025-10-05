"""Command-line entrypoint for the AI autoscaler."""

from __future__ import annotations

import argparse

from .config import AutoscalerConfig
from .runner import run_loop


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI autoscaler for Docker Swarm clusters")
    parser.add_argument("--prom-url", default="http://localhost:9090", help="Prometheus base URL")
    parser.add_argument("--interval", type=int, default=30, help="Scrape interval in seconds")
    parser.add_argument(
        "--epsilon",
        type=float,
        default=0.1,
        help="Exploration probability (epsilon-greedy)",
    )
    parser.add_argument("--gamma", type=float, default=0.9, help="Reward discount factor")
    parser.add_argument("--alpha", type=float, default=0.1, help="Learning rate")
    parser.add_argument("--reward-scale", type=float, default=1.0, help="Reward scaling factor")
    parser.add_argument(
        "--load-threshold",
        type=float,
        default=0.75,
        help="Utilisation threshold considered overloaded (0-1)",
    )
    parser.add_argument(
        "--idle-threshold",
        type=float,
        default=0.25,
        help="Utilisation threshold considered idle (0-1)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=3,
        help="Minimum number of nodes observed before acting",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Stop after this many iterations (default: run forever)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = AutoscalerConfig(
        prom_url=args.prom_url,
        scrape_interval=args.interval,
        epsilon=args.epsilon,
        gamma=args.gamma,
        alpha=args.alpha,
        reward_scale=args.reward_scale,
        load_threshold=args.load_threshold,
        idle_threshold=args.idle_threshold,
        min_samples=args.min_samples,
    )
    config.ensure_dirs()
    run_loop(config, stop_after=args.iterations)


if __name__ == "__main__":
    main()
