"""Generate markdown exports optimized for pasting into Claude.ai."""

from datetime import date
from dashboard.db import get_recommendations


def fmt_pct(val):
    if isinstance(val, (int, float)):
        return f"{val*100:.1f}%" if val < 1 else f"{val:.1f}%"
    return str(val)


def fmt_dur(seconds):
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return str(seconds)
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"


def generate_export(data: dict, start_date: date, end_date: date, prev_data: dict | None = None, prev_start: date | None = None, prev_end: date | None = None, country: str = "US") -> str:
    lines = []
    w = lines.append

    w("# Zenskar Marketing Data Export")
    w(f"**Period:** {start_date} to {end_date}")
    if prev_start:
        w(f"**Comparison Period:** {prev_start} to {prev_end}")
    w(f"**Geo Filter:** {country}")
    w("")
    w("> Use this with the **Zenskar Analysis Context** document for best results.")
    w("> Upload that document to your Claude.ai Project, then paste this export into a conversation.")
    w("")

    gsc = data.get("gsc", {})
    ga4 = data.get("ga4", {})
    ads = data.get("ads", {})
    prev_gsc = prev_data.get("gsc", {}) if prev_data else {}
    prev_ga4 = prev_data.get("ga4", {}) if prev_data else {}

    # ── OVERVIEW ──
    w("---")
    w("## Overview")
    w("")

    eng = ga4.get("engagement", {})
    prev_eng = prev_ga4.get("engagement", {})
    gsc_totals = gsc.get("totals", {})
    prev_gsc_totals = prev_gsc.get("totals", {})
    total_spend = sum(c.get("cost", 0) for c in ads.get("campaigns", []))
    total_clicks = sum(c.get("clicks", 0) for c in ads.get("campaigns", []))
    total_conv = sum(c.get("conversions", 0) for c in ads.get("campaigns", []))

    w("| Metric | Current Period | Previous Period |")
    w("|--------|---------------|-----------------|")
    _metric_row(w, "GA4 Sessions", eng.get("sessions"), prev_eng.get("sessions"))
    _metric_row(w, "GA4 Users", eng.get("totalUsers"), prev_eng.get("totalUsers"))
    _metric_row(w, "GA4 New Users", eng.get("newUsers"), prev_eng.get("newUsers"))
    _metric_row(w, "GA4 Engagement Rate", eng.get("engagementRate"), prev_eng.get("engagementRate"), is_pct=True)
    _metric_row(w, "GA4 Bounce Rate", eng.get("bounceRate"), prev_eng.get("bounceRate"), is_pct=True)
    _metric_row(w, "GA4 Avg Session Duration", eng.get("averageSessionDuration"), prev_eng.get("averageSessionDuration"), is_dur=True)
    _metric_row(w, "GSC Clicks", gsc_totals.get("clicks"), prev_gsc_totals.get("clicks"))
    _metric_row(w, "GSC Impressions", gsc_totals.get("impressions"), prev_gsc_totals.get("impressions"))
    _metric_row(w, "GSC Avg CTR", gsc_totals.get("ctr"), prev_gsc_totals.get("ctr"), is_pct=True)
    _metric_row(w, "GSC Avg Position", gsc_totals.get("position"), prev_gsc_totals.get("position"), fmt_fn=lambda v: f"{v:.1f}")
    w(f"| Google Ads Spend | ${total_spend:,.2f} | — |")
    w(f"| Google Ads Clicks | {total_clicks:,} | — |")
    w(f"| Google Ads Conversions | {total_conv:.0f} | — |")
    w("")

    # ── GA4 CHANNELS ──
    w("---")
    w(f"## GA4 — {country} Traffic by Channel")
    w("")
    w("| Channel | Sessions | Users | Engagement Rate | Avg Duration | Bounce Rate |")
    w("|---------|----------|-------|-----------------|-------------|-------------|")
    for ch in ga4.get("channels", []):
        w(f"| {ch.get('sessionDefaultChannelGroup', '?')} | {ch.get('sessions', 0):,} | {ch.get('totalUsers', 0):,} | {fmt_pct(ch.get('engagementRate', 0))} | {fmt_dur(ch.get('averageSessionDuration', 0))} | {fmt_pct(ch.get('bounceRate', 0))} |")
    w("")

    # Landing pages
    w(f"### {country} Top Landing Pages")
    w("")
    w("| Landing Page | Sessions | Users | Engagement Rate | Bounce Rate | Key Events |")
    w("|-------------|----------|-------|-----------------|-------------|------------|")
    for lp in ga4.get("landing_pages", [])[:20]:
        path = lp.get("landingPagePlusQueryString", "?")
        if len(path) > 60:
            path = path[:57] + "..."
        w(f"| {path} | {lp.get('sessions', 0):,} | {lp.get('totalUsers', 0):,} | {fmt_pct(lp.get('engagementRate', 0))} | {fmt_pct(lp.get('bounceRate', 0))} | {lp.get('keyEvents', 0)} |")
    w("")

    # ── GSC ──
    w("---")
    w("## Google Search Console — Organic Search")
    w(f"*GSC data period: {gsc.get('gsc_start', '?')} to {gsc.get('gsc_end', '?')} (3-day data lag)*")
    w("")

    queries = gsc.get("queries", [])
    branded_patterns = ["zenskar"]
    branded_clicks = sum(q["clicks"] for q in queries if any(bp in q.get("query", "").lower() for bp in branded_patterns))
    total_q_clicks = sum(q["clicks"] for q in queries)
    if total_q_clicks > 0:
        w(f"**Branded clicks:** {branded_clicks:,} ({branded_clicks/total_q_clicks*100:.1f}%)")
        w(f"**Non-branded clicks:** {total_q_clicks - branded_clicks:,} ({(total_q_clicks - branded_clicks)/total_q_clicks*100:.1f}%)")
        w("")

    w("### Top Queries by Clicks")
    w("")
    w("| Query | Clicks | Impressions | CTR | Avg Position |")
    w("|-------|--------|-------------|-----|-------------|")
    sorted_queries = sorted(queries, key=lambda x: x.get("clicks", 0), reverse=True)
    for q in sorted_queries[:25]:
        w(f"| {q.get('query', '?')} | {q['clicks']:,} | {q['impressions']:,} | {fmt_pct(q['ctr'])} | {q['position']:.1f} |")
    w("")

    w("### Top Pages by Clicks")
    w("")
    w("| Page | Clicks | Impressions | CTR | Avg Position |")
    w("|------|--------|-------------|-----|-------------|")
    sorted_pages = sorted(gsc.get("pages", []), key=lambda x: x.get("clicks", 0), reverse=True)
    for p in sorted_pages[:20]:
        page_path = p.get("page", "?").replace("https://www.zenskar.com", "")
        if len(page_path) > 65:
            page_path = page_path[:62] + "..."
        w(f"| {page_path} | {p['clicks']:,} | {p['impressions']:,} | {fmt_pct(p['ctr'])} | {p['position']:.1f} |")
    w("")

    # ── GOOGLE ADS ──
    w("---")
    w("## Google Ads — Paid Search")
    w("")
    avg_cpc = f"${total_spend/total_clicks:.2f}" if total_clicks else "N/A"
    w(f"**Total:** ${total_spend:,.2f} spend | {total_clicks} clicks | {avg_cpc} avg CPC | {total_conv:.0f} conversions")
    w("")

    w("### Campaign Performance")
    w("")
    w("| Campaign | Status | Impressions | Clicks | CTR | Spend | Avg CPC | Imp Share | Conv |")
    w("|----------|--------|-------------|--------|-----|-------|---------|-----------|------|")
    for c in ads.get("campaigns", []):
        imp_share = f"{c['impression_share']*100:.0f}%" if c.get("impression_share") else "N/A"
        w(f"| {c['name']} | {c['status']} | {c['impressions']:,} | {c['clicks']:,} | {fmt_pct(c['ctr'])} | ${c['cost']:,.2f} | ${c['avg_cpc']:.2f} | {imp_share} | {c['conversions']:.0f} |")
    w("")

    w("### Keywords with Quality Scores")
    w("")
    w("| Keyword | Match | QS | Ad Relevance | Landing Page | Pred CTR | Clicks | Spend | Conv |")
    w("|---------|-------|----|-------------|-------------|---------|--------|-------|------|")
    for kw in ads.get("keywords", []):
        if kw.get("impressions", 0) > 0 or kw.get("cost", 0) > 0:
            qs = f"{kw['quality_score']}/10" if kw.get("quality_score") else "N/A"
            w(f"| {kw['keyword']} | {kw['match_type']} | {qs} | {kw.get('creative_quality', 'N/A')} | {kw.get('landing_page_quality', 'N/A')} | {kw.get('predicted_ctr', 'N/A')} | {kw['clicks']} | ${kw['cost']:,.2f} | {kw['conversions']:.0f} |")
    w("")

    w("### Search Terms (What People Actually Typed)")
    w("")
    w("| Search Term | Campaign | Clicks | Impressions | CTR | Cost | Conv |")
    w("|-------------|----------|--------|-------------|-----|------|------|")
    for st in ads.get("search_terms", [])[:30]:
        w(f"| {st['term']} | {st['campaign'][:35]} | {st['clicks']} | {st['impressions']:,} | {fmt_pct(st['ctr'])} | ${st['cost']:,.2f} | {st['conversions']:.0f} |")
    w("")

    # ── CROSS-CHANNEL ──
    w("---")
    w("## Cross-Channel: Paid vs Organic Overlap")
    w("")
    gsc_query_map = {q["query"].lower(): q for q in queries}
    w("| Paid Keyword | Paid Clicks | Paid Spend | Organic Clicks | Organic Impressions | Organic Position |")
    w("|-------------|------------|-----------|----------------|--------------------|-----------------:|")
    for kw in ads.get("keywords", []):
        kw_lower = kw["keyword"].lower()
        org = gsc_query_map.get(kw_lower)
        if not org:
            for oq, od in gsc_query_map.items():
                if kw_lower in oq or oq in kw_lower:
                    org = od
                    break
        org_clicks = org["clicks"] if org else 0
        org_imp = org["impressions"] if org else 0
        org_pos = f"{org['position']:.1f}" if org else "N/A"
        w(f"| {kw['keyword']} | {kw['clicks']} | ${kw['cost']:,.2f} | {org_clicks} | {org_imp:,} | {org_pos} |")
    w("")

    # ── RECOMMENDATIONS HISTORY ──
    recs = get_recommendations()
    if recs:
        w("---")
        w("## Prior Recommendations & Status")
        w("")
        w("These are actions from previous analyses. Reference them in your analysis — build on what worked, flag stalled items, and avoid re-recommending completed actions.")
        w("")
        w("| Date | Recommendation | Category | Priority | Status | Outcome |")
        w("|------|---------------|----------|----------|--------|---------|")
        for rec in recs:
            outcome = rec.get("outcome", "") or ""
            w(f"| {rec['created_date'][:10]} | {rec['recommendation']} | {rec['category']} | {rec['priority']} | **{rec['status'].upper()}** | {outcome} |")
        w("")
        pending_count = sum(1 for r in recs if r["status"] == "pending")
        done_count = sum(1 for r in recs if r["status"] == "done")
        if pending_count:
            w(f"*{pending_count} actions still pending. {done_count} completed.*")
            w("")

    # ── PROMPT ──
    w("---")
    w("## Analysis Instructions")
    w("")
    w("You are a B2B SaaS marketing analyst for Zenskar. Analyze this data thoroughly using the Zenskar Analysis Context document you have in your project knowledge.")
    w("")
    w("### 1. Executive Summary (3-5 bullets)")
    w("- Headline metrics: total sessions, organic clicks, paid spend, conversions")
    w("- Biggest win and biggest concern this period")
    w(f"- If comparison data is included, highlight the most significant period-over-period changes")
    w("")
    w("### 2. Organic Search Health (GSC)")
    w("- **Branded vs non-branded split** — what % of organic clicks are branded? Is brand awareness growing?")
    w("- **High-impression, low-CTR queries** — which keywords have strong visibility but poor click-through? These are title/meta description optimization opportunities")
    w("- **Position movement** — any queries climbing or falling significantly?")
    w("- **Page performance** — which pages drive the most organic traffic? Any pages with high impressions but low clicks?")
    w("- **Content gaps** — based on the query data, what topics is Zenskar ranking for weakly or not at all that relate to our ICP (finance leaders at B2B SaaS companies)?")
    w("")
    w("### 3. Site Engagement (GA4)")
    w("- **Channel quality** — which channels drive the most engaged traffic (high engagement rate, low bounce rate, long sessions)?")
    w("- **Channel red flags** — any channels with high traffic but poor engagement? These may be attracting wrong-fit visitors")
    w("- **Landing page effectiveness** — which landing pages convert well vs. which have high bounce rates?")
    w("- **Key events** — which channels/pages drive the most key events (demo requests, sign-ups)?")
    w("")
    w("### 4. Paid Search Assessment (Google Ads)")
    w("- **Budget efficiency** — cost per conversion, overall ROAS assessment")
    w("- **Quality Score analysis** — which keywords have low QS? Break down the components (ad relevance, landing page, predicted CTR) and recommend specific fixes")
    w("- **Search term audit** — identify wasted spend on irrelevant search terms. Flag terms that don't match Zenskar's ICP (e.g., B2C billing, invoicing for freelancers, unrelated SaaS tools)")
    w("- **Campaign structure** — are campaigns well-organized? Any overlap or cannibalization?")
    w("- **Impression share** — where are we losing impression share? Is it budget or rank?")
    w("")
    w("### 5. Cross-Channel: Paid vs Organic Overlap")
    w("- For keywords where we rank organically AND pay for ads: should we keep paying, or can we rely on organic?")
    w("- Rule of thumb: if organic position is 1-3 AND organic CTR is strong, consider pausing paid for that keyword")
    w("- If organic position is 4+, paid likely still adds incremental value")
    w("- Flag any keywords where we're paying for clicks but have zero organic presence (content opportunity)")
    w("")
    w("### 6. ICP Alignment Check")
    w(f"- **Geo filter applied:** {country}")
    w("- Are we attracting the right audience? Zenskar's ICP: B2B SaaS/XaaS companies, 150-1500 employees, finance/accounting buyers")
    w("- Flag any traffic or search terms that suggest non-ICP visitors (B2C, freelancer, very small business, wrong industry)")
    w("- Assess whether our content and ads speak to CFOs/Controllers/VP Finance or to developers/engineers (we want finance buyers)")
    w("")
    w("### 7. Prioritized Action Plan")
    w("Organize recommendations by urgency:")
    w("- **Do Today** — quick wins, obvious fixes (negative keywords, pause wasteful terms)")
    w("- **This Week** — tactical improvements (ad copy, landing page tweaks, meta descriptions)")
    w("- **This Month** — strategic initiatives (new content, campaign restructuring, landing page rebuilds)")
    w("- **Next Quarter** — longer-term bets (new keyword verticals, content hubs, competitive positioning)")
    w("")
    w("### Formatting")
    w("- Use tables for comparisons")
    w("- Bold key numbers and takeaways")
    w("- Be specific — don't say 'improve Quality Score', say which keyword, which component, and what to do")
    w("- Include estimated impact where possible (e.g., 'fixing landing page for X keyword could save ~$Y/month')")
    w("")

    return "\n".join(lines)


def _metric_row(w, label, current, previous, is_pct=False, is_dur=False, fmt_fn=None):
    if current is None:
        current = 0
    if fmt_fn:
        cur_str = fmt_fn(current)
        prev_str = fmt_fn(previous) if previous else "—"
    elif is_pct:
        cur_str = fmt_pct(current)
        prev_str = fmt_pct(previous) if previous else "—"
    elif is_dur:
        cur_str = fmt_dur(current)
        prev_str = fmt_dur(previous) if previous else "—"
    elif isinstance(current, float):
        cur_str = f"{current:,.2f}"
        prev_str = f"{previous:,.2f}" if previous else "—"
    else:
        cur_str = f"{current:,}" if isinstance(current, int) else str(current)
        prev_str = f"{previous:,}" if isinstance(previous, int) else (str(previous) if previous else "—")
    w(f"| {label} | {cur_str} | {prev_str} |")
