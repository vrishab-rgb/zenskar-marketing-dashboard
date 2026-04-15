"""Zenskar Marketing Analytics MCP Server.

Exposes read-only tools for GSC, GA4, Google Ads, HubSpot, and Bing.

Supports two transport modes:
- stdio (default) — for Claude Code / Claude Desktop local use
- sse — for remote deployment (Render, Railway, etc.) accessible via Claude.ai web

Set MCP_TRANSPORT=sse and PORT=8000 env vars for remote mode.
"""

import json
import logging
import os
from datetime import date, timedelta

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.WARNING)

# Remote deployment: bind to 0.0.0.0 and use PORT from hosting platform
_host = os.environ.get("HOST", "0.0.0.0")
_port = int(os.environ.get("PORT", "8000"))

mcp = FastMCP(
    "Zenskar Marketing Analytics",
    host=_host,
    port=_port,
    instructions=(
        "Marketing analytics server for Zenskar. Provides read-only access to:\n"
        "- Google Search Console (organic search performance)\n"
        "- Google Analytics 4 (site engagement, traffic channels)\n"
        "- Google Ads (campaign performance, keywords, search terms)\n"
        "- HubSpot CRM (deals, contacts, companies — READ-ONLY)\n"
        "- Bing Webmaster Tools (Bing search performance)\n\n"
        "All date parameters accept YYYY-MM-DD format. Omit for last 28 days.\n"
        "HubSpot tools are strictly read-only — no data is ever modified."
    ),
)


# ── Helpers ─────────────────────────────────────────────────────


def _parse_dates(
    start_str: str, end_str: str, default_days: int = 28, lag_days: int = 0
) -> tuple[date, date]:
    """Parse date strings or default to last N days."""
    today = date.today()
    end = (
        date.fromisoformat(end_str)
        if end_str
        else today - timedelta(days=lag_days)
    )
    start = (
        date.fromisoformat(start_str)
        if start_str
        else end - timedelta(days=default_days)
    )
    return start, end


def _ok(data) -> str:
    return json.dumps(data, indent=2, default=str)


def _err(tool: str, ex: Exception) -> str:
    return json.dumps({"error": str(ex), "tool": tool})


# ═══════════════════════════════════════════════════════════════
# GSC TOOLS
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def gsc_search_analytics(
    dimensions: str = "query",
    start_date: str = "",
    end_date: str = "",
    row_limit: int = 100,
    country: str = "",
) -> str:
    """Get Google Search Console search analytics data.

    Args:
        dimensions: Comma-separated dimensions (query, page, date, device, country). Default: "query"
        start_date: Start date YYYY-MM-DD (default: 31 days ago)
        end_date: End date YYYY-MM-DD (default: 3 days ago, due to GSC data lag)
        row_limit: Max rows to return (default: 100)
        country: 3-letter country code filter (e.g. usa, gbr, can). Empty for global.
    """
    try:
        from mcp_server.clients import gsc

        start, end = _parse_dates(start_date, end_date, lag_days=3)
        dims = [d.strip() for d in dimensions.split(",")]

        filters = None
        if country:
            filters = [{"filters": [{"dimension": "country", "operator": "equals", "expression": country.lower()}]}]

        rows = gsc.fetch_search_analytics(start, end, dimensions=dims, row_limit=row_limit, dimension_filter_groups=filters)
        return _ok({"period": f"{start} to {end}", "row_count": len(rows), "rows": rows})
    except Exception as ex:
        return _err("gsc_search_analytics", ex)


@mcp.tool()
def gsc_totals(start_date: str = "", end_date: str = "") -> str:
    """Get aggregate Google Search Console totals (clicks, impressions, CTR, position).

    Args:
        start_date: Start date YYYY-MM-DD (default: 31 days ago)
        end_date: End date YYYY-MM-DD (default: 3 days ago)
    """
    try:
        from mcp_server.clients import gsc

        start, end = _parse_dates(start_date, end_date, lag_days=3)
        result = gsc.fetch_totals(start, end)
        result["period"] = f"{start} to {end}"
        return _ok(result)
    except Exception as ex:
        return _err("gsc_totals", ex)


