"""Google Analytics 4 Data API client (bundled for portability)."""

import logging
from datetime import date

from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
    FilterExpression,
    Filter,
    OrderBy,
)

from dashboard import config

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def _get_client() -> BetaAnalyticsDataClient:
    credentials = service_account.Credentials.from_service_account_file(
        config.SERVICE_ACCOUNT_PATH, scopes=_SCOPES
    )
    return BetaAnalyticsDataClient(credentials=credentials)


def _property() -> str:
    return f"properties/{config.GA4_PROPERTY_ID}"


def run_report(
    start_date: date,
    end_date: date,
    metrics: list[str],
    dimensions: list[str] | None = None,
    dimension_filter: FilterExpression | None = None,
    order_by: list[OrderBy] | None = None,
    limit: int = 100,
) -> list[dict]:
    """Generic GA4 report runner. Returns list of row dicts."""
    if not config.GA4_PROPERTY_ID:
        logger.warning("GA4_PROPERTY_ID not set, skipping GA4 fetch")
        return []

    client = _get_client()

    request_kwargs = {
        "property": _property(),
        "date_ranges": [DateRange(start_date=start_date.isoformat(), end_date=end_date.isoformat())],
        "metrics": [Metric(name=m) for m in metrics],
        "limit": limit,
    }
    if dimensions:
        request_kwargs["dimensions"] = [Dimension(name=d) for d in dimensions]
    if dimension_filter:
        request_kwargs["dimension_filter"] = dimension_filter
    if order_by:
        request_kwargs["order_bys"] = order_by

    request = RunReportRequest(**request_kwargs)
    response = client.run_report(request)

    rows = []
    for row in response.rows:
        entry = {}
        if dimensions:
            for i, dim in enumerate(dimensions):
                entry[dim] = row.dimension_values[i].value
        for i, metric_name in enumerate(metrics):
            val = row.metric_values[i].value
            try:
                entry[metric_name] = int(val) if "." not in val else float(val)
            except ValueError:
                entry[metric_name] = val
        rows.append(entry)

    return rows
