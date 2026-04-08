"""Configuration via environment variables or Streamlit secrets.

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


def _get(key: str, default: str = "") -> str:
    """Read from env vars first, then Streamlit secrets."""
    val = os.getenv(key, "")
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


# ── Google Service Account ──────────────────────────────────────
# Accepts either a file path or inline JSON (for cloud deployments)
_sa_env = _get("GOOGLE_SERVICE_ACCOUNT_JSON")
if _sa_env.startswith("{"):
    _tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    _tmp.write(_sa_env)
    _tmp.close()
    SERVICE_ACCOUNT_PATH = _tmp.name
else:
    SERVICE_ACCOUNT_PATH = _sa_env or str(_project_root / "credentials.json")

# ── Google Search Console ───────────────────────────────────────
GSC_SITE_URL = _get("GSC_SITE_URL", "https://www.zenskar.com/")

# ── Google Analytics 4 ──────────────────────────────────────────
GA4_PROPERTY_ID = _get("GA4_PROPERTY_ID")

# ── Google Ads ──────────────────────────────────────────────────
ADS_CUSTOMER_ID = _get("ADS_CUSTOMER_ID", "5860587550")
ADS_DEV_TOKEN = _get("ADS_DEV_TOKEN", "15TPUo-DIzm0AzR3P5W-tQ")
# Accepts inline JSON (for Streamlit Cloud) or a file path
_ads_token_env = _get("ADS_TOKEN_JSON")
if _ads_token_env.startswith("{"):
    ADS_TOKEN = json.loads(_ads_token_env)
    ADS_TOKEN_FILE = None
else:
    ADS_TOKEN = None
    ADS_TOKEN_FILE = _get("ADS_TOKEN_FILE", str(_project_root / "google_ads_token.json"))

# ── Supabase ────────────────────────────────────────────────────
SUPABASE_URL = _get("SUPABASE_URL")
SUPABASE_KEY = _get("SUPABASE_KEY")
