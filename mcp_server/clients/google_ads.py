"""Google Ads API client (read-only)."""

import json
import logging
from datetime import date

from mcp_server import config

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        from google.ads.googleads.client import GoogleAdsClient
        if config.ADS_TOKEN:
            t = config.ADS_TOKEN
        else:
            with open(config.ADS_TOKEN_FILE) as f:
                t = json.load(f)
        _client = GoogleAdsClient.load_from_dict({
            "developer_token": config.ADS_DEV_TOKEN,
            "use_proto_plus": True,
            "client_id": t["client_id"],
            "client_secret": t["client_secret"],
            "refresh_token": t["refresh_token"],
        })
    return _client


def _query(query: str) -> list:
    from google.ads.googleads.errors import GoogleAdsException
    client = _get_client()
    ga = client.get_service("GoogleAdsService")
    rows = []
    try:
        stream = ga.search_stream(customer_id=config.ADS_CUSTOMER_ID, query=query)
        for batch in stream:
            for row in batch.results:
                rows.append(row)
    except GoogleAdsException as ex:
        logger.error(f"Google Ads API error: {ex}")
        raise
    return rows


def fetch_campaigns(start_date: date, end_date: date) -> list[dict]:
    """Fetch campaign performance data."""
    rows = _query(f"""
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
            "name": r.campaign.name,
            "status": r.campaign.status.name,
            "impressions": r.metrics.impressions,
            "clicks": r.metrics.clicks,
            "ctr": round(r.metrics.ctr, 4),
            "avg_cpc": round(r.metrics.average_cpc / 1e6, 2),
            "cost": round(r.metrics.cost_micros / 1e6, 2),
            "conversions": r.metrics.conversions,
            "impression_share": round(r.metrics.search_impression_share, 4)
            if r.metrics.search_impression_share else None,
        })
    return campaigns


def fetch_keywords(start_date: date, end_date: date, limit: int = 30) -> list[dict]:
    """Fetch keyword performance with quality scores."""
    rows = _query(f"""
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
        LIMIT {limit}
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
            "impressions": r.metrics.impressions,
            "clicks": r.metrics.clicks,
            "ctr": round(r.metrics.ctr, 4),
            "avg_cpc": round(r.metrics.average_cpc / 1e6, 2),
            "cost": round(r.metrics.cost_micros / 1e6, 2),
            "conversions": r.metrics.conversions,
        })
    return keywords


def fetch_search_terms(start_date: date, end_date: date, limit: int = 100) -> list[dict]:
    """Fetch actual search terms triggering ads."""
    rows = _query(f"""
        SELECT campaign.name, search_term_view.search_term,
            metrics.impressions, metrics.clicks, metrics.ctr,
            metrics.cost_micros, metrics.conversions
        FROM search_term_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY metrics.cost_micros DESC
        LIMIT {limit}
    """)
    search_terms = []
    for r in rows:
        search_terms.append({
            "term": r.search_term_view.search_term,
            "campaign": r.campaign.name,
            "impressions": r.metrics.impressions,
            "clicks": r.metrics.clicks,
            "ctr": round(r.metrics.ctr, 4),
            "cost": round(r.metrics.cost_micros / 1e6, 2),
            "conversions": r.metrics.conversions,
        })
    return search_terms