@mcp.tool()
def gsc_compare_periods(
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
    dimensions: str = "query",
    row_limit: int = 50,
) -> str:
    """Compare two date periods in Google Search Console side-by-side.

    Args:
        period1_start: First period start YYYY-MM-DD
        period1_end: First period end YYYY-MM-DD
        period2_start: Second period start YYYY-MM-DD
        period2_end: Second period end YYYY-MM-DD
        dimensions: Comma-separated dimensions (default: "query")
        row_limit: Max rows per period (default: 50)
    """
    try:
        from mcp_server.clients import gsc

        p1_start = date.fromisoformat(period1_start)
        p1_end = date.fromisoformat(period1_end)
        p2_start = date.fromisoformat(period2_start)
        p2_end = date.fromisoformat(period2_end)
        dims = [d.strip() for d in dimensions.split(",")]

        p1_rows = gsc.fetch_search_analytics(p1_start, p1_end, dimensions=dims, row_limit=row_limit)
        p2_rows = gsc.fetch_search_analytics(p2_start, p2_end, dimensions=dims, row_limit=row_limit)

        # Index by dimension key
        dim_key = dims[0]
        p1_map = {r[dim_key]: r for r in p1_rows}
        p2_map = {r[dim_key]: r for r in p2_rows}

        all_keys = set(p1_map.keys()) | set(p2_map.keys())
        compared = []
        for key in all_keys:
            r1 = p1_map.get(key, {})
            r2 = p2_map.get(key, {})
            entry = {dim_key: key}
            for metric in ("clicks", "impressions", "ctr", "position"):
                v1 = r1.get(metric, 0)
                v2 = r2.get(metric, 0)
                entry[f"p1_{metric}"] = v1
                entry[f"p2_{metric}"] = v2
                entry[f"{metric}_change"] = round(v2 - v1, 4)
                if v1:
                    entry[f"{metric}_change_pct"] = round((v2 - v1) / v1 * 100, 1)
            compared.append(entry)

        compared.sort(key=lambda x: abs(x.get("clicks_change", 0)), reverse=True)

        return _ok({
            "period1": f"{p1_start} to {p1_end}",
            "period2": f"{p2_start} to {p2_end}",
            "row_count": len(compared),
            "rows": compared[:row_limit],
        })
    except Exception as ex:
        return _err("gsc_compare_periods", ex)


# ═══════════════════════════════════════════════════════════════
# GA4 TOOLS
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def ga4_site_engagement(
    start_date: str = "",
    end_date: str = "",
    country: str = "",
    channel: str = "",
) -> str:
    """Get GA4 site engagement metrics (sessions, users, engagement rate, bounce rate).

    Args:
        start_date: Start date YYYY-MM-DD (default: 28 days ago)
        end_date: End date YYYY-MM-DD (default: today)
        country: Full country name filter (e.g. "United States", "United Kingdom")
        channel: Channel filter (e.g. "Organic Search", "Paid Search", "Direct")
    """
    try:
        from mcp_server.clients import ga4

        start, end = _parse_dates(start_date, end_date)
        result = ga4.fetch_site_engagement(start, end, country=country, channel=channel)
        result["period"] = f"{start} to {end}"
        if country:
            result["country_filter"] = country
        if channel:
            result["channel_filter"] = channel
        return _ok(result)
    except Exception as ex:
        return _err("ga4_site_engagement", ex)


@mcp.tool()
def ga4_channel_breakdown(
    start_date: str = "",
    end_date: str = "",
    country: str = "",
) -> str:
    """Get GA4 traffic breakdown by channel (Organic Search, Paid Search, Direct, etc.).

    Args:
        start_date: Start date YYYY-MM-DD (default: 28 days ago)
        end_date: End date YYYY-MM-DD (default: today)
        country: Full country name filter (e.g. "United States")
    """
    try:
        from mcp_server.clients import ga4

        start, end = _parse_dates(start_date, end_date)
        rows = ga4.fetch_channel_breakdown(start, end, country=country)
        return _ok({"period": f"{start} to {end}", "channels": rows})
    except Exception as ex:
        return _err("ga4_channel_breakdown", ex)


@mcp.tool()
def ga4_top_pages(
    start_date: str = "",
    end_date: str = "",
    limit: int = 30,
    country: str = "",
    channel: str = "",
) -> str:
    """Get top landing pages by sessions from GA4.

    Args:
        start_date: Start date YYYY-MM-DD (default: 28 days ago)
        end_date: End date YYYY-MM-DD (default: today)
        limit: Max pages to return (default: 30)
        country: Full country name filter (e.g. "United States")
        channel: Channel filter (e.g. "Organic Search")
    """
    try:
        from mcp_server.clients import ga4

        start, end = _parse_dates(start_date, end_date)
        rows = ga4.fetch_top_pages(start, end, limit=limit, country=country, channel=channel)
        return _ok({"period": f"{start} to {end}", "page_count": len(rows), "pages": rows})
    except Exception as ex:
        return _err("ga4_top_pages", ex)


