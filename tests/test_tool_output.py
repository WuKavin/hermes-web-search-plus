from __future__ import annotations

import json
import sys

import search
from tool_output import MAX_LINE_CHARS, render_extract_markdown, render_search_markdown


def test_extract_markdown_preserves_content_without_oversized_lines():
    content = "intro\n" + ("汉" * 70000) + "\noutro"
    rendered = render_extract_markdown({
        "provider": "anysearch",
        "results": [{
            "title": "Large page",
            "url": "https://example.com/large",
            "content": content,
        }],
    })

    assert rendered.startswith("# Extracted Pages\n")
    assert "Source: https://example.com/large" in rendered
    assert "intro" in rendered
    assert "outro" in rendered
    assert max(len(line) for line in rendered.splitlines()) <= MAX_LINE_CHARS
    assert max(len(line.encode("utf-8")) for line in rendered.splitlines()) < 65536


def test_search_markdown_uses_excerpt_instead_of_full_page_content():
    rendered = render_search_markdown({
        "provider": "anysearch",
        "query": "test query",
        "results": [{
            "title": "Source title",
            "url": "https://example.com/source",
            "snippet": "Useful excerpt",
            "content": "FULL_PAGE_SENTINEL" * 10000,
        }],
        "routing": {"auto_routed": True, "confidence_level": "high"},
    })

    assert rendered.startswith("# Search Results\n")
    assert "Useful excerpt" in rendered
    assert "FULL_PAGE_SENTINEL" not in rendered
    assert "Auto-routed: yes | confidence: high" in rendered


def test_extract_markdown_removes_embedded_base64_images():
    rendered = render_extract_markdown({
        "provider": "tavily",
        "results": [{
            "url": "https://example.com",
            "content": "before ![chart](data:image/png;base64," + ("A" * 70000) + ") after",
        }],
    })

    assert "data:image" not in rendered
    assert "[IMAGE: chart]" in rendered
    assert "before" in rendered and "after" in rendered


def test_markdown_error_is_multiline_and_human_readable():
    assert render_search_markdown({"error": "provider failed", "results": []}) == (
        "# Search Error\n\nprovider failed"
    )
    assert render_extract_markdown({"error": "extract failed", "results": []}) == (
        "# Extract Error\n\nextract failed"
    )


def test_extract_cli_markdown_mode_uses_line_safe_renderer(monkeypatch, capsys):
    monkeypatch.setattr(search, "extract_plus", lambda **_kwargs: {
        "provider": "anysearch",
        "results": [{
            "url": "https://example.com",
            "content": "x" * 70000,
        }],
    })
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "search.py",
            "--extract-urls",
            "https://example.com",
            "--provider",
            "anysearch",
            "--tool-output",
            "markdown",
        ],
    )

    search.main()

    rendered = capsys.readouterr().out
    assert rendered.startswith("# Extracted Pages\n")
    assert max(len(line.encode("utf-8")) for line in rendered.splitlines()) < 65536


def test_extract_cli_keeps_json_as_default(monkeypatch, capsys):
    payload = {
        "provider": "anysearch",
        "results": [{"url": "https://example.com", "content": "body"}],
    }
    monkeypatch.setattr(search, "extract_plus", lambda **_kwargs: payload)
    monkeypatch.setattr(
        sys,
        "argv",
        ["search.py", "--extract-urls", "https://example.com", "--provider", "anysearch"],
    )

    search.main()

    assert json.loads(capsys.readouterr().out) == payload
