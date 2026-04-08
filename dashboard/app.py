"""Zenskar Marketing Analytics Dashboard — Streamlit App."""

import sys
import os
from datetime import date, timedelta

import streamlit as st
import pandas as pd

# Load Streamlit secrets into env vars (for Streamlit Cloud deployment)
_SECRET_KEYS = ["GOOGLE_SERVICE_ACCOUNT_JSON", "GA4_PROPERTY_ID", "GSC_SITE_URL",
                "ADS_CUSTOMER_ID", "ADS_DEV_TOKEN", "ADS_TOKEN_JSON"]
for _k in _SECRET_KEYS:
    if _k not in os.environ:
        try:
            os.environ[_k] = st.secrets[_k]
        except (KeyError, FileNotFoundError):
            pass

# Ensure project root is on path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dashboard.pullers import pull_all, load_all, pull_daily_trends
from dashboard.exporter import generate_export, fmt_pct, fmt_dur
from dashboard.db import get_all_pull_dates, add_recommendation, update_recommendation, delete_recommendation, get_recommendations

st.set_page_config(page_title="Zenskar Marketing Analytics", page_icon="Z", layout="wide")

st.title("Zenskar Marketing Analytics")
# Country badge shown after data loads

# ── SIDEBAR ──────────────────────────────────────────────────

with st.sidebar:
    st.header("Date Range")

    preset = st.radio(
        "Period",
        ["Last 7 days", "Last 14 days", "Last 30 days", "Last 60 days", "Last 90 days", "Custom"],
        index=2,
    )

    today = date.today()
    if preset == "Custom":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start", today - timedelta(days=30))
        with col2:
            end_date = st.date_input("End", today)
    else:
        days = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30, "Last 60 days": 60, "Last 90 days": 90}[preset]
        end_date = today
        start_date = today - timedelta(days=days)

    # Comparison period (same length, immediately before)
    period_length = (end_date - start_date).days
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_length)

    st.caption(f"Comparing with: {prev_start} to {prev_end}")

    st.divider()

    st.header("Location")
    country = st.selectbox(
        "Filter by country",
        ["US", "Global", "UK", "Canada", "India", "Israel", "Germany", "Australia"],
        index=0,
        help="US is default (ICP focus). Switch to Global for worldwide data.",
    )

    st.divider()

    pull_clicked = st.button("Pull Fresh Data", type="primary", use_container_width=True)
    export_clicked = st.button("Export for Claude", use_container_width=True)

    st.divider()
    st.caption("**How to use the export:**")
    st.caption("1. Upload `zenskar_claude_context.md` to a Claude.ai Project")
    st.caption("2. Click 'Export for Claude' above")
    st.caption("3. Copy the export and paste into Claude.ai")

    # Pull history
    st.divider()
    st.caption("**Recent Pulls:**")
    pull_dates = get_all_pull_dates()
    if pull_dates:
        seen = set()
        for p in pull_dates[:10]:
            key = f"{p['pull_timestamp'][:16]} | {p['source']}"
            if key not in seen:
                st.caption(f"- {key} ({p['period_start']} to {p['period_end']})")
                seen.add(key)
    else:
        st.caption("No data pulled yet.")


# ── DATA LOADING ─────────────────────────────────────────────

@st.cache_data(ttl=300)
def _load(start, end, geo):
    return load_all(start, end, geo)


@st.cache_data(ttl=300)
def _load_prev(start, end, geo):
    return load_all(start, end, geo)


if pull_clicked:
    with st.spinner(f"Pulling data ({country}) from GSC, GA4, and Google Ads..."):
        data = pull_all(start_date, end_date, force=True, country=country)
        data["pull_timestamp"] = "just now"
    with st.spinner("Pulling comparison period..."):
        prev_data = pull_all(prev_start, prev_end, force=True, country=country)
    st.cache_data.clear()
    st.success(f"Data pulled and stored ({country}).")
