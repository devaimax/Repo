from pathlib import Path
from typing import Dict

import pandas as pd
import time

try:
    import matplotlib.pyplot as plt  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    plt = None  # type: ignore


def _prepare_target(plot_dir: Path, filename: str) -> Path:
    """Return a writable path for the plot, handling non-writable leftovers."""

    plot_dir.mkdir(parents=True, exist_ok=True)
    target = plot_dir / filename
    try:
        target.unlink(missing_ok=True)
    except PermissionError as exc:
        alt_name = f"{target.stem}_{int(time.time())}{target.suffix}"
        alt_target = plot_dir / alt_name
        print(
            f"⚠️ Unable to overwrite existing plot {target} ({exc}); "
            f"writing to {alt_target.name} instead"
        )
        target = alt_target
    return target


def generate_plots(csv_path: Path, plot_dir: Path) -> Dict[str, Path]:
    """Produce PNG plots from the scheduler log if matplotlib is available."""

    if plt is None:
        print("⚠️ Plotting skipped: matplotlib not available")
        return {}

    try:
        df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    except FileNotFoundError:
        print(f"⚠️ Plotting skipped: log file {csv_path} not found")
        return {}

    if df.empty:
        print("⚠️ Plotting skipped: log CSV empty")
        return {}

    generated: Dict[str, Path] = {}

    pivot = (
        df.pivot_table(
            index="timestamp",
            columns="node",
            values="service",
            aggfunc="count",
        ).fillna(0)
    )
    if not pivot.empty:
        pivot.plot(kind="bar", stacked=True)
        plt.title("Service Distribution Over Time")
        plt.ylabel("Services")
        distribution_path = _prepare_target(plot_dir, "distribution.png")
        plt.savefig(distribution_path, bbox_inches="tight")
        plt.close()
        generated["distribution"] = distribution_path

    weight_df = (
        df[["timestamp", "cpu_weight", "mem_weight"]]
        .drop_duplicates()
        .set_index("timestamp")
    )
    if not weight_df.empty:
        weight_df.plot()
        plt.title("CPU/MEM Weights Over Time")
        plt.ylabel("Weight")
        weights_path = _prepare_target(plot_dir, "weights.png")
        plt.savefig(weights_path, bbox_inches="tight")
        plt.close()
        generated["weights"] = weights_path

    return generated
