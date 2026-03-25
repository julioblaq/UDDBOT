"""
scraper.py — Firecrawl-based scraper for hip hop drama content.
"""
import os
import logging
from firecrawl import FirecrawlApp

log = logging.getLogger(__name__)
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")

SITES = {
    "shaderoom": "https://theshaderoom.com",
    "worldstar":  "https://worldstarhiphop.com/videos",
    "allhiphop":  "https://allhiphop.com/news",
}

def _client():
    return FirecrawlApp(api_key=FIRECRAWL_API_KEY)

def scrape_site(site_key):
    url = SITES.get(site_key)
    if not url:
        return []
    try:
        result = _client().scrape_url(url, formats=["markdown"])
        return _parse_stories(result.markdown or "", url)
    except Exception as e:
        log.error(f"Firecrawl scrape error ({site_key}): {e}")
        return []

def scrape_all():
    return {key: scrape_site(key) for key in SITES}

def search_content(query):
    try:
        results = _client().search(f"{query} hip hop drama", limit=8)
        return [{"title": r.get("title","No title"), "url": r.get("url",""), "snippet": r.get("description") or r.get("markdown","")[:200]} for r in results]
    except Exception as e:
        log.error(f"Firecrawl search error: {e}")
        return []

def _parse_stories(markdown, base_url):
    stories = []
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("[") and "](" in line and line.endswith(")"):
            i = line.index("](")
            title = line[1:i].strip()
            url = line[i+2:-1].strip()
            if len(title) > 10 and not title.lower().startswith("http"):
                if not url.startswith("http"):
                    url = base_url.rstrip("/") + "/" + url.lstrip("/")
                stories.append({"title": title, "url": url, "snippet": ""})
        if len(stories) >= 10:
            break
    return stories
