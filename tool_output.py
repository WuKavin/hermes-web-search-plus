"""Human-readable, line-safe output for tool hosts such as OpenCode."""

from __future__ import annotations

import re
from typing import Any, Iterable


# Keep even ripgrep JSON records with one submatch per character below 64 KiB.
MAX_LINE_CHARS = 1000
MAX_SEARCH_EXCERPT_CHARS = 4000

_BASE64_MARKDOWN_IMAGE_RE = re.compile(
    r"!\[([^\]]*)\]\(\s*data:image/[^)]+\)", re.IGNORECASE
)
_BASE64_HTML_IMAGE_RE = re.compile(
    r"<img\b(?=[^>]*\bsrc=[\"']data:image/)[^>]*>", re.IGNORECASE
)


def _inline(value: Any, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 3)].rstrip() + "..."


def _sanitize_content(value: Any) -> str:
    text = str(value or "").replace("\x00", "")
    text = _BASE64_MARKDOWN_IMAGE_RE.sub(
        lambda match: "[IMAGE: {}]".format(_inline(match.group(1) or "image", 100)),
        text,
    )
    return _BASE64_HTML_IMAGE_RE.sub("[IMAGE: embedded image]", text)


def _line_safe(value: Any, max_chars: int = MAX_LINE_CHARS) -> list[str]:
    text = _sanitize_content(value).replace("\r\n", "\n").replace("\r", "\n")
    rendered: list[str] = []
    for line in text.split("\n"):
        if not line:
            rendered.append("")
            continue
        rendered.extend(
            line[offset : offset + max_chars]
            for offset in range(0, len(line), max_chars)
        )
    return rendered or [""]


def _extend(lines: list[str], value: Any) -> None:
    lines.extend(_line_safe(value))


def _routing_lines(payload: dict[str, Any]) -> Iterable[str]:
    routing = payload.get("routing") or {}
    if not isinstance(routing, dict):
        return ()
    lines = []
    if routing.get("auto_routed"):
        detail = "Auto-routed: yes"
        if routing.get("confidence_level"):
            detail += " | confidence: {}".format(_inline(routing["confidence_level"], 50))
        lines.append(detail)
    if routing.get("fallback_used"):
        lines.append(
            "Fallback: {} -> {}".format(
                _inline(routing.get("original_provider") or "unknown", 100),
                _inline(routing.get("provider") or payload.get("provider") or "unknown", 100),
            )
        )
    return lines


def render_search_markdown(payload: dict[str, Any]) -> str:
    """Render search sources without embedding provider full-page content."""
    if payload.get("error") and not payload.get("results"):
        return "# Search Error\n\n{}".format(_inline(payload["error"], 2000))

    lines = ["# Search Results", ""]
    if payload.get("query"):
        _extend(lines, "Query: {}".format(_inline(payload["query"], 2000)))
    lines.append("Provider: {}".format(_inline(payload.get("provider") or "unknown", 100)))
    lines.extend(_routing_lines(payload))
    if payload.get("cached"):
        lines.append("Cached: yes")

    results = payload.get("results") or []
    if not results:
        lines.extend(["", "No results returned."])
        return "\n".join(lines).strip()

    for index, result in enumerate(results, 1):
        if not isinstance(result, dict):
            continue
        lines.extend(["", "## {}. {}".format(index, _inline(result.get("title") or "Untitled"))])
        if result.get("url"):
            _extend(lines, "Source: {}".format(result["url"]))
        if result.get("date") or result.get("published_date"):
            lines.append("Date: {}".format(_inline(result.get("date") or result.get("published_date"), 100)))
        excerpt = (
            result.get("snippet")
            or result.get("description")
            or result.get("summary")
            or result.get("content")
            or ""
        )
        if excerpt:
            excerpt = str(excerpt)
            if len(excerpt) > MAX_SEARCH_EXCERPT_CHARS:
                excerpt = excerpt[:MAX_SEARCH_EXCERPT_CHARS].rstrip() + "\n\n[Excerpt truncated]"
            lines.append("")
            _extend(lines, excerpt)

    return "\n".join(lines).strip()


def render_extract_markdown(payload: dict[str, Any]) -> str:
    """Render extracted pages as searchable multi-line text with bounded lines."""
    if payload.get("error") and not payload.get("results"):
        return "# Extract Error\n\n{}".format(_inline(payload["error"], 2000))

    lines = [
        "# Extracted Pages",
        "",
        "Provider: {}".format(_inline(payload.get("provider") or "unknown", 100)),
    ]
    lines.extend(_routing_lines(payload))
    results = payload.get("results") or []
    if not results:
        lines.extend(["", "No pages returned."])
        return "\n".join(lines).strip()

    for index, result in enumerate(results, 1):
        if not isinstance(result, dict):
            continue
        lines.extend(["", "## {}. {}".format(index, _inline(result.get("title") or "Untitled"))])
        if result.get("url"):
            _extend(lines, "Source: {}".format(result["url"]))
        if result.get("error"):
            _extend(lines, "Error: {}".format(_inline(result["error"], 2000)))
            continue
        content = result.get("content") or result.get("raw_content") or ""
        if content:
            lines.append("")
            _extend(lines, content)
        else:
            lines.extend(["", "No extracted content returned."])

    return "\n".join(lines).strip()
