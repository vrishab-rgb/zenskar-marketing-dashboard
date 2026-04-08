"""Data pullers for GSC, GA4, and Google Ads. All read-only."""

import json
from datetime import date, timedelta

from dashboard import config
from dashboard.db import store_pull, get_latest_pull
from dashboard.gsc_client import fetch_totals, fetch_search_analytics
from dashboard.ga4_client import run_report

# GSC data has ~3 day lag
GSC_LAG_DAYS = 3

# Country codes for GSC filtering
COUNTRY_CODES = {
    "US": "usa",
    "UK": "gbr",
    "Canada": "can",
    "India": "ind",
    "Israel": "isr",
    "Germany": "deu",
    "Australia": "aus",
}

# GA4 country names (uses full names, not codes)
GA4_COUNTRY_NAMES = {
    "US": "United States",
    "UK": "United Kingdom",
    "Canada": "Canada",
    "India": "India",
    "Israel": "Israel",
    "Germany": "Germany",
    "Australia": "Australia",
}


def _gsc_dates(start: date, end: date) -> tuple[date, date]:
    """Shift dates back by GSC lag."""
    lag = timedelta(days=GSC_LAG_DAYS)
    return start - lag, end - lag


def _gsc_country_filter(country: str) -> list[dict] | None:
    """Build GSC dimension filter for a country. Returns None for global."""
    code = COUNTRY_CODES.get(country)
    if not code:
        return None
    return [{
        "filters": [{
            "dimension": "country",
            "operator": "equals",
            "expression": code,
        }]
    }]


# ── GSC ──────────────────────────────────────────────────────

def pull_gsc(start_date: date, end_date: date, force: bool = False, country: str = "Global") -> dict:
    gsc_start, gsc_end = _gsc_dates(start_date, end_date)
    source = f"gsc_{country.lower()}"
    country_filter = _gsc_country_filter(country)

    if not force:
        totals, _ = get_latest_pull(source, "totals", gsc_start, gsc_end)
        queries, _ = get_latest_pull(source, "queries", gsc_start, gsc_end)
        pages, _ = get_latest_pull(source, "pages", gsc_start, gsc_end)
        page_queries, _ = get_latest_pull(source, "page_queries", gsc_start, gsc_end)
        if totals and queries and pages and page_queries:
            return {"totals": totals, "queries": queries, "pages": pages, "page_queries": page_queries, "gsc_start": str(gsc_start), "gsc_end": str(gsc_end)}

    if country_filter:
        totals_rows = fetch_search_analytics(gsc_start, gsc_end, dimensions=["country"], dimension_filter_groups=country_filter)
        if totals_rows:
            totals = {"clicks": sum(r["clicks"] for r in totals_rows), "impressions": sum(r["impressions"] for r in totals_rows),
                       "ctr": sum(r["clicks"] for r in totals_rows) / max(sum(r["impressions"] for r in totals_rows), 1),
                       "position": sum(r["position"] * r["impressions"] for r in totals_rows) / max(sum(r["impressions"] for r in totals_rows), 1)}
        else:
            totals = {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}
    else:
        totals = fetch_totals(gsc_start, gsc_end)

    queries = fetch_search_analytics(gsc_start, gsc_end, dimensions=["query"], dimension_filter_groups=country_filter)
    pages = fetch_search_analytics(gsc_start, gsc_end, dimensions=["page"], dimension_filter_groups=country_filter)

    store_pull(source, "totals", gsc_start, gsc_end, totals)
    store_pull(source, "queries", gsc_start, gsc_end, queries)
    store_pull(source, "pages", gsc_start, gsc_end, pages)

    # Query-page pairs (for page explorer)
    page_queries = fetch_search_analytics(gsc_start, gsc_end, dimensions=["page", "query"], dimension_filter_groups=country_filter)
    store_pull(source, "page_queries", gsc_start, gsc_end, page_queries)

    return {"totals": totals, "queries": queries, "pages": pages, "page_queries": page_queries, "gsc_start": str(gsc_start), "gsc_end": str(gsc_end)}


# ── GA4 ──────────────────────────────────────────────────────