else:
    data = _load(start_date, end_date, country)
    prev_data = _load_prev(prev_start, prev_end, country)

# ── EXPORT ───────────────────────────────────────────────────

if export_clicked and data:
    export_md = generate_export(data, start_date, end_date, prev_data, prev_start, prev_end, country=country)
    st.session_state["export_md"] = export_md

if "export_md" in st.session_state:
    st.divider()
    st.subheader("Export for Claude")
    st.text_area("Copy this and paste into Claude.ai:", st.session_state["export_md"], height=400)
    st.download_button("Download as .md", st.session_state["export_md"], file_name=f"zenskar_export_{start_date}_{end_date}.md", mime="text/markdown")
    if st.button("Close export"):
        del st.session_state["export_md"]
        st.rerun()
    st.stop()

# ── NO DATA STATE ────────────────────────────────────────────

if not data:
    st.info(f"No data found for **{start_date}** to **{end_date}** ({country}). Click **'Pull Fresh Data'** in the sidebar to fetch.")
    st.stop()

st.caption(f"Showing: **{country}** data | {start_date} to {end_date}")


# ── HELPER FUNCTIONS ─────────────────────────────────────────

def delta_val(current, previous):
    """Calculate percentage change for st.metric delta."""
    if not previous or previous == 0:
        return None
    change = ((current - previous) / abs(previous)) * 100
    return f"{change:+.1f}%"


def safe_get(d, key, default=0):
    if not d:
        return default
    return d.get(key, default)


# ── TABS ─────────────────────────────────────────────────────

tab_overview, tab_gsc, tab_ga4, tab_ads, tab_pages, tab_trends, tab_actions = st.tabs(["Overview", "Search Console", "Analytics", "Google Ads", "Page Explorer", "Trends", "Action Log"])

gsc = data.get("gsc", {})
ga4 = data.get("ga4", {})
ads = data.get("ads", {})
prev_gsc = prev_data.get("gsc", {}) if prev_data else {}
prev_ga4 = prev_data.get("ga4", {}) if prev_data else {}

# ── TAB 1: OVERVIEW ──────────────────────────────────────────

with tab_overview:
    st.subheader("Key Metrics")
    st.caption(f"Period: {start_date} to {end_date} vs {prev_start} to {prev_end}")

    eng = ga4.get("engagement", {})
    prev_eng = prev_ga4.get("engagement", {})
    gsc_totals = gsc.get("totals", {})
    prev_gsc_totals = prev_gsc.get("totals", {})
    total_spend = sum(c.get("cost", 0) for c in ads.get("campaigns", []))
    total_ad_clicks = sum(c.get("clicks", 0) for c in ads.get("campaigns", []))
    total_conv = sum(c.get("conversions", 0) for c in ads.get("campaigns", []))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("GA4 Sessions", f"{safe_get(eng, 'sessions'):,}", delta_val(safe_get(eng, 'sessions'), safe_get(prev_eng, 'sessions')))
    c2.metric("GA4 Users", f"{safe_get(eng, 'totalUsers'):,}", delta_val(safe_get(eng, 'totalUsers'), safe_get(prev_eng, 'totalUsers')))
    c3.metric("GSC Clicks", f"{safe_get(gsc_totals, 'clicks'):,}", delta_val(safe_get(gsc_totals, 'clicks'), safe_get(prev_gsc_totals, 'clicks')))
    c4.metric("GSC Impressions", f"{safe_get(gsc_totals, 'impressions'):,}", delta_val(safe_get(gsc_totals, 'impressions'), safe_get(prev_gsc_totals, 'impressions')))

    c5, c6, c7, c8 = st.columns(4)
    eng_rate = safe_get(eng, 'engagementRate', 0)
    c5.metric("Engagement Rate", fmt_pct(eng_rate))
    c6.metric("Avg Position", f"{safe_get(gsc_totals, 'position', 0):.1f}")
    c7.metric("Ads Spend", f"${total_spend:,.2f}")
    c8.metric("Ads Conversions", f"{total_conv:.0f}")

    st.divider()

    # Channel breakdown chart
    st.subheader("Traffic by Channel (GA4)")
    channels = ga4.get("channels", [])
    if channels:
        df_ch = pd.DataFrame(channels)
        if "sessionDefaultChannelGroup" in df_ch.columns and "sessions" in df_ch.columns:
            chart_data = df_ch.set_index("sessionDefaultChannelGroup")["sessions"]
            st.bar_chart(chart_data)

    # Quick organic vs paid
    st.divider()
    st.subheader("Organic vs Paid Search")
    org_clicks = safe_get(gsc_totals, "clicks", 0)
    total_search = org_clicks + total_ad_clicks
    if total_search > 0:
        c1, c2, c3 = st.columns(3)
        c1.metric("Organic Clicks", f"{org_clicks:,}", help="From Google Search Console")
        c2.metric("Paid Clicks", f"{total_ad_clicks:,}", help="From Google Ads")
        c3.metric("Organic Share", f"{org_clicks/total_search*100:.1f}%")


