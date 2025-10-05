"""Static configuration defaults for the AI autoscaler."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

DEFAULT_PROM_URL = "http://localhost:9090"
DEFAULT_PROM_TIMEOUT = 5  # seconds
DEFAULT_SCRAPE_INTERVAL = 30  # seconds between observations
DEFAULT_NODE_LABEL_FILTER = ""
DEFAULT_LOG_DIR = Path("logs/ai_autoscaler")
DEFAULT_RESULTS_DIR = Path("reports/ai_autoscaler")
DEFAULT_METRICS = (
    "node_cpu_seconds_total",
    "node_memory_MemAvailable_bytes",
    "node_memory_MemTotal_bytes",
    "factorial_execution_time_seconds",
    "matrix_multiplication_time_seconds",
)

# Reinforcement learning hyperparameters
DEFAULT_GAMMA = 0.9
DEFAULT_ALPHA = 0.1
DEFAULT_EPSILON = 0.1
DEFAULT_REWARD_SCALE = 1.0
DEFAULT_LOAD_THRESHOLD = 0.75  # >75% utilisation triggers remediation
DEFAULT_IDLE_THRESHOLD = 0.25  # <25% utilisation counts as idle
DEFAULT_MIN_SAMPLES = 3  # require this many observations before acting


@dataclass(frozen=True)
class AutoscalerConfig:
    prom_url: str = DEFAULT_PROM_URL
    prom_timeout: int = DEFAULT_PROM_TIMEOUT
    scrape_interval: int = DEFAULT_SCRAPE_INTERVAL
    node_label_filter: str = DEFAULT_NODE_LABEL_FILTER
    log_dir: Path = DEFAULT_LOG_DIR
    results_dir: Path = DEFAULT_RESULTS_DIR
    metrics: Tuple[str, ...] = DEFAULT_METRICS
    gamma: float = DEFAULT_GAMMA
    alpha: float = DEFAULT_ALPHA
    epsilon: float = DEFAULT_EPSILON
    reward_scale: float = DEFAULT_REWARD_SCALE
    load_threshold: float = DEFAULT_LOAD_THRESHOLD
    idle_threshold: float = DEFAULT_IDLE_THRESHOLD
    min_samples: int = DEFAULT_MIN_SAMPLES

    def ensure_dirs(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
