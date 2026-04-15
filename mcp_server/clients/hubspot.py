"""HubSpot CRM API client (strictly READ-ONLY)."""

import logging
import re
import time

import requests

from mcp_server import config

logger = logging.getLogger(__name__)

_BASE = "https://api.hubapi.com"
_session_cache = None


def _session() -> requests.Session:
    """Get a cached requests session with auth headers."""
    global _session_cache
    if _session_cache is None:
        if not config.HUBSPOT_PAT:
            raise ValueError("HUBSPOT_PAT not set")
        _session_cache = requests.Session()
        _session_cache.headers.update({
            "Authorization": f"Bearer {config.HUBSPOT_PAT}",
            "Content-Type": "application/json",
        })
    return _session_cache


def strip_html(text: str) -> str:
    """Strip HTML tags and decode entities."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    for old, new in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                     ("&nbsp;", " "), ("&#x27;", "'"), ("&quot;", '"')]:
        text = text.replace(old, new)
    return text.strip()


def get_company(company_id: str, properties: list[str]) -> dict:
    """GET a company by ID with specified properties."""
    props = ",".join(properties)
    r = _session().get(f"{_BASE}/crm/v3/objects/companies/{company_id}?properties={props}")
    r.raise_for_status()
    data = r.json()
    result = {"id": data.get("id", company_id)}
    result.update(data.get("properties", {}))
    return result


def get_contact(contact_id: str, properties: list[str]) -> dict:
    """GET a contact by ID with specified properties."""
    props = ",".join(properties)
    r = _session().get(f"{_BASE}/crm/v3/objects/contacts/{contact_id}?properties={props}")
    r.raise_for_status()
    data = r.json()
    result = {"id": data.get("id", contact_id)}
    result.update(data.get("properties", {}))
    return result


def get_deal(deal_id: str, properties: list[str]) -> dict:
    """GET a deal by ID with specified properties."""
    props = ",".join(properties)
    r = _session().get(f"{_BASE}/crm/v3/objects/deals/{deal_id}?properties={props}")
    r.raise_for_status()
    data = r.json()
    result = {"id": data.get("id", deal_id)}
    result.update(data.get("properties", {}))
    return result


def search_deals(
    filter_groups: list[dict],
    properties: list[str],
    limit: int = 20,
    sort_by: str = "createdate",
) -> list[dict]:
    """Search deals with HubSpot filter groups (POST, read-only search)."""
    payload = {
        "filterGroups": filter_groups,
        "properties": properties,
        "sorts": [{"propertyName": sort_by, "direction": "DESCENDING"}],
        "limit": limit,
    }
    r = _session().post(f"{_BASE}/crm/v3/objects/deals/search", json=payload)
    r.raise_for_status()
    data = r.json()
    results = []
    for deal in data.get("results", []):
        entry = {"id": deal.get("id", "")}
        entry.update(deal.get("properties", {}))
        results.append(entry)
    return results


def get_company_contacts(company_id: str, limit: int = 5) -> list[dict]:
    """Get contacts associated with a company."""
    r = _session().get(f"{_BASE}/crm/v3/objects/companies/{company_id}/associations/contacts")
    r.raise_for_status()
    contact_ids = [str(c["id"]) for c in r.json().get("results", [])]

    default_props = [
        "firstname", "lastname", "email", "jobtitle",
        "hs_analytics_source", "hs_analytics_first_url", "hs_analytics_last_url",
        "hs_analytics_num_page_views",
    ]

    contacts = []
    for ctid in contact_ids[:limit]:
        time.sleep(0.1)
        r2 = _session().get(
            f"{_BASE}/crm/v3/objects/contacts/{ctid}?properties={','.join(default_props)}"
        )
        if r2.status_code != 200:
            continue
        cp = r2.json().get("properties", {})
        contacts.append({
            "id": ctid,
            "name": f"{cp.get('firstname', '') or ''} {cp.get('lastname', '') or ''}".strip(),
            "email": cp.get("email") or "",
            "title": cp.get("jobtitle") or "",
            "source": cp.get("hs_analytics_source") or "",
            "first_url": cp.get("hs_analytics_first_url") or "",
            "last_url": cp.get("hs_analytics_last_url") or "",
            "page_views": cp.get("hs_analytics_num_page_views") or "",
        })

    return contacts


def get_company_notes(company_id: str, limit: int = 8) -> list[dict]:
    """Get notes associated with a company."""
    r = _session().get(f"{_BASE}/crm/v3/objects/companies/{company_id}/associations/notes")
    r.raise_for_status()
    note_ids = [str(n["id"]) for n in r.json().get("results", [])]

    notes = []
    for nid in note_ids[:limit]:
        time.sleep(0.1)
        r2 = _session().get(
            f"{_BASE}/crm/v3/objects/notes/{nid}?properties=hs_timestamp,hs_note_body"
        )
        if r2.status_code != 200:
            continue
        np = r2.json().get("properties", {})
        body = strip_html(np.get("hs_note_body"))
        if body:
            notes.append({
                "timestamp": np.get("hs_timestamp", ""),
                "body": body,
            })

    return notes


def get_company_meetings(company_id: str, limit: int = 8) -> list[dict]:
    """Get meetings associated with a company."""
    r = _session().get(f"{_BASE}/crm/v3/objects/companies/{company_id}/associations/meetings")
    r.raise_for_status()
    meeting_ids = [str(m["id"]) for m in r.json().get("results", [])]

    meetings = []
    for mid in meeting_ids[:limit]:
        time.sleep(0.1)
        r2 = _session().get(
            f"{_BASE}/crm/v3/objects/meetings/{mid}?properties=hs_timestamp,hs_meeting_title,hs_meeting_body,hs_meeting_outcome"
        )
        if r2.status_code != 200:
            continue
        mp = r2.json().get("properties", {})
        meetings.append({
            "timestamp": mp.get("hs_timestamp", ""),
            "title": mp.get("hs_meeting_title") or "",
            "outcome": mp.get("hs_meeting_outcome") or "",
            "body": strip_html(mp.get("hs_meeting_body")),
        })

    return meetings


def get_contact_page_visits(contact_id: str, limit: int = 50) -> list[dict]:
    """Get page visit events for a contact."""
    base_url = f"{_BASE}/events/v3/events?objectType=contact&objectId={contact_id}&eventType=e_visited_page&limit={min(limit, 50)}"

    events = []
    url = base_url
    while len(events) < limit:
        r = _session().get(url)
        if r.status_code != 200:
            break
        data = r.json()
        for evt in data.get("results", []):
            props = evt.get("properties", {})
            events.append({
                "timestamp": evt.get("occurredAt", ""),
                "url": props.get("hs_url") or "",
                "title": props.get("hs_page_title") or "",
                "referrer": props.get("hs_referrer") or "",
                "source": props.get("hs_visit_source") or "",
                "device": props.get("hs_device_type") or "",
                "country": props.get("hs_country") or "",
            })

        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
        url = f"{base_url}&after={after}"
        time.sleep(0.1)

    events.sort(key=lambda x: x["timestamp"])
    return events[:limit]
