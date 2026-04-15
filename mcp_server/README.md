# Zenskar Marketing Analytics MCP Server

MCP server providing read-only access to Zenskar's marketing analytics stack:

- **Google Search Console** — organic search performance (queries, pages, CTR, position)
- **Google Analytics 4** — site engagement, traffic channels, landing pages
- **Google Ads** — campaign performance, keyword quality scores, search terms
- **HubSpot CRM** — deals, companies, contacts, activity, page visit journeys
- **Bing Webmaster Tools** — Bing search queries and pages

---

## Option A: Deploy to Render (free) + use from Claude.ai web

This is the easiest way to share with your team — deploy once, everyone uses it from claude.ai.

### 1. Push to GitHub

Make sure the repo is pushed to GitHub (don't push `.env` or `credentials.json`).

### 2. Deploy on Render

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repo
3. Render auto-detects `render.yaml` — it will configure everything
4. Add these **environment variables** in Render dashboard (marked as Secret):

| Variable | Value |
|----------|-------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Paste the entire `credentials.json` content as a string |
| `GA4_PROPERTY_ID` | `428507848` |
| `ADS_CUSTOMER_ID` | `5860587550` |
| `ADS_DEV_TOKEN` | Your Google Ads dev token |
| `ADS_TOKEN_JSON` | Paste the entire `google_ads_token.json` content as a string |
| `HUBSPOT_PAT` | Your HubSpot Personal Access Token |
| `BING_API_KEY` | Your Bing Webmaster API key |

5. Deploy — you'll get a URL like `https://zenskar-mcp.onrender.com`

### 3. Add to Claude.ai (for your whole team)

1. Go to [claude.ai](https://claude.ai) → **Settings** → **Integrations**
2. Click **Add Integration** → **MCP Server**
3. Enter your Render URL: `https://zenskar-mcp.onrender.com/sse`
4. Save

Now every conversation on claude.ai can use the 19 marketing tools. Share the integration with your team via Claude.ai's team settings.

> **Note:** Render free tier spins down after 15 min of inactivity. The first request after idle takes ~30s to cold-start. Subsequent requests are instant.

---

## Option B: Claude Desktop (local, per-machine)

### 1. Clone + install

```bash
git clone <repo-url>
cd "Zenskar Demo Analysis"
pip install -e .
```

### 2. Set up credentials

```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Add to Claude Desktop

**Windows:** Edit `%APPDATA%\Claude\claude_desktop_config.json`
**Mac:** Edit `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "zenskar-marketing": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "D:\\Projects\\Zenskar Demo Analysis",
      "env": {
        "DOTENV_PATH": "D:\\Projects\\Zenskar Demo Analysis\\.env"
      }
    }
  }
}
```

Restart Claude Desktop. Tools appear automatically.

---

## Option C: Claude Code (local, per-project)

The `.mcp.json` in the repo root already configures this. Just open the project in Claude Code.

---

## Available Tools (19)

### Google Search Console
| Tool | Description |
|------|-------------|
| `gsc_search_analytics` | Search analytics by query/page/date/device/country with pagination |
| `gsc_totals` | Aggregate clicks, impressions, CTR, position |
| `gsc_compare_periods` | Compare two date ranges side-by-side |

### Google Analytics 4
| Tool | Description |
|------|-------------|
| `ga4_site_engagement` | Sessions, users, engagement rate, bounce rate |
| `ga4_channel_breakdown` | Traffic by channel (Organic, Paid, Direct, etc.) |
| `ga4_top_pages` | Top landing pages by sessions |
| `ga4_report` | Custom report with any GA4 metrics/dimensions |

### Google Ads
| Tool | Description |
|------|-------------|
| `ads_campaigns` | Campaign performance with cost, conversions, impression share |
| `ads_keywords` | Keyword performance with quality scores |
| `ads_search_terms` | Actual search terms triggering your ads |

### HubSpot (all read-only)
| Tool | Description |
|------|-------------|
| `hubspot_search_deals` | Search deals with filters (stage, source, date) |
| `hubspot_get_company` | Get company properties by ID |
| `hubspot_get_contact` | Get contact properties by ID |
| `hubspot_get_deal` | Get deal properties by ID |
| `hubspot_company_contacts` | Get contacts associated with a company |
| `hubspot_company_activity` | Get notes and meetings for a company |
| `hubspot_contact_journey` | Get page visit history for a contact |

### Bing Webmaster Tools
| Tool | Description |
|------|-------------|
| `bing_top_queries` | Top Bing search queries (US traffic) |
| `bing_top_pages` | Top Bing pages by clicks |

## Usage Examples

Once connected, just ask Claude naturally:

- "What were our top 10 GSC queries last week?"
- "Show me GA4 organic traffic for the US this month"
- "How are our Google Ads campaigns performing?"
- "Find all HubSpot deals created this month with source Inbound - Organic"
- "Get the page visit journey for contact 12345"

All date parameters default to the last 28 days if omitted.
