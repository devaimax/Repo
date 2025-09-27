import datetime as dt
from pathlib import Path

try:
    from fpdf import FPDF  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    FPDF = None  # type: ignore


def generate_pdf(report_dir: Path, plot_dir: Path) -> None:
    """Render a PDF report embedding any generated plots."""

    if FPDF is None:
        print("⚠️ PDF generation skipped: FPDF not available")
        return

    report_dir.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, f"Auto Scheduler Report - {dt.date.today()}", ln=True, align="C")

    distribution = plot_dir / "distribution.png"
    weights = plot_dir / "weights.png"

    if distribution.exists():
        pdf.image(str(distribution), w=180)
    if weights.exists():
        pdf.image(str(weights), w=180)

    pdf.output(report_dir / f"report_{dt.date.today()}.pdf")
