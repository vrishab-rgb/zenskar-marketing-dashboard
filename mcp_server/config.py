"""Configuration via environment variables for MCP server.

Supports:
- .env file (auto-detected or via DOTENV_PATH env var)
- Plain env vars (for VM/Docker)
"""

import os
import tempfile
import json
from pathlib import Path

from dotenv import load_dotenv

# Load .env — check DOTENV_PATH first, then project root
_project_root = Path(__file__).parent.parent
_dotenv_path = os.getenv("DOTENV_PATH", "")
if _dotenv_path:
    load_dotenv(Path(_dotenv_path))
else:
    load_dotenv(_project_root / ".env")

# ── Google Service Account ──────────────────────────────────────
# Accepts either a file path or inline JSON (for cloud deployments)
_sa_env = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
if _sa_env.startswith("{"):
    _tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    _tmp.write(_sa_env)
    _tmp.close()
    SERVICE_ACCOUNT_PATH = _tmp.name
else:
    SERVICE_ACCOUNT_PATH = _sa_env or str(_project_root / "credentials.json")

# ── Google Search Console ───────────────────────────────────────
GSC_SITE_URL = os.getenv("GSC_SITE_URL", "https://www.zenskar.com/")

# ── Google Analytics 4 ──────────────────────────────────────────
GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "")

# ── Google Ads ──────────────────────────────────────────────────
ADS_CUSTOMER_ID = os.getenv("ADS_CUSTOMER_ID", "5860587550")
ADS_DEV_TOKEN = os.getenv("ADS_DEV_TOKEN", "15TPUo-DIzm0AzR3P5W-tQ")
# Accepts inline JSON or a file path
_ads_token_env = os.getenv("ADS_TOKEN_JSON", "")
if _ads_token_env.startswith("{"):
    ADS_TOKEN = json.loads(_ads_token_env)
    ADS_TOKEN_FILE = None
else:
    ADS_TOKEN = None
    ADS_TOKEN_FILE = os.getenv("ADS_TOKEN_FILE", str(_project_root / "google_ads_token.json"))

# ── HubSpot ─────────────────────────────────────────────────────
HUBSPOT_PAT = os.getenv("HUBSPOT_PAT", "")

# ── Bing Webmaster Tools ────────────────────────────────────────
BING_API_KEY = os.getenv("BING_API_KEY", "")
