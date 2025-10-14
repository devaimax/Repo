import csv
import datetime as dt
import sqlite3
from pathlib import Path
from typing import Iterable, Tuple


LOG_HEADERS: Tuple[str, ...] = (
    "timestamp",
    "service",
    "node",
    "cpu_weight",
    "mem_weight",
    "node_score",
    "reason",
)


def init_logs(csv_path: Path, db_path: Path) -> None:
    """Ensure CSV/SQLite destinations exist with the expected schema."""

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    rows_to_preserve = []
    needs_header = True
    if csv_path.exists():
        try:
            with csv_path.open("r", newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
        except (csv.Error, UnicodeDecodeError):
            rows = []
        if rows and list(rows[0]) == list(LOG_HEADERS):
            needs_header = False
        else:
            rows_to_preserve = rows
    if needs_header:
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(LOG_HEADERS)
            for row in rows_to_preserve:
                writer.writerow(row)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            timestamp TEXT,
            service TEXT,
            node TEXT,
            cpu_weight REAL,
            mem_weight REAL,
            node_score REAL,
            reason TEXT
        )
        """
    )
    conn.close()


def append_log(
    csv_path: Path,
    db_path: Path,
    service: str,
    node: str,
    cpu_weight: float,
    mem_weight: float,
    score: float,
    reason: str,
) -> None:
    """Append a scheduler decision to CSV and SQLite destinations."""

    timestamp = dt.datetime.now().isoformat()

    with csv_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                timestamp,
                service,
                node,
                f"{cpu_weight:.2f}",
                f"{mem_weight:.2f}",
                f"{score:.2f}",
                reason,
            ]
        )

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO logs VALUES (?,?,?,?,?,?,?)",
            (timestamp, service, node, cpu_weight, mem_weight, score, reason),
        )
        conn.commit()
    finally:
        conn.close()
