"""SQLite storage for historical analytics data."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "analytics.db"


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS data_pulls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_timestamp TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            source TEXT NOT NULL,
            data_type TEXT NOT NULL,
            data TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_source_type_period
        ON data_pulls(source, data_type, period_start, period_end)
    """)
    conn.commit()
    conn.close()


def store_pull(source: str, data_type: str, period_start, period_end, data):
    conn = _connect()
    conn.execute(
        "INSERT INTO data_pulls (pull_timestamp, period_start, period_end, source, data_type, data) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), str(period_start), str(period_end), source, data_type, json.dumps(data)),
    )
    conn.commit()
    conn.close()


def get_latest_pull(source: str, data_type: str, period_start, period_end):
    conn = _connect()
    row = conn.execute(
        "SELECT data, pull_timestamp FROM data_pulls WHERE source=? AND data_type=? AND period_start=? AND period_end=? ORDER BY pull_timestamp DESC LIMIT 1",
        (source, data_type, str(period_start), str(period_end)),
    ).fetchone()
    conn.close()
    if row:
        return json.loads(row["data"]), row["pull_timestamp"]
    return None, None


def has_data(source: str, data_type: str, period_start, period_end) -> bool:
    data, _ = get_latest_pull(source, data_type, period_start, period_end)
    return data is not None


def get_all_pull_dates() -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT DISTINCT pull_timestamp, period_start, period_end, source FROM data_pulls ORDER BY pull_timestamp DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Initialize on import
init_db()
