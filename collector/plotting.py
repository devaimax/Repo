from pathlib import Path

import pandas as pd

try:
    import matplotlib.pyplot as plt  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    plt = None  # type: ignore


def generate_plots(csv_path: Path, plot_dir: Path) -> None:
    """Produce PNG plots from the scheduler log if matplotlib is available."""

    if plt is None:
        print("⚠️ Plotting skipped: matplotlib not available")
        return

    try:
        df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    except FileNotFoundError:
        print(f"⚠️ Plotting skipped: log file {csv_path} not found")
        return

    if df.empty:
        print("⚠️ Plotting skipped: log CSV empty")
        return

    plot_dir.mkdir(parents=True, exist_ok=True)

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
        plt.savefig(plot_dir / "distribution.png", bbox_inches="tight")
        plt.close()

    weight_df = (
        df[["timestamp", "cpu_weight", "mem_weight"]]
        .drop_duplicates()
        .set_index("timestamp")
    )
    if not weight_df.empty:
        weight_df.plot()
        plt.title("CPU/MEM Weights Over Time")
        plt.ylabel("Weight")
        plt.savefig(plot_dir / "weights.png", bbox_inches="tight")
        plt.close()
