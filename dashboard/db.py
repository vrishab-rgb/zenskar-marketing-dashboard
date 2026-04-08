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


# ── Recommendations Log ─────────────────────────────────────

def _init_recommendations():
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_date TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            priority TEXT NOT NULL DEFAULT 'this_week',
            status TEXT NOT NULL DEFAULT 'pending',
            outcome TEXT DEFAULT '',
            updated_date TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_recommendation(recommendation: str, category: str = "general", priority: str = "this_week") -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO recommendations (created_date, recommendation, category, priority, status) VALUES (?, ?, ?, ?, 'pending')",
        (datetime.now().isoformat()[:10], recommendation, category, priority),
    )
    conn.commit()
    rec_id = cur.lastrowid
    conn.close()
    return rec_id


def update_recommendation(rec_id: int, status: str = None, outcome: str = None):
    conn = _connect()
    if status:
        conn.execute("UPDATE recommendations SET status=?, updated_date=? WHERE id=?", (status, datetime.now().isoformat()[:10], rec_id))
    if outcome is not None:
        conn.execute("UPDATE recommendations SET outcome=?, updated_date=? WHERE id=?", (outcome, datetime.now().isoformat()[:10], rec_id))
    conn.commit()
    conn.close()


def delete_recommendation(rec_id: int):
    conn = _connect()
    conn.execute("DELETE FROM recommendations WHERE id=?", (rec_id,))
    conn.commit()
    conn.close()


def get_recommendations(status: str = None) -> list[dict]:
    conn = _connect()
    if status:
        rows = conn.execute("SELECT * FROM recommendations WHERE status=? ORDER BY created_date DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM recommendations ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'done' THEN 1 ELSE 2 END, created_date DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Initialize on import
init_db()
_init_recommendations()