def pull_ga4(start_date: date, end_date: date, force: bool = False, country: str = "Global") -> dict:
    source = f"ga4_{country.lower()}"

    if not force:
        engagement, _ = get_latest_pull(source, "engagement", start_date, end_date)
        channels, _ = get_latest_pull(source, "channels", start_date, end_date)
        landing_pages, _ = get_latest_pull(source, "landing_pages", start_date, end_date)
        if engagement and channels and landing_pages:
            return {"engagement": engagement, "channels": channels, "landing_pages": landing_pages}

    from google.analytics.data_v1beta.types import OrderBy, FilterExpression, Filter

    # Build country filter
    ga4_country_name = GA4_COUNTRY_NAMES.get(country)
    if ga4_country_name:
        geo_filter = FilterExpression(
            filter=Filter(
                field_name="country",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.EXACT,
                    value=ga4_country_name,
                ),
            )
        )
    else:
        geo_filter = None

    # Engagement metrics
    eng_metrics = ["sessions", "totalUsers", "newUsers", "engagementRate",
                   "averageSessionDuration", "screenPageViewsPerSession", "bounceRate"]
    eng_rows = run_report(start_date, end_date, metrics=eng_metrics, dimension_filter=geo_filter)
    engagement = eng_rows[0] if eng_rows else {m: 0 for m in eng_metrics}

    # Channel breakdown
    channel_metrics = ["sessions", "totalUsers", "newUsers", "engagementRate",
                       "averageSessionDuration", "bounceRate", "keyEvents", "userKeyEventRate"]
    channels = run_report(
        start_date, end_date,
        metrics=channel_metrics,
        dimensions=["sessionDefaultChannelGroup"],
        dimension_filter=geo_filter,
        order_by=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        limit=15,
    )

    # Landing pages
    lp_metrics = ["sessions", "totalUsers", "engagementRate", "averageSessionDuration",
                  "bounceRate", "keyEvents"]
    landing_pages = run_report(
        start_date, end_date,
        metrics=lp_metrics,
        dimensions=["landingPagePlusQueryString"],
        dimension_filter=geo_filter,
        order_by=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        limit=30,
    )

    store_pull(source, "engagement", start_date, end_date, engagement)
    store_pull(source, "channels", start_date, end_date, channels)
    store_pull(source, "landing_pages", start_date, end_date, landing_pages)

    return {"engagement": engagement, "channels": channels, "landing_pages": landing_pages}


# ── Google Ads ───────────────────────────────────────────────

def _get_ads_client():
    from google.ads.googleads.client import GoogleAdsClient
    if config.ADS_TOKEN:
        t = config.ADS_TOKEN
    else:
        with open(config.ADS_TOKEN_FILE) as f:
            t = json.load(f)
    return GoogleAdsClient.load_from_dict({
        "developer_token": config.ADS_DEV_TOKEN,
        "use_proto_plus": True,
        "client_id": t["client_id"],
        "client_secret": t["client_secret"],
        "refresh_token": t["refresh_token"],
    })


def _ads_query(client, query: str) -> list:
    from google.ads.googleads.errors import GoogleAdsException
    ga = client.get_service("GoogleAdsService")
    rows = []
    try:
        stream = ga.search_stream(customer_id=config.ADS_CUSTOMER_ID, query=query)
        for batch in stream:
            for row in batch.results:
                rows.append(row)
    except GoogleAdsException:
        pass
    return rows


