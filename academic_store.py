"""Plug-and-play SQLite store for normalized academic records.

The demo CSV seeds the database on first use. A Moodle importer can later
upsert the same normalized fields without changing the agent or MCP layers.
"""
from __future__ import annotations

import csv
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = Path(os.getenv("STUDENT_DB_CSV_PATH", BASE_DIR / "data" / "students.csv"))
DB_PATH = Path(os.getenv("ACADEMIC_SQLITE_PATH", BASE_DIR / "data" / "academic.sqlite"))
EXTERNAL_SQLITE = bool(os.getenv("ACADEMIC_SQLITE_PATH"))


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_database() -> Path:
    """Return an attached SQLite database, or seed the bundled demo database."""
    # An explicitly configured database is authoritative.  This keeps a
    # Moodle import from being replaced by the bundled demonstration CSV.
    if EXTERNAL_SQLITE and DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as conn:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='student_records'"
            ).fetchone()
        if exists:
            return DB_PATH
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Academic source not found: {CSV_PATH}")
    if DB_PATH.exists() and DB_PATH.stat().st_mtime >= CSV_PATH.stat().st_mtime:
        return DB_PATH
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as source:
        rows = list(csv.DictReader(source))
        headers = source and list(rows[0].keys()) if rows else []
    if not headers:
        raise ValueError("Academic source has no records.")
    columns = ", ".join(f'"{name}" TEXT' for name in headers)
    quoted = ", ".join(f'"{name}"' for name in headers)
    marks = ", ".join("?" for _ in headers)
    with _connect() as conn:
        conn.execute("DROP TABLE IF EXISTS student_records")
        conn.execute(f"CREATE TABLE student_records ({columns})")
        conn.executemany(
            f"INSERT INTO student_records ({quoted}) VALUES ({marks})",
            [[row.get(header, "") for header in headers] for row in rows],
        )
        conn.execute('CREATE INDEX idx_student_records_id ON student_records("student_id")')
    return DB_PATH


def fetch_records() -> list[dict[str, str]]:
    ensure_database()
    with _connect() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM student_records").fetchall()]


def database_status() -> dict[str, object]:
    path = ensure_database()
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM student_records").fetchone()[0]
    return {
        "engine": "sqlite",
        "path": str(path),
        "records": count,
        "source": "external_sqlite" if EXTERNAL_SQLITE else "bundled_demo_csv",
    }


def source_label() -> str:
    """Human-readable source name for answers and export metadata."""
    return "Moodle SQL import" if EXTERNAL_SQLITE else "Bundled demonstration data"
