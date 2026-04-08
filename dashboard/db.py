"""Storage layer — SQLite for data cache, Supabase for persistent recommendations."""

import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

from dashboard import config

logger = logging.getLogger(__name__)

# ── SQLite (data pull cache) ────────────────────────────────

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


# ── Supabase REST API (persistent recommendations) ──────────

def _sb_headers():
    """Supabase REST API headers."""
    return {
        "apikey": config.SUPABASE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _sb_url(table: str) -> str:
    return f"{config.SUPABASE_URL}/rest/v1/{table}"


def _sb_ok() -> bool:
    return bool(config.SUPABASE_URL and config.SUPABASE_KEY)


def add_recommendation(recommendation: str, category: str = "general", priority: str = "this_week") -> int:
    if not _sb_ok():
        return -1
    import httpx
    resp = httpx.post(_sb_url("recommendations"), headers=_sb_headers(), json={
        "created_date": datetime.now().isoformat()[:10],
        "recommendation": recommendation,
        "category": category,
        "priority": priority,
        "status": "pending",
        "outcome": "",
    })
    if resp.status_code in (200, 201) and resp.json():
        return resp.json()[0].get("id", -1)
    return -1


def update_recommendation(rec_id: int, status: str = None, outcome: str = None):
    if not _sb_ok():
        return
    import httpx
    updates = {"updated_date": datetime.now().isoformat()[:10]}
    if status:
        updates["status"] = status
    if outcome is not None:
        updates["outcome"] = outcome
    httpx.patch(f"{_sb_url('recommendations')}?id=eq.{rec_id}", headers=_sb_headers(), json=updates)


def delete_recommendation(rec_id: int):
    if not _sb_ok():
        return
    import httpx
    httpx.delete(f"{_sb_url('recommendations')}?id=eq.{rec_id}", headers=_sb_headers())


def get_recommendations(status: str = None) -> list[dict]:
    if not _sb_ok():
        return []
    import httpx
    url = _sb_url("recommendations")
    params = {"order": "status.asc,created_date.desc"}
    if status:
        params["status"] = f"eq.{status}"
    resp = httpx.get(url, headers=_sb_headers(), params=params)
    if resp.status_code == 200:
        return resp.json()
    return []


# Initialize on import
init_db()
