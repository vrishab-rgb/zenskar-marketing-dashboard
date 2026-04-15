"""Bing Webmaster Tools API client."""

import logging
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import requests

from mcp_server import config

logger = logging.getLogger(__name__)

_BASE = "https://ssl.bing.com/webmaster/api.svc/json"
_HEADERS = {"Accept": "application/json"}

# Matches /Date(1234567890000-0800)/ or /Date(1234567890000)/
_MS_DATE_RE = re.compile(r"/Date\((\d+)[^)]*\)/")


def _parse_ms_date(ms_date_str: str) -> date | None:
    """Parse Microsoft JSON date format /Date(epoch_ms+offset)/ to a date."""
    m = _MS_DATE_RE.search(ms_date_str or "")
    if not m:
        return None
    return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc).date()


def _filter_rows_by_date(rows: list[dict], start: date, end: date) -> list[dict]:
    """Filter Bing API rows to those whose week overlaps the requested range."""
    range_start = start - timedelta(days=6)
    filtered = []
    for row in rows:
        row_date = _parse_ms_date(row.get("Date", ""))
        if row_date is None:
            continue
        if range_start <= row_date <= end:
            filtered.append(row)
    return filtered


def _get(endpoint: str, params: dict):
    """Make a GET request to the Bing Webmaster API."""
    if not config.BING_API_KEY:
        logger.warning("BING_API_KEY not set — skipping Bing data")
        return []
    params["apikey"] = config.BING_API_KEY
    try:
        r = requests.get(f"{_BASE}/{endpoint}", params=params, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return r.json().get("d", [])
    except Exception as e:
        logger.warning(f"Bing API error ({endpoint}): {e}")
        return []


def fetch_bing_top_queries(
    start: date, end: date, site_url: str | None = None
) -> list[dict]:
    """Fetch query stats from Bing Webmaster Tools for US traffic."""
    site = site_url or config.GSC_SITE_URL
    data = _get("GetQueryStats", {
        "siteUrl": site,
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "country": "us",
    })

    if not isinstance(data, list):
        data = []
    data = _filter_rows_by_date(data, start, end)

    agg: dict[str, dict] = defaultdict(
        lambda: {"clicks": 0, "impressions": 0, "position_sum": 0.0, "position_count": 0}
    )
    for row in data:
        q = row.get("Query", "")
        if not q:
            continue
        bucket = agg[q]
        bucket["clicks"] += row.get("Clicks") or 0
        bucket["impressions"] += row.get("Impressions") or 0
        pos = row.get("AvgImpressionPosition") or 0.0
        if pos > 0:
            bucket["position_sum"] += pos
            bucket["position_count"] += 1

    rows = []
    for query, vals in agg.items():
        impr = vals["impressions"]
        clicks = vals["clicks"]
        avg_pos = vals["position_sum"] / vals["position_count"] if vals["position_count"] > 0 else 0.0
        rows.append({
            "query": query,
            "clicks": clicks,
            "impressions": impr,
            "ctr": round(clicks / impr, 4) if impr > 0 else 0.0,
            "position": round(avg_pos, 1),
        })
    return sorted(rows, key=lambda x: x["clicks"], reverse=True)


def fetch_bing_top_pages(
    start: date, end: date, site_url: str | None = None
) -> list[dict]:
    """Fetch page stats from Bing Webmaster Tools for US traffic."""
    site = site_url or config.GSC_SITE_URL
    data = _get("GetPageStats", {
        "siteUrl": site,
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "country": "us",
    })

    if not isinstance(data, list):
        data = []
    data = _filter_rows_by_date(data, start, end)

    agg: dict[str, dict] = defaultdict(lambda: {"clicks": 0, "impressions": 0})
    for row in data:
        url = row.get("Query") or row.get("Url") or row.get("Page") or ""
        if not url:
            continue
        agg[url]["clicks"] += row.get("Clicks") or 0
        agg[url]["impressions"] += row.get("Impressions") or 0

    rows = []
    for url, vals in agg.items():
        rows.append({
            "page": url,
            "clicks": vals["clicks"],
            "impressions": vals["impressions"],
        })
    return sorted(rows, key=lambda x: x["clicks"], reverse=True)
