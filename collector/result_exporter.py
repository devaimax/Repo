"""Shared helpers for exporting Prometheus samples into Excel workbooks."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Iterable

import importlib
import math
from xml.sax.saxutils import escape
from zipfile import ZipFile

import pandas as pd
from prometheus_api_client import PrometheusConnect

if __package__ is None or __package__ == "":  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from collector.cache import load_json, store_json  # type: ignore
else:  # pragma: no cover
    from .cache import load_json, store_json


DEFAULT_METRICS = (
    "factorial_execution_time_seconds",
    "matrix_multiplication_time_seconds",
)

SAMPLES_CACHE_FILE = Path("excel_samples.json")


def _collect_samples(prom: PrometheusConnect, metrics: Iterable[str], minutes: int) -> pd.DataFrame:
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(minutes=minutes)

    rows = []
    for metric in metrics:
        try:
            data = prom.custom_query_range(
                query=metric,
                start_time=start,
                end_time=end,
                step="30s",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"❌ Error fetching {metric}: {exc}")
            continue

        if not data:
            print(f"⚠️ No series returned for {metric} in the selected window.")
            continue

        for series in data:
            labels = series["metric"]
            for ts, val in series["values"]:
                try:
                    completed_at = dt.datetime.fromtimestamp(float(ts), tz=dt.timezone.utc)
                    duration = float(val)
                    service_label = labels.get("service_name", "unknown")
                    service_type = (
                        "factorial"
                        if "factorial" in metric
                        else "matrix"
                        if "matrix" in metric
                        else "other"
                    )
                    container = (
                        labels.get("container_id")
                        or labels.get("container")
                        or labels.get("pod")
                        or "unknown"
                    )
                    node = labels.get("node_name") or labels.get("instance") or "unknown"
                    task = labels.get("task") or labels.get("swarm_task") or "unknown"

                    rows.append(
                        {
                            "metric": metric,
                            "service": service_label,
                            "service_type": service_type,
                            "node": node,
                            "container": container,
                            "task": task,
                            "job": labels.get("job", "unknown"),
                            "instance": labels.get("instance", "unknown"),
                            "address": labels.get("__address__", labels.get("instance", "unknown")),
                            "duration_seconds": duration,
                            "completed_at": completed_at,
                            "started_at": completed_at - dt.timedelta(seconds=duration),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"⚠️ Skipped invalid sample for {metric}: {exc}")
                    continue

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["duration_seconds"] = df["duration_seconds"].astype(float)
    df["completed_at"] = pd.to_datetime(df["completed_at"], utc=True)
    df["started_at"] = pd.to_datetime(df["started_at"], utc=True)
    df.sort_values("completed_at", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def _safe_sheet_name(name: str) -> str:
    cleaned = "".join("_" if ch in '[]:*?/\\' else ch for ch in name)
    cleaned = cleaned.strip() or "Sheet"
    return cleaned[:31]


def _excel_column(col_idx: int) -> str:
    result = ""
    while col_idx > 0:
        col_idx, rem = divmod(col_idx - 1, 26)
        result = chr(65 + rem) + result
    return result


def _format_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def _build_sheet_xml(rows: list[list[str]]) -> str:
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<worksheet xmlns="{ns}">',
        "<sheetData>",
    ]
    for r_idx, row in enumerate(rows, start=1):
        cells: list[str] = []
        for c_idx, value in enumerate(row, start=1):
            cell_ref = f"{_excel_column(c_idx)}{r_idx}"
            text = escape(value)
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{text}</t></is></c>'
            )
        parts.append(f"<row r=\"{r_idx}\">{''.join(cells)}</row>")
    parts.append("</sheetData>")
    parts.append("</worksheet>")
    return "".join(parts)


def _write_minimal_xlsx(destination: Path, sheets: list[tuple[str, pd.DataFrame]]) -> None:
    timestamp = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    normalized: list[tuple[int, str, list[list[str]]]] = []
    for idx, (name, df) in enumerate(sheets, start=1):
        safe_name = _safe_sheet_name(name)
        data_rows: list[list[str]] = []
        data_rows.append([_format_cell(col) for col in df.columns])
        for _, row in df.iterrows():
            data_rows.append([_format_cell(row[col]) for col in df.columns])
        normalized.append((idx, safe_name, data_rows))

    sheet_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{idx}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for idx, _, _ in normalized
    )

    content_types = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>"
        "<Override PartName=\"/xl/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/>"
        "<Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/>"
        "<Override PartName=\"/docProps/app.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.extended-properties+xml\"/>"
        f"{sheet_overrides}" "</Types>"
    )

    root_rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/>"
        "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties\" Target=\"docProps/core.xml\"/>"
        "<Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties\" Target=\"docProps/app.xml\"/>"
        "</Relationships>"
    )

    sheets_xml = "".join(
        f'<sheet name="{escape(name)}" sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, name, _ in normalized
    )
    workbook_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
        f"<sheets>{sheets_xml}</sheets></workbook>"
    )

    rels_entries = []
    for idx, _, _ in normalized:
        rels_entries.append(
            f'<Relationship Id="rId{idx}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{idx}.xml"/>'
        )
    rels_entries.append(
        f'<Relationship Id="rId{len(normalized)+1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    workbook_rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        f"{''.join(rels_entries)}</Relationships>"
    )

    styles_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<styleSheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
        "<fonts count=\"1\"><font><sz val=\"11\"/><color theme=\"1\"/><name val=\"Calibri\"/><family val=\"2\"/></font></fonts>"
        "<fills count=\"1\"><fill><patternFill patternType=\"none\"/></fill></fills>"
        "<borders count=\"1\"><border><left/><right/><top/><bottom/><diagonal/></border></borders>"
        "<cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs>"
        "<cellXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\" xfId=\"0\"/></cellXfs>"
        "</styleSheet>"
    )

    titles_vector = "".join(f"<vt:lpstr>{escape(name)}</vt:lpstr>" for _, name, _ in normalized)
    app_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\" "
        "xmlns:vt=\"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes\">"
        "<Application>Python</Application>"
        "<HeadingPairs><vt:vector size=\"2\" baseType=\"variant\"><vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant><vt:variant><vt:i4>"
        f"{len(normalized)}</vt:i4></vt:variant></vt:vector></HeadingPairs>"
        f"<TitlesOfParts><vt:vector size=\"{len(normalized)}\" baseType=\"lpstr\">{titles_vector}</vt:vector></TitlesOfParts>"
        "<AppVersion>16.0000</AppVersion></Properties>"
    )

    core_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" "
        "xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:dcterms=\"http://purl.org/dc/terms/\" "
        "xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"
        "<dc:creator>result_exporter</dc:creator><cp:lastModifiedBy>result_exporter</cp:lastModifiedBy>"
        f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{timestamp}</dcterms:created>"
        f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{timestamp}</dcterms:modified>"
        "</cp:coreProperties>"
    )

    with ZipFile(destination, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", styles_xml)
        zf.writestr("docProps/app.xml", app_xml)
        zf.writestr("docProps/core.xml", core_xml)
        for idx, _, rows in normalized:
            sheet_xml = _build_sheet_xml(rows)
            zf.writestr(f"xl/worksheets/sheet{idx}.xml", sheet_xml)


def export_strategy_results(
    method: str,
    prom_url: str,
    window_minutes: int = 10,
    metrics: Iterable[str] | None = None,
    out_path: Path | None = None,
) -> Path | None:
    """Fetch metric samples and write them to an Excel workbook.

    Returns the path to the written workbook, or ``None`` if no samples were found.
    """

    metrics = tuple(metrics or DEFAULT_METRICS)
    prom = PrometheusConnect(url=prom_url, disable_ssl=not prom_url.startswith("https"))

    try:
        df = _collect_samples(prom, metrics, window_minutes)
    except Exception as exc:  # noqa: BLE001
        cached = load_json(SAMPLES_CACHE_FILE)
        if cached:
            print(f"⚠️ Prometheus query failed ({exc}); using cached Excel samples.")
            df = pd.DataFrame(cached)
        else:
            raise

    if df.empty:
        cached = load_json(SAMPLES_CACHE_FILE)
        if cached:
            print("⚠️ No fresh samples; reusing cached dataset for Excel export.")
            df = pd.DataFrame(cached)
        else:
            print("⚠️ No samples retrieved; skipped Excel export.")
            return None
    else:
        store_json(df.to_dict(orient="records"), SAMPLES_CACHE_FILE)

    df.insert(0, "strategy", method)

    destination = out_path or Path("reports") / f"{method}_results.xlsx"
    destination.parent.mkdir(parents=True, exist_ok=True)

    engine = None
    for candidate in ("xlsxwriter", "openpyxl"):
        try:
            importlib.import_module(candidate)
        except ModuleNotFoundError:
            continue
        engine = candidate
        break

    summary = (
        df.groupby(["service", "service_type"], dropna=False)["duration_seconds"]
        .agg(["count", "mean", "std", "min", "max"])
        .reset_index()
    )
    summary.insert(0, "strategy", method)

    if engine is None:
        _write_minimal_xlsx(destination, [
            ("raw_samples", df),
            ("summary", summary),
        ])
    else:
        with pd.ExcelWriter(destination, engine=engine) as writer:
            df.to_excel(writer, index=False, sheet_name="raw_samples")
            summary.to_excel(writer, index=False, sheet_name="summary")

    print(f"📊 Exported {len(df)} samples to {destination}")
    return destination
