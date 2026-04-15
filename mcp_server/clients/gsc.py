"""Google Search Console API client."""

import logging
from datetime import date

from google.oauth2 import service_account
from googleapiclient.discovery import build

from mcp_server import config

logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
_service = None


def _get_service():
    global _service
    if _service is None:
        credentials = service_account.Credentials.from_service_account_file(
            config.SERVICE_ACCOUNT_PATH, scopes=_SCOPES
        )
        _service = build("searchconsole", "v1", credentials=credentials)
    return _service


def fetch_search_analytics(
    start_date: date,
    end_date: date,
    dimensions: list[str] | None = None,
    row_limit: int = 25000,
    dimension_filter_groups: list[dict] | None = None,
) -> list[dict]:
    """Fetch search analytics from GSC with optional dimension filters."""
    if dimensions is None:
        dimensions = ["query", "page", "date"]

    service = _get_service()
    body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": dimensions,
        "rowLimit": row_limit,
        "dataState": "final",
    }
    if dimension_filter_groups:
        body["dimensionFilterGroups"] = dimension_filter_groups

    all_rows = []
    start_row = 0

    while True:
        body["startRow"] = start_row
        response = service.searchanalytics().query(
            siteUrl=config.GSC_SITE_URL, body=body
        ).execute()

        rows = response.get("rows", [])
        if not rows:
            break

        for row in rows:
            keys = row.get("keys", [])
            entry = {
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0.0), 4),
                "position": round(row.get("position", 0.0), 1),
            }
            for i, dim in enumerate(dimensions):
                entry[dim] = keys[i] if i < len(keys) else None
            all_rows.append(entry)

        if len(rows) < row_limit:
            break
        start_row += row_limit

    return all_rows


def fetch_totals(start_date: date, end_date: date) -> dict:
    """Fetch aggregate totals (no dimensions) for a date range."""
    service = _get_service()
    body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dataState": "final",
    }
    response = service.searchanalytics().query(
        siteUrl=config.GSC_SITE_URL, body=body
    ).execute()

    rows = response.get("rows", [])
    if rows:
        row = rows[0]
        return {
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": round(row.get("ctr", 0.0), 4),
            "position": round(row.get("position", 0.0), 1),
        }
    return {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}
