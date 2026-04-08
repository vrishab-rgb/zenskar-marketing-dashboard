"""Configuration via environment variables.

Supports:
- .env file in project root (for local dev)
- Streamlit secrets (for Streamlit Cloud)
- Plain env vars (for VM/Docker)
"""

import os
import tempfile
import json
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root if present
_project_root = Path(__file__).parent.parent
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
# Accepts inline JSON (for Streamlit Cloud) or a file path
_ads_token_env = os.getenv("ADS_TOKEN_JSON", "")
if _ads_token_env.startswith("{"):
    ADS_TOKEN = json.loads(_ads_token_env)
    ADS_TOKEN_FILE = None
else:
    ADS_TOKEN = None
    ADS_TOKEN_FILE = os.getenv("ADS_TOKEN_FILE", str(_project_root / "google_ads_token.json"))
