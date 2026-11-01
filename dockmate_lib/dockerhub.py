#!/usr/bin/env python3
"""Docker Hub API client for searching and discovering containers."""

import json
import urllib.request
import urllib.parse
import urllib.error

SEARCH_URL = "https://hub.docker.com/v2/search/repositories/"


def search(query, limit=10):
    """
    Search Docker Hub for images matching *query*.

    Returns a list of dicts ``{name, description, stars, official}``
    or ``None`` on network error.
    """
    params = urllib.parse.urlencode({"query": query, "page_size": limit})
    url = f"{SEARCH_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "DockMate/1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = []
        for item in data.get("results", []):
            results.append({
                "name": item.get("repo_name", ""),
                "description": (item.get("short_description") or "")[:70],
                "stars": item.get("star_count", 0),
                "official": item.get("is_official", False),
            })
        return results

    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, OSError, ValueError):
        return None


def format_stars(count):
    """Format a star count for display (e.g. ``1.2K``)."""
    if count >= 1000:
        return f"{count / 1000:.1f}K"
    return str(count)
