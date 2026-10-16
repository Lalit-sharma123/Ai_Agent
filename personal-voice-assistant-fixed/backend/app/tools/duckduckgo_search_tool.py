"""DuckDuckGo scraper exposed as a LangChain Custom Tool.

The tool performs text search only, requires no API key, and returns normalized
JSON-friendly source records for LangGraph/MCP research workflows.
"""
from __future__ import annotations

import json
from typing import Literal

try:
    from langchain_core.tools import tool
except ImportError:  # Keep API importable in minimal test environments.
    def tool(*decorator_args, **decorator_kwargs):
        def decorate(func):
            func.name = decorator_kwargs.get("name", func.__name__)
            func.description = decorator_kwargs.get("description", func.__doc__ or "")
            func.invoke = lambda args: func(**args) if isinstance(args, dict) else func(args)
            return func
        if decorator_args and callable(decorator_args[0]):
            return decorate(decorator_args[0])
        return decorate


@tool("duckduckgo_search", return_direct=False)
def duckduckgo_search(
    query: str,
    max_results: int = 5,
    region: str = "wt-wt",
    safesearch: Literal["on", "moderate", "off"] = "moderate",
    timelimit: Literal["d", "w", "m", "y"] | None = None,
) -> str:
    """Search the web using the open-source DuckDuckGo scraper.

    Args:
        query: The web search query.
        max_results: Number of results, from 1 through 20.
        region: DuckDuckGo region, e.g. wt-wt, us-en, uk-en, in-en.
        safesearch: Safe search setting: on, moderate, or off.
        timelimit: Optional time filter: d (day), w (week), m (month), y (year).
    Returns:
        A JSON string containing normalized title, URL, snippet, and provider fields.
    """
    query = query.strip()
    if len(query) < 2:
        raise ValueError("Search query must contain at least two characters.")
    if len(query) > 1000:
        raise ValueError("Search query is too long.")
    max_results = max(1, min(int(max_results), 20))
    if safesearch not in {"on", "moderate", "off"}:
        raise ValueError("safesearch must be on, moderate, or off.")
    if timelimit not in {None, "d", "w", "m", "y"}:
        raise ValueError("timelimit must be d, w, m, y, or null.")

    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError as exc:
            raise RuntimeError(
                "DuckDuckGo dependency is missing. "
                "Run pip install ddgs in the backend virtualenv."
            ) from exc

    with DDGS() as ddgs:
        raw = list(ddgs.text(
            query,
            max_results=max_results,
            region=region,
            safesearch=safesearch,
            timelimit=timelimit,
        ) or [])

    results = []
    for item in raw[:max_results]:
        url = str(item.get("href") or item.get("url") or "").strip()
        if not url.startswith(("https://", "http://")):
            continue
        results.append({
            "title": str(item.get("title") or "Untitled result")[:500],
            "url": url[:2000],
            "snippet": str(item.get("body") or item.get("snippet") or "")[:5000],
            "provider": "duckduckgo",
        })
    return json.dumps({"query": query, "provider": "duckduckgo", "count": len(results), "results": results}, ensure_ascii=False)


def search_duckduckgo(**kwargs) -> dict:
    """Convenience wrapper for backend code; calls the LangChain tool's invoke API."""
    raw = duckduckgo_search.invoke(kwargs)
    return json.loads(raw) if isinstance(raw, str) else raw
