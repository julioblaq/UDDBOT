"""
scraper.py — Firecrawl search-based scraper for hip hop drama content.
"""
import os
import logging
from firecrawl import FirecrawlApp

log = logging.getLogger(__name__)
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")

SITE_QUERIES = {
    "shaderoom": "site:theshaderoom.com",
    "worldstar":  "site:worldstarhiphop.com",
    "allhiphop":  "site:allhiphop.com",
}

def _client():
    return FirecrawlApp(api_key=FIRECRAWL_API_KEY)

def _parse_results(raw) -> list[dict]:
    if isinstance(raw, list):
        items = raw
    elif hasattr(raw, "data"):
        items = raw.data
    elif hasattr(raw, "results"):
        items = raw.results
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
    query = {"shaderoom": "site:theshaderoom.com", "worldstar": "site:worldstarhiphop.com", "allhiphop": "site:allhiphop.com"}.get(site_key)
    if not query:
        return []
    try:
        return _parse_results(_client().search(query, limit=8))
    except Exception as e:
        log.error(f"Firecrawl search error ({site_key}): {e}")
        return []

def scrape_all() -> dict:
    return {key: scrape_site(key) for key in ["shaderoom", "worldstar", "allhiphop"]}

def search_content(query: str) -> list[dict]:
    try:
        return _parse_results(_client().search(f"{query} hip hop", limit=8))
    except Exception as e:
        log.error(f"Firecrawl search error: {e}")
        return []