@mcp.tool()
def ga4_report(
    metrics: str,
    dimensions: str = "",
    start_date: str = "",
    end_date: str = "",
    country: str = "",
    channel: str = "",
    limit: int = 50,
) -> str:
    """Run a custom GA4 report with any metrics and dimensions.

    Args:
        metrics: Comma-separated metric names (e.g. "sessions,totalUsers,keyEvents")
        dimensions: Comma-separated dimension names (e.g. "date,country"). Optional.
        start_date: Start date YYYY-MM-DD (default: 28 days ago)
        end_date: End date YYYY-MM-DD (default: today)
        country: Full country name filter
        channel: Channel filter
        limit: Max rows (default: 50)
    """
    try:
        from mcp_server.clients import ga4

        start, end = _parse_dates(start_date, end_date)
        metrics_list = [m.strip() for m in metrics.split(",")]
        dims_list = [d.strip() for d in dimensions.split(",") if d.strip()] or None
        dim_filter = ga4._build_filter(country, channel)

        from google.analytics.data_v1beta.types import OrderBy

        order = None
        if dims_list:
            order = [OrderBy(metric=OrderBy.MetricOrderBy(metric_name=metrics_list[0]), desc=True)]

        rows = ga4.run_report(
            start, end,
            metrics=metrics_list,
            dimensions=dims_list,
            dimension_filter=dim_filter,
            order_by=order,
            limit=limit,
        )
        return _ok({"period": f"{start} to {end}", "row_count": len(rows), "rows": rows})
    except Exception as ex:
        return _err("ga4_report", ex)


# ═══════════════════════════════════════════════════════════════
# GOOGLE ADS TOOLS
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def ads_campaigns(start_date: str = "", end_date: str = "") -> str:
    """Get Google Ads campaign performance (cost, clicks, conversions, impression share).

    Args:
        start_date: Start date YYYY-MM-DD (default: 28 days ago)
        end_date: End date YYYY-MM-DD (default: today)
    """
    try:
        from mcp_server.clients import google_ads

        start, end = _parse_dates(start_date, end_date)
        rows = google_ads.fetch_campaigns(start, end)
        return _ok({"period": f"{start} to {end}", "campaigns": rows})
    except Exception as ex:
        return _err("ads_campaigns", ex)


@mcp.tool()
def ads_keywords(
    start_date: str = "", end_date: str = "", limit: int = 30
) -> str:
    """Get Google Ads keyword performance with quality scores.

    Args:
        start_date: Start date YYYY-MM-DD (default: 28 days ago)
        end_date: End date YYYY-MM-DD (default: today)
        limit: Max keywords to return (default: 30)
    """
    try:
        from mcp_server.clients import google_ads

        start, end = _parse_dates(start_date, end_date)
        rows = google_ads.fetch_keywords(start, end, limit=limit)
        return _ok({"period": f"{start} to {end}", "keyword_count": len(rows), "keywords": rows})
    except Exception as ex:
        return _err("ads_keywords", ex)


@mcp.tool()
def ads_search_terms(
    start_date: str = "", end_date: str = "", limit: int = 50
) -> str:
    """Get actual search terms triggering Google Ads.

    Args:
        start_date: Start date YYYY-MM-DD (default: 28 days ago)
        end_date: End date YYYY-MM-DD (default: today)
        limit: Max search terms to return (default: 50)
    """
    try:
        from mcp_server.clients import google_ads

        start, end = _parse_dates(start_date, end_date)
        rows = google_ads.fetch_search_terms(start, end, limit=limit)
        return _ok({"period": f"{start} to {end}", "term_count": len(rows), "search_terms": rows})
    except Exception as ex:
        return _err("ads_search_terms", ex)


# ═══════════════════════════════════════════════════════════════
# HUBSPOT TOOLS (all READ-ONLY)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def hubspot_search_deals(
    filters: str = "[]",
    properties: str = "dealname,amount,dealstage,pipeline,createdate,closedate,primary_source",
    limit: int = 20,
    sort_by: str = "createdate",
) -> str:
    """Search HubSpot deals with filters (READ-ONLY).

    Args:
        filters: JSON string of HubSpot filter groups array. Example:
            '[{"filters":[{"propertyName":"dealstage","operator":"EQ","value":"closedwon"}]}]'
        properties: Comma-separated deal properties to return
        limit: Max deals to return (default: 20)
        sort_by: Property to sort by (default: "createdate")
    """
    try:
        from mcp_server.clients import hubspot

        filter_groups = json.loads(filters)
        props_list = [p.strip() for p in properties.split(",")]
        rows = hubspot.search_deals(filter_groups, props_list, limit=limit, sort_by=sort_by)
        return _ok({"deal_count": len(rows), "deals": rows})
    except Exception as ex:
        return _err("hubspot_search_deals", ex)


@mcp.tool()
def hubspot_get_company(
    company_id: str,
    properties: str = "name,domain,industry,numberofemployees,annualrevenue,country,city,description",
) -> str:
    """Get a HubSpot company by ID (READ-ONLY).

    Args:
        company_id: HubSpot company ID
        properties: Comma-separated properties to return
    """
    try:
        from mcp_server.clients import hubspot

        props_list = [p.strip() for p in properties.split(",")]
        result = hubspot.get_company(company_id, props_list)
        return _ok(result)
    except Exception as ex:
        return _err("hubspot_get_company", ex)


