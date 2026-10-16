import json
import pytest

from app.tools import duckduckgo_search_tool as module


def test_duckduckgo_tool_validates_query_before_network():
    with pytest.raises(ValueError):
        module.duckduckgo_search.invoke({
            "query": " ",
            "max_results": 5,
            "region": "wt-wt",
            "safesearch": "moderate",
            "timelimit": None,
        })


def test_search_wrapper_normalizes_results(monkeypatch):
    class FakeDDGS:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def text(self, query, **kwargs):
            assert query == "latest AI agent framework updates"
            assert kwargs["max_results"] == 2
            return [
                {"title": "A", "href": "https://example.com/a", "body": "Snippet A"},
                {"title": "B", "href": "https://example.com/b", "body": "Snippet B"},
                {"title": "Invalid", "href": "javascript:alert(1)", "body": "skip"},
            ]
    monkeypatch.setitem(__import__("sys").modules, "duckduckgo_search", type("FakeModule", (), {"DDGS": FakeDDGS}))
    result = module.search_duckduckgo(query="latest AI agent framework updates", max_results=2)
    assert result["count"] == 2
    assert result["provider"] == "duckduckgo"
    assert result["results"][0]["url"] == "https://example.com/a"
    assert result["results"][1]["snippet"] == "Snippet B"


def test_search_wrapper_rejects_invalid_timelimit():
    with pytest.raises(ValueError):
        module.duckduckgo_search.invoke({
            "query": "test query",
            "max_results": 5,
            "region": "wt-wt",
            "safesearch": "moderate",
            "timelimit": "forever",
        })
