import os
import logging
from firecrawl import FirecrawlApp

log = logging.getLogger(__name__)
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")

def _client():
    return FirecrawlApp(api_key=FIRECRAWL_API_KEY)

def _parse_results(raw) -> list[dict]:
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("data") or raw.get("results") or []
    elif hasattr(raw, "data"):
        items = raw.data or []
    else:
        items = []
    stories = []
    for r in items:
        if isinstance(r, dict):
            title   = r.get("title", "")
            url     = r.get("url", "")
            snippet = r.get("description") or r.get("snippet", "")
        else:
            title   = getattr(r, "title", "")
            url     = getattr(r, "url", "")
            snippet = getattr(r, "description", "") or getattr(r, "snippet", "")
        if title and url:
            stories.append({"title": title, "url": url, "snippet": str(snippet)[:200]})
    return stories

def scrape_site(site_key: str) -> list[dict]:
    queries = {
        "shaderoom": "theshaderoom.com celebrity news latest",
        "worldstar":  "worldstarhiphop.com latest videos",
        "allhiphop":  "allhiphop.com hip hop news"
    }
    query = queries.get(site_key, "")
    try:
        return _parse_results(_client().search(query))
    except Exception as e:
        log.error(f"Firecrawl search error ({site_key}): {e}")
        return []

def scrape_all() -> dict:
    return {key: scrape_site(key) for key in ["shaderoom", "worldstar", "allhiphop"]}

def search_content(query: str) -> list[dict]:
    try:
        return _parse_results(_client().search(f"{query} hip hop"))
    except Exception as e:
        log.error(f"Firecrawl search error: {e}")
        return []