@mcp.tool()
def hubspot_get_contact(
    contact_id: str,
    properties: str = "firstname,lastname,email,jobtitle,hs_analytics_source,hs_analytics_first_url",
) -> str:
    """Get a HubSpot contact by ID (READ-ONLY).

    Args:
        contact_id: HubSpot contact ID
        properties: Comma-separated properties to return
    """
    try:
        from mcp_server.clients import hubspot

        props_list = [p.strip() for p in properties.split(",")]
        result = hubspot.get_contact(contact_id, props_list)
        return _ok(result)
    except Exception as ex:
        return _err("hubspot_get_contact", ex)


@mcp.tool()
def hubspot_get_deal(
    deal_id: str,
    properties: str = "dealname,amount,dealstage,closedate,primary_source,description",
) -> str:
    """Get a HubSpot deal by ID (READ-ONLY).

    Args:
        deal_id: HubSpot deal ID
        properties: Comma-separated properties to return
    """
    try:
        from mcp_server.clients import hubspot

        props_list = [p.strip() for p in properties.split(",")]
        result = hubspot.get_deal(deal_id, props_list)
        return _ok(result)
    except Exception as ex:
        return _err("hubspot_get_deal", ex)


@mcp.tool()
def hubspot_company_contacts(company_id: str, limit: int = 5) -> str:
    """Get contacts associated with a HubSpot company (READ-ONLY).

    Args:
        company_id: HubSpot company ID
        limit: Max contacts to return (default: 5)
    """
    try:
        from mcp_server.clients import hubspot

        contacts = hubspot.get_company_contacts(company_id, limit=limit)
        return _ok({"company_id": company_id, "contact_count": len(contacts), "contacts": contacts})
    except Exception as ex:
        return _err("hubspot_company_contacts", ex)


@mcp.tool()
def hubspot_company_activity(
    company_id: str,
    include_notes: bool = True,
    include_meetings: bool = True,
    limit: int = 5,
) -> str:
    """Get notes and meetings for a HubSpot company (READ-ONLY).

    Args:
        company_id: HubSpot company ID
        include_notes: Include notes (default: True)
        include_meetings: Include meetings (default: True)
        limit: Max items per type (default: 5)
    """
    try:
        from mcp_server.clients import hubspot

        result: dict = {"company_id": company_id}
        if include_notes:
            result["notes"] = hubspot.get_company_notes(company_id, limit=limit)
        if include_meetings:
            result["meetings"] = hubspot.get_company_meetings(company_id, limit=limit)
        return _ok(result)
    except Exception as ex:
        return _err("hubspot_company_activity", ex)


@mcp.tool()
def hubspot_contact_journey(contact_id: str, limit: int = 50) -> str:
    """Get page visit history for a HubSpot contact (READ-ONLY).

    Args:
        contact_id: HubSpot contact ID
        limit: Max page visits to return (default: 50)
    """
    try:
        from mcp_server.clients import hubspot

        events = hubspot.get_contact_page_visits(contact_id, limit=limit)
        return _ok({"contact_id": contact_id, "visit_count": len(events), "visits": events})
    except Exception as ex:
        return _err("hubspot_contact_journey", ex)


# ═══════════════════════════════════════════════════════════════
# BING TOOLS
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def bing_top_queries(start_date: str = "", end_date: str = "") -> str:
    """Get top Bing search queries (US traffic) with clicks, impressions, CTR, position.

    Args:
        start_date: Start date YYYY-MM-DD (default: 28 days ago)
        end_date: End date YYYY-MM-DD (default: today)
    """
    try:
        from mcp_server.clients import bing

        start, end = _parse_dates(start_date, end_date)
        rows = bing.fetch_bing_top_queries(start, end)
        return _ok({"period": f"{start} to {end}", "query_count": len(rows), "queries": rows})
    except Exception as ex:
        return _err("bing_top_queries", ex)


@mcp.tool()
def bing_top_pages(start_date: str = "", end_date: str = "") -> str:
    """Get top Bing pages by clicks (US traffic).

    Args:
        start_date: Start date YYYY-MM-DD (default: 28 days ago)
        end_date: End date YYYY-MM-DD (default: today)
    """
    try:
        from mcp_server.clients import bing

        start, end = _parse_dates(start_date, end_date)
        rows = bing.fetch_bing_top_pages(start, end)
        return _ok({"period": f"{start} to {end}", "page_count": len(rows), "pages": rows})
    except Exception as ex:
        return _err("bing_top_pages", ex)


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════


def main():
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
