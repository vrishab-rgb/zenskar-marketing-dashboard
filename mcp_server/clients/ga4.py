"""Google Analytics 4 Data API client."""

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

from mcp_server import config

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
_client = None


def _get_client() -> BetaAnalyticsDataClient:
    global _client
    if _client is None:
        credentials = service_account.Credentials.from_service_account_file(
            config.SERVICE_ACCOUNT_PATH, scopes=_SCOPES
        )
        _client = BetaAnalyticsDataClient(credentials=credentials)
    return _client


def _property() -> str:
    return f"properties/{config.GA4_PROPERTY_ID}"


def _build_filter(country: str = "", channel: str = "") -> FilterExpression | None:
    """Build a combined filter expression for country and/or channel."""
    filters = []
    if country:
        filters.append(FilterExpression(
            filter=Filter(
                field_name="country",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.EXACT,
                    value=country,
                ),
            )
        ))
    if channel:
        filters.append(FilterExpression(
            filter=Filter(
                field_name="sessionDefaultChannelGroup",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.EXACT,
                    value=channel,
                ),
            )
        ))

    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    # AND filter for multiple conditions
    return FilterExpression(and_group=FilterExpression.AndGroup(expressions=filters))


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
                entry[metric_name] = int(val) if "." not in val else round(float(val), 4)
            except ValueError:
                entry[metric_name] = val
        rows.append(entry)

    return rows


def fetch_site_engagement(
    start_date: date, end_date: date, country: str = "", channel: str = ""
) -> dict:
    """Fetch site engagement metrics, optionally filtered by country/channel."""
    metrics = [
        "sessions", "totalUsers", "newUsers", "engagementRate",
        "averageSessionDuration", "screenPageViewsPerSession", "bounceRate",
    ]
    dim_filter = _build_filter(country, channel)
    rows = run_report(start_date, end_date, metrics=metrics, dimension_filter=dim_filter)
    return rows[0] if rows else {m: 0 for m in metrics}


def fetch_channel_breakdown(
    start_date: date, end_date: date, country: str = ""
) -> list[dict]:
    """Fetch traffic breakdown by channel group."""
    metrics = [
        "sessions", "totalUsers", "newUsers", "engagementRate",
        "averageSessionDuration", "bounceRate", "keyEvents",
    ]
    dim_filter = _build_filter(country)
    return run_report(
        start_date, end_date,
        metrics=metrics,
        dimensions=["sessionDefaultChannelGroup"],
        dimension_filter=dim_filter,
        order_by=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        limit=15,
    )


def fetch_top_pages(
    start_date: date, end_date: date, limit: int = 30,
    country: str = "", channel: str = ""
) -> list[dict]:
    """Fetch top landing pages by sessions."""
    metrics = [
        "sessions", "totalUsers", "engagementRate",
        "averageSessionDuration", "bounceRate", "keyEvents",
    ]
    dim_filter = _build_filter(country, channel)
    return run_report(
        start_date, end_date,
        metrics=metrics,
        dimensions=["landingPagePlusQueryString"],
        dimension_filter=dim_filter,
        order_by=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        limit=limit,
    )
