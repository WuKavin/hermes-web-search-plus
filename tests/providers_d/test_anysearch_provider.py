from __future__ import annotations

from types import SimpleNamespace

import provider_registry


def _provider():
    spec = provider_registry.PROVIDER_SPECS["anysearch"]
    return spec, spec.execute_search.__globals__


def test_anysearch_registers_for_search_extract_and_auto_routing():
    spec, _module = _provider()

    assert spec.kind == "both"
    assert spec.auto_allowed_by_default is True
    assert spec.supports_freshness is True
    assert "anysearch" in provider_registry.SEARCH_PROVIDER_IDS
    assert "anysearch" in provider_registry.EXTRACT_PROVIDER_IDS
    assert "anysearch" in provider_registry.DEFAULT_PROVIDER_PRIORITY
    assert "anysearch" not in provider_registry.DEFAULT_AUTO_ALLOW


def test_anysearch_search_projects_source_only_results(monkeypatch):
    spec, module = _provider()
    monkeypatch.setitem(module, "make_request", lambda *_args, **_kwargs: {
        "code": 0,
        "message": "success",
        "data": {"results": [{
            "title": "Source",
            "url": "https://example.com/source",
            "content": "Evidence",
            "score": 0.9,
        }]},
    })
    args = SimpleNamespace(
        query="test query",
        max_results=3,
        time_range=None,
        freshness=None,
        include_domains=None,
        exclude_domains=None,
    )

    result = spec.execute_search(None, "anysearch", args, "key", {}, {})

    assert result["provider"] == "anysearch"
    assert result["query"] == "test query"
    assert result["results"][0]["url"] == "https://example.com/source"
    assert "answer" not in result


def test_anysearch_extract_projects_mcp_text(monkeypatch):
    spec, module = _provider()
    monkeypatch.setitem(module, "make_request", lambda *_args, **_kwargs: {
        "result": {"content": [{"type": "text", "text": "# Extracted"}]},
    })

    result = spec.execute_extract(
        None,
        "anysearch",
        ["https://example.com/source"],
        "key",
        "markdown",
        False,
        False,
        False,
        {},
        False,
    )

    assert result["provider"] == "anysearch"
    assert result["results"][0]["content"] == "# Extracted"