# ── TAB 2: GSC ───────────────────────────────────────────────

with tab_gsc:
    st.subheader(f"Google Search Console ({country})")
    st.caption(f"GSC data period: {gsc.get('gsc_start', '?')} to {gsc.get('gsc_end', '?')} (3-day data lag)")

    gsc_totals = gsc.get("totals", {})
    prev_gsc_totals = prev_gsc.get("totals", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clicks", f"{safe_get(gsc_totals, 'clicks'):,}", delta_val(safe_get(gsc_totals, 'clicks'), safe_get(prev_gsc_totals, 'clicks')))
    c2.metric("Impressions", f"{safe_get(gsc_totals, 'impressions'):,}", delta_val(safe_get(gsc_totals, 'impressions'), safe_get(prev_gsc_totals, 'impressions')))
    c3.metric("CTR", fmt_pct(safe_get(gsc_totals, 'ctr', 0)))
    c4.metric("Avg Position", f"{safe_get(gsc_totals, 'position', 0):.1f}")

    st.divider()

    # Branded vs non-branded
    queries = gsc.get("queries", [])
    branded_clicks = sum(q["clicks"] for q in queries if "zenskar" in q.get("query", "").lower())
    total_q_clicks = sum(q["clicks"] for q in queries)
    if total_q_clicks > 0:
        c1, c2 = st.columns(2)
        c1.metric("Branded Clicks", f"{branded_clicks:,} ({branded_clicks/total_q_clicks*100:.1f}%)")
        c2.metric("Non-branded Clicks", f"{total_q_clicks - branded_clicks:,} ({(total_q_clicks - branded_clicks)/total_q_clicks*100:.1f}%)")

    st.divider()

    # Top queries
    st.subheader("Top Queries")
    if queries:
        df_q = pd.DataFrame(queries).sort_values("clicks", ascending=False).head(30)
        df_q["ctr"] = df_q["ctr"].apply(lambda x: f"{x*100:.1f}%")
        df_q["position"] = df_q["position"].round(1)
        st.dataframe(df_q[["query", "clicks", "impressions", "ctr", "position"]], use_container_width=True, hide_index=True)

    # Top pages
    st.subheader("Top Pages")
    pages = gsc.get("pages", [])
    if pages:
        df_p = pd.DataFrame(pages).sort_values("clicks", ascending=False).head(20)
        df_p["page"] = df_p["page"].str.replace("https://www.zenskar.com", "", regex=False)
        df_p["ctr"] = df_p["ctr"].apply(lambda x: f"{x*100:.1f}%")
        df_p["position"] = df_p["position"].round(1)
        st.dataframe(df_p[["page", "clicks", "impressions", "ctr", "position"]], use_container_width=True, hide_index=True)


# ── TAB 3: GA4 ──────────────────────────────────────────────

with tab_ga4:
    st.subheader("Google Analytics 4")

    eng = ga4.get("engagement", {})
    prev_eng = prev_ga4.get("engagement", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sessions", f"{safe_get(eng, 'sessions'):,}", delta_val(safe_get(eng, 'sessions'), safe_get(prev_eng, 'sessions')))
    c2.metric("Users", f"{safe_get(eng, 'totalUsers'):,}", delta_val(safe_get(eng, 'totalUsers'), safe_get(prev_eng, 'totalUsers')))
    c3.metric("Engagement Rate", fmt_pct(safe_get(eng, 'engagementRate', 0)))
    c4.metric("Avg Duration", fmt_dur(safe_get(eng, 'averageSessionDuration', 0)))

    st.divider()

    # Channels
    st.subheader(f"Traffic by Channel ({country})")
    channels = ga4.get("channels", [])
    if channels:
        df_ch = pd.DataFrame(channels)
        for col in ["engagementRate", "bounceRate"]:
            if col in df_ch.columns:
                df_ch[col] = df_ch[col].apply(lambda x: f"{x*100:.1f}%" if isinstance(x, (int, float)) else x)
        if "averageSessionDuration" in df_ch.columns:
            df_ch["averageSessionDuration"] = df_ch["averageSessionDuration"].apply(fmt_dur)
        display_cols = [c for c in ["sessionDefaultChannelGroup", "sessions", "totalUsers", "newUsers", "engagementRate", "averageSessionDuration", "bounceRate", "keyEvents"] if c in df_ch.columns]
        st.dataframe(df_ch[display_cols], use_container_width=True, hide_index=True)

    st.divider()

    # Landing pages
    st.subheader(f"Top Landing Pages ({country})")
    landing_pages = ga4.get("landing_pages", [])
    if landing_pages:
        df_lp = pd.DataFrame(landing_pages)
        for col in ["engagementRate", "bounceRate"]:
            if col in df_lp.columns:
                df_lp[col] = df_lp[col].apply(lambda x: f"{x*100:.1f}%" if isinstance(x, (int, float)) else x)
        display_cols = [c for c in ["landingPagePlusQueryString", "sessions", "totalUsers", "engagementRate", "bounceRate", "keyEvents"] if c in df_lp.columns]
        st.dataframe(df_lp[display_cols].head(20), use_container_width=True, hide_index=True)


# ── TAB 4: GOOGLE ADS ───────────────────────────────────────

with tab_ads:
    st.subheader("Google Ads — Paid Search")

    campaigns = ads.get("campaigns", [])
    total_spend = sum(c.get("cost", 0) for c in campaigns)
    total_clicks = sum(c.get("clicks", 0) for c in campaigns)
    total_imp = sum(c.get("impressions", 0) for c in campaigns)
    total_conv = sum(c.get("conversions", 0) for c in campaigns)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Spend", f"${total_spend:,.2f}")
    c2.metric("Total Clicks", f"{total_clicks:,}")
    c3.metric("Avg CPC", f"${total_spend/total_clicks:.2f}" if total_clicks else "N/A")
    c4.metric("Conversions", f"{total_conv:.0f}")

    st.divider()

    # Campaigns
    st.subheader("Campaign Performance")
    if campaigns:
        df_c = pd.DataFrame(campaigns)
        df_c["ctr"] = df_c["ctr"].apply(lambda x: f"{x*100:.1f}%")
        df_c["cost"] = df_c["cost"].apply(lambda x: f"${x:,.2f}")
        df_c["avg_cpc"] = df_c["avg_cpc"].apply(lambda x: f"${x:.2f}")
        df_c["impression_share"] = df_c["impression_share"].apply(lambda x: f"{x*100:.0f}%" if x else "N/A")
        st.dataframe(df_c[["name", "status", "impressions", "clicks", "ctr", "cost", "avg_cpc", "impression_share", "conversions"]], use_container_width=True, hide_index=True)

    st.divider()

    # Keywords with quality scores
    st.subheader("Keywords & Quality Scores")
    keywords = ads.get("keywords", [])
    if keywords:
        df_kw = pd.DataFrame(keywords)
        df_kw["quality_score"] = df_kw["quality_score"].apply(lambda x: f"{x}/10" if x else "N/A")
        df_kw["ctr"] = df_kw["ctr"].apply(lambda x: f"{x*100:.1f}%")
        df_kw["cost"] = df_kw["cost"].apply(lambda x: f"${x:,.2f}")
        df_kw["avg_cpc"] = df_kw["avg_cpc"].apply(lambda x: f"${x:.2f}")
        # Only show rows with impressions or spend
        df_kw_active = df_kw[(df_kw["impressions"] > 0) | (df_kw["cost"] != "$0.00")]
        st.dataframe(df_kw_active[["keyword", "match_type", "quality_score", "creative_quality", "landing_page_quality", "predicted_ctr", "clicks", "cost", "conversions"]], use_container_width=True, hide_index=True)

        # Show inactive keywords separately
        df_kw_inactive = df_kw[(df_kw["impressions"] == 0) & (df_kw["cost"] == "$0.00")]
        if not df_kw_inactive.empty:
            with st.expander(f"Inactive keywords ({len(df_kw_inactive)})"):
                st.dataframe(df_kw_inactive[["keyword", "match_type", "campaign"]], use_container_width=True, hide_index=True)

    st.divider()

    # Search terms with waste flagging
    st.subheader("Search Terms")
    search_terms = ads.get("search_terms", [])
    if search_terms:
        irrelevant_indicators = ["appzen", "rillion", "docyt", "ap automation", "e billing",
                                 "e-billing", "accounts payable", "payroll", "invoice factoring",
                                 "invoice financing", "online billing platform", "the billing platform"]
        relevant_indicators = ["zuora", "tabs", "billing platform", "billingplatform",
                               "maxio", "chargify", "recurly", "stripe billing",
                               "chargebee", "metronome", "ordway", "billing software",
                               "revenue recognition", "revrec", "revpro", "usage based billing",
                               "saas billing", "zenskar"]

        for st_item in search_terms:
            term_lower = st_item["term"].lower()
            if "zenskar" in term_lower:
                st_item["flag"] = "Branded"
            elif any(i in term_lower for i in irrelevant_indicators):
                st_item["flag"] = "IRRELEVANT"
            elif any(r in term_lower for r in relevant_indicators):
                st_item["flag"] = "Relevant"
            else:
                st_item["flag"] = "Review"

        df_st = pd.DataFrame(search_terms)
        df_st["ctr"] = df_st["ctr"].apply(lambda x: f"{x*100:.1f}%")
        df_st["cost"] = df_st["cost"].apply(lambda x: f"${x:,.2f}")

        # Summary
        wasted = [s for s in search_terms if s["flag"] == "IRRELEVANT"]
        wasted_cost = sum(s["cost"] for s in wasted if isinstance(s["cost"], (int, float)))
        if wasted:
            st.warning(f"**{len(wasted)} irrelevant search terms** found — ${wasted_cost:,.2f} wasted spend")

        st.dataframe(df_st[["term", "campaign", "clicks", "impressions", "ctr", "cost", "conversions", "flag"]], use_container_width=True, hide_index=True)

    st.divider()

    # Paid vs organic overlap
    st.subheader("Paid vs Organic Overlap")
    gsc_queries = gsc.get("queries", [])
    if keywords and gsc_queries:
        gsc_map = {q["query"].lower(): q for q in gsc_queries}
        overlap_rows = []
        for kw in keywords:
            if kw.get("impressions", 0) == 0 and kw.get("cost", 0) == 0:
                continue
            kw_lower = kw["keyword"].lower()
            org = gsc_map.get(kw_lower)
            if not org:
                for oq, od in gsc_map.items():
                    if kw_lower in oq or oq in kw_lower:
                        org = od
                        break
            overlap_rows.append({
                "Paid Keyword": kw["keyword"],
                "Paid Clicks": kw["clicks"],
                "Paid Spend": f"${kw['cost']:,.2f}",
                "Organic Clicks": org["clicks"] if org else 0,
                "Organic Impressions": org["impressions"] if org else 0,
                "Organic Position": f"{org['position']:.1f}" if org else "N/A",
            })
        if overlap_rows:
            st.dataframe(pd.DataFrame(overlap_rows), use_container_width=True, hide_index=True)


# ── TAB 5: PAGE EXPLORER ───────────────────────────────────

with tab_pages:
    st.subheader("Page Explorer")
    st.caption("Select a page to see all its metrics in one view — GSC search performance + GA4 engagement + top queries driving traffic.")

    # Build page list from GSC pages data (sorted by clicks)
    gsc_pages_list = sorted(gsc.get("pages", []), key=lambda x: x.get("clicks", 0), reverse=True)
    ga4_lp_list = ga4.get("landing_pages", [])
    page_queries_data = gsc.get("page_queries", [])
    prev_gsc_pages = prev_gsc.get("pages", []) if prev_gsc else []
    prev_ga4_lp = prev_ga4.get("landing_pages", []) if prev_ga4 else []

    if not gsc_pages_list:
        st.info("No page data available. Pull fresh data first.")
    else:
        # Dropdown with page paths
        page_options = []
        for p in gsc_pages_list:
            path = p.get("page", "").replace("https://www.zenskar.com", "")
            if path:
                page_options.append(path)

        selected_path = st.selectbox(
            "Select a page",
            page_options,
            format_func=lambda x: f"{x}  ({next((p['clicks'] for p in gsc_pages_list if p.get('page', '').endswith(x)), 0)} clicks)",
        )

        if selected_path:
            full_url = f"https://www.zenskar.com{selected_path}"

            # Find GSC data for this page
            page_gsc = next((p for p in gsc_pages_list if p.get("page") == full_url), {})
            prev_page_gsc = next((p for p in prev_gsc_pages if p.get("page") == full_url), {})

            # Find GA4 data — match on path
            page_ga4 = next((lp for lp in ga4_lp_list if lp.get("landingPagePlusQueryString", "").rstrip("/") == selected_path.rstrip("/")), {})
            prev_page_ga4 = next((lp for lp in prev_ga4_lp if lp.get("landingPagePlusQueryString", "").rstrip("/") == selected_path.rstrip("/")), {})

            # ── GSC Metrics ──
            st.divider()
            st.subheader("Search Performance (GSC)")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Clicks", f"{page_gsc.get('clicks', 0):,}", delta_val(page_gsc.get('clicks', 0), prev_page_gsc.get('clicks')))
            c2.metric("Impressions", f"{page_gsc.get('impressions', 0):,}", delta_val(page_gsc.get('impressions', 0), prev_page_gsc.get('impressions')))
            c3.metric("CTR", fmt_pct(page_gsc.get('ctr', 0)))
            c4.metric("Avg Position", f"{page_gsc.get('position', 0):.1f}")

            # ── GA4 Metrics ──
            st.divider()
            st.subheader("Engagement (GA4)")
            if page_ga4:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Sessions", f"{page_ga4.get('sessions', 0):,}", delta_val(page_ga4.get('sessions', 0), prev_page_ga4.get('sessions')))
                c2.metric("Users", f"{page_ga4.get('totalUsers', 0):,}", delta_val(page_ga4.get('totalUsers', 0), prev_page_ga4.get('totalUsers')))
                c3.metric("Engagement Rate", fmt_pct(page_ga4.get('engagementRate', 0)))
                c4.metric("Bounce Rate", fmt_pct(page_ga4.get('bounceRate', 0)))

                c5, c6 = st.columns(2)
                c5.metric("Key Events", f"{page_ga4.get('keyEvents', 0)}")
                avg_dur = page_ga4.get('averageSessionDuration', 0)
                if avg_dur:
                    c6.metric("Avg Duration", fmt_dur(avg_dur))
            else:
                st.caption("No GA4 landing page data for this page in the selected period.")

            # ── Top Queries for this Page ──
            st.divider()
            st.subheader("Top Queries Driving Traffic to This Page")
            if page_queries_data:
                queries_for_page = [pq for pq in page_queries_data if pq.get("page") == full_url]
                queries_for_page.sort(key=lambda x: x.get("clicks", 0), reverse=True)

                if queries_for_page:
                    df_pq = pd.DataFrame(queries_for_page).head(25)
                    df_pq["ctr"] = df_pq["ctr"].apply(lambda x: f"{x*100:.1f}%")
                    df_pq["position"] = df_pq["position"].round(1)
                    st.dataframe(df_pq[["query", "clicks", "impressions", "ctr", "position"]], use_container_width=True, hide_index=True)

                    # Insights
                    high_imp_low_ctr = [q for q in queries_for_page if q.get("impressions", 0) > 50 and q.get("ctr", 0) < 0.03]
                    if high_imp_low_ctr:
                        st.divider()
                        st.subheader("Optimization Opportunities")
                        st.caption("Queries with high impressions but low CTR (<3%) — potential title/meta description improvements:")
                        df_opp = pd.DataFrame(high_imp_low_ctr).sort_values("impressions", ascending=False).head(10)
                        df_opp["ctr"] = df_opp["ctr"].apply(lambda x: f"{x*100:.1f}%")
                        df_opp["position"] = df_opp["position"].round(1)
                        st.dataframe(df_opp[["query", "clicks", "impressions", "ctr", "position"]], use_container_width=True, hide_index=True)
                else:
                    st.caption("No query-level data available for this page.")
            else:
                st.caption("Page query data not available. Pull fresh data to populate.")


# ── TAB 6: TRENDS ──────────────────────────────────────────

with tab_trends:
    st.subheader("Trends")
    st.caption(f"Daily metrics for {start_date} to {end_date} ({country})")

    # Load daily trend data
    from dashboard.db import get_latest_pull as _get_pull
    from dashboard.pullers import _gsc_dates
    _gsc_s, _gsc_e = _gsc_dates(start_date, end_date)
    _gsc_src = f"gsc_{country.lower()}"
    _ga4_src = f"ga4_{country.lower()}"
    gsc_daily, _ = _get_pull(_gsc_src, "daily", _gsc_s, _gsc_e)
    ga4_daily, _ = _get_pull(_ga4_src, "daily", start_date, end_date)

    if not gsc_daily and not ga4_daily:
        st.info("No trend data available. Click **Pull Fresh Data** to fetch daily breakdowns.")
    else:
        # GSC daily trends
        if gsc_daily:
            st.subheader("Organic Search (GSC)")
            df_gsc_d = pd.DataFrame(gsc_daily).sort_values("date")
            df_gsc_d["date"] = pd.to_datetime(df_gsc_d["date"])
            df_gsc_d = df_gsc_d.set_index("date")

            c1, c2 = st.columns(2)
            with c1:
                st.caption("Clicks")
                st.line_chart(df_gsc_d["clicks"])
            with c2:
                st.caption("Impressions")
                st.line_chart(df_gsc_d["impressions"])

            c3, c4 = st.columns(2)
            with c3:
                st.caption("CTR")
                st.line_chart(df_gsc_d["ctr"])
            with c4:
                st.caption("Avg Position")
                st.line_chart(df_gsc_d["position"])

        st.divider()

        # GA4 daily trends
        if ga4_daily:
            st.subheader("Site Engagement (GA4)")
            df_ga4_d = pd.DataFrame(ga4_daily).sort_values("date")
            # GA4 date format is YYYYMMDD
            df_ga4_d["date"] = pd.to_datetime(df_ga4_d["date"], format="%Y%m%d")
            df_ga4_d = df_ga4_d.set_index("date")

            c1, c2 = st.columns(2)
            with c1:
                st.caption("Sessions")
                st.line_chart(df_ga4_d["sessions"])
            with c2:
                st.caption("Users")
                st.line_chart(df_ga4_d["totalUsers"])

            c3, c4 = st.columns(2)
            with c3:
                st.caption("Engagement Rate")
                st.line_chart(df_ga4_d["engagementRate"])
            with c4:
                st.caption("Bounce Rate")
                st.line_chart(df_ga4_d["bounceRate"])


# ── TAB 7: ACTION LOG ──────────────────────────────────────

with tab_actions:
    st.subheader("Action Log")
    st.caption("Track recommendations from Claude analyses. Add actions, mark as done, note outcomes. This history is included in future exports so Claude can build on prior analysis.")

    # Add new recommendation
    with st.expander("Add New Recommendation", expanded=False):
        with st.form("add_rec", clear_on_submit=True):
            rec_text = st.text_area("Recommendation", placeholder="e.g., Add negative keyword 'freelancer billing' to Brand campaign")
            col1, col2 = st.columns(2)
            with col1:
                rec_category = st.selectbox("Category", ["ads", "seo", "content", "landing_page", "general"])
            with col2:
                rec_priority = st.selectbox("Priority", ["immediate", "this_week", "this_month", "next_quarter"])
            submitted = st.form_submit_button("Add", type="primary")
            if submitted and rec_text.strip():
                add_recommendation(rec_text.strip(), rec_category, rec_priority)
                st.success("Added!")
                st.rerun()

    st.divider()

    # Display recommendations
    recs = get_recommendations()
    if not recs:
        st.info("No recommendations logged yet. Add one above, or paste recommendations from a Claude analysis.")
    else:
        # Summary counts
        pending = [r for r in recs if r["status"] == "pending"]
        done = [r for r in recs if r["status"] == "done"]
        skipped = [r for r in recs if r["status"] == "skipped"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Pending", len(pending))
        c2.metric("Done", len(done))
        c3.metric("Skipped", len(skipped))

        st.divider()

        for rec in recs:
            with st.container():
                # Status indicator
                status_icon = {"pending": "[ ]", "done": "[x]", "skipped": "[-]"}.get(rec["status"], "?")
                priority_badge = {"immediate": "NOW", "this_week": "This Week", "this_month": "This Month", "next_quarter": "Next Qtr"}.get(rec["priority"], "")

                col1, col2, col3, col4 = st.columns([0.5, 0.15, 0.15, 0.2])
                with col1:
                    st.markdown(f"**{status_icon} {rec['recommendation']}**")
                    st.caption(f"{rec['category'].upper()} | {priority_badge} | Added: {rec['created_date'][:10]}")
                    if rec.get("outcome"):
                        st.caption(f"Outcome: {rec['outcome']}")
                with col2:
                    if rec["status"] != "done":
                        if st.button("Done", key=f"done_{rec['id']}"):
                            update_recommendation(rec["id"], status="done")
                            st.rerun()
                with col3:
                    if rec["status"] == "pending":
                        if st.button("Skip", key=f"skip_{rec['id']}"):
                            update_recommendation(rec["id"], status="skipped")
                            st.rerun()
                with col4:
                    outcome_text = st.text_input("Outcome", value=rec.get("outcome", ""), key=f"outcome_{rec['id']}", label_visibility="collapsed", placeholder="What happened?")
                    if outcome_text != (rec.get("outcome") or ""):
                        update_recommendation(rec["id"], outcome=outcome_text)

                st.divider()