def pull_ads(start_date: date, end_date: date, force: bool = False) -> dict:
    source = "ads"

    if not force:
        campaigns, _ = get_latest_pull(source, "campaigns", start_date, end_date)
        keywords, _ = get_latest_pull(source, "keywords", start_date, end_date)
        search_terms, _ = get_latest_pull(source, "search_terms", start_date, end_date)
        if campaigns and keywords and search_terms:
            return {"campaigns": campaigns, "keywords": keywords, "search_terms": search_terms}

    client = _get_ads_client()

    # Campaigns
    rows = _ads_query(client, f"""
        SELECT campaign.name, campaign.status,
            metrics.impressions, metrics.clicks, metrics.ctr,
            metrics.average_cpc, metrics.cost_micros,
            metrics.conversions, metrics.search_impression_share
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
    """)
    campaigns = []
    for r in rows:
        campaigns.append({
            "name": r.campaign.name, "status": r.campaign.status.name,
            "impressions": r.metrics.impressions, "clicks": r.metrics.clicks,
            "ctr": r.metrics.ctr, "avg_cpc": r.metrics.average_cpc / 1e6,
            "cost": r.metrics.cost_micros / 1e6, "conversions": r.metrics.conversions,
            "impression_share": r.metrics.search_impression_share,
        })

    # Keywords with quality scores
    rows = _ads_query(client, f"""
        SELECT campaign.name, ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            ad_group_criterion.quality_info.quality_score,
            ad_group_criterion.quality_info.creative_quality_score,
            ad_group_criterion.quality_info.post_click_quality_score,
            ad_group_criterion.quality_info.search_predicted_ctr,
            metrics.impressions, metrics.clicks, metrics.ctr,
            metrics.average_cpc, metrics.cost_micros, metrics.conversions
        FROM keyword_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY metrics.cost_micros DESC
        LIMIT 30
    """)
    keywords = []
    for r in rows:
        qi = r.ad_group_criterion.quality_info
        keywords.append({
            "keyword": r.ad_group_criterion.keyword.text,
            "match_type": r.ad_group_criterion.keyword.match_type.name,
            "campaign": r.campaign.name,
            "quality_score": qi.quality_score if qi.quality_score else None,
            "creative_quality": qi.creative_quality_score.name if qi.creative_quality_score else None,
            "landing_page_quality": qi.post_click_quality_score.name if qi.post_click_quality_score else None,
            "predicted_ctr": qi.search_predicted_ctr.name if qi.search_predicted_ctr else None,
            "impressions": r.metrics.impressions, "clicks": r.metrics.clicks,
            "ctr": r.metrics.ctr, "avg_cpc": r.metrics.average_cpc / 1e6,
            "cost": r.metrics.cost_micros / 1e6, "conversions": r.metrics.conversions,
        })

    # Search terms
    rows = _ads_query(client, f"""
        SELECT campaign.name, search_term_view.search_term,
            metrics.impressions, metrics.clicks, metrics.ctr,
            metrics.cost_micros, metrics.conversions
        FROM search_term_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY metrics.cost_micros DESC
        LIMIT 100
    """)
    search_terms = []
    for r in rows:
        search_terms.append({
            "term": r.search_term_view.search_term, "campaign": r.campaign.name,
            "impressions": r.metrics.impressions, "clicks": r.metrics.clicks,
            "ctr": r.metrics.ctr, "cost": r.metrics.cost_micros / 1e6,
            "conversions": r.metrics.conversions,
        })

    store_pull(source, "campaigns", start_date, end_date, campaigns)
    store_pull(source, "keywords", start_date, end_date, keywords)
    store_pull(source, "search_terms", start_date, end_date, search_terms)

    return {"campaigns": campaigns, "keywords": keywords, "search_terms": search_terms}


# ── Combined ─────────────────────────────────────────────────

def pull_all(start_date: date, end_date: date, force: bool = False, country: str = "US") -> dict:
    return {
        "gsc": pull_gsc(start_date, end_date, force, country),
        "ga4": pull_ga4(start_date, end_date, force, country),
        "ads": pull_ads(start_date, end_date, force),
        "country": country,
    }


def load_all(start_date: date, end_date: date, country: str = "US") -> dict | None:
    """Load all data from DB without pulling. Returns None if any source is missing."""
    gsc_start, gsc_end = _gsc_dates(start_date, end_date)
    gsc_source = f"gsc_{country.lower()}"
    ga4_source = f"ga4_{country.lower()}"

    gsc_totals, ts = get_latest_pull(gsc_source, "totals", gsc_start, gsc_end)
    if not gsc_totals:
        return None
    gsc_queries, _ = get_latest_pull(gsc_source, "queries", gsc_start, gsc_end)
    gsc_pages, _ = get_latest_pull(gsc_source, "pages", gsc_start, gsc_end)
    gsc_page_queries, _ = get_latest_pull(gsc_source, "page_queries", gsc_start, gsc_end)

    ga4_engagement, _ = get_latest_pull(ga4_source, "engagement", start_date, end_date)
    ga4_channels, _ = get_latest_pull(ga4_source, "channels", start_date, end_date)
    ga4_landing_pages, _ = get_latest_pull(ga4_source, "landing_pages", start_date, end_date)

    ads_campaigns, _ = get_latest_pull("ads", "campaigns", start_date, end_date)
    ads_keywords, _ = get_latest_pull("ads", "keywords", start_date, end_date)
    ads_search_terms, _ = get_latest_pull("ads", "search_terms", start_date, end_date)

    if not all([gsc_queries, gsc_pages, ga4_engagement, ga4_channels, ga4_landing_pages, ads_campaigns, ads_keywords, ads_search_terms]):
        return None

    return {
        "gsc": {"totals": gsc_totals, "queries": gsc_queries, "pages": gsc_pages, "page_queries": gsc_page_queries or [], "gsc_start": str(gsc_start), "gsc_end": str(gsc_end)},
        "ga4": {"engagement": ga4_engagement, "channels": ga4_channels, "landing_pages": ga4_landing_pages},
        "ads": {"campaigns": ads_campaigns, "keywords": ads_keywords, "search_terms": ads_search_terms},
        "country": country,
        "pull_timestamp": ts,
    }
