import datetime as dt
import time
from pathlib import Path
from typing import Mapping, Optional

try:
    from fpdf import FPDF  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    FPDF = None  # type: ignore


def generate_pdf(
    report_dir: Path,
    plot_dir: Path,
    plot_paths: Optional[Mapping[str, Path]] = None,
) -> None:
    """Render a PDF report embedding any generated plots."""

    if FPDF is None:
        print("⚠️ PDF generation skipped: FPDF not available")
        return

    report_dir.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, f"Auto Scheduler Report - {dt.date.today()}", ln=True, align="C")

    distribution = None
    weights = None
    if plot_paths:
        distribution = plot_paths.get("distribution")
        weights = plot_paths.get("weights")

    if distribution is None:
        distribution = plot_dir / "distribution.png"
    if weights is None:
        weights = plot_dir / "weights.png"

    if distribution.exists():
        pdf.image(str(distribution), w=180)
    if weights.exists():
        pdf.image(str(weights), w=180)

    report_path = report_dir / f"report_{dt.date.today()}.pdf"
    try:
        report_path.unlink(missing_ok=True)
    except PermissionError as exc:
        alt_name = f"{report_path.stem}_{int(time.time())}{report_path.suffix}"
        alt_path = report_dir / alt_name
        print(
            f"⚠️ Unable to overwrite existing report {report_path} ({exc}); "
            f"writing to {alt_path.name} instead"
        )
        report_path = alt_path

    pdf.output(str(report_path))
