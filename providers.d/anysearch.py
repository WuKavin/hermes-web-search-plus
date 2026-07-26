"""AnySearch provider for source search and URL extraction."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from http_client import make_request
from wsp_sdk import ProviderSpec, extract_result, search_result, source_result


def _domain_matches(url: str, domain: str) -> bool:
    hostname = (urlsplit(url).hostname or "").lower().rstrip(".")
    expected = str(domain).lower().strip().removeprefix("*.").rstrip(".")
    return bool(expected) and (hostname == expected or hostname.endswith(f".{expected}"))


def execute_search(search_module, prov, args, key, config, routing_info):
    section = config.get("anysearch", {}) if isinstance(config, dict) else {}
    if not isinstance(section, dict):
        section = {}
    endpoint = section.get("search_url", "https://api.anysearch.com/v1/search")
    timeout = int(section.get("timeout", 30))
    body: dict[str, Any] = {
        "query": str(getattr(args, "query", "")),
        "max_results": int(getattr(args, "max_results", 5)),
        "zone": section.get("zone", "intl"),
        "language": section.get("language", "en"),
    }
    freshness = getattr(args, "time_range", None) or getattr(args, "freshness", None)
    if freshness and freshness != "none":
        body["constraint"] = {"freshness": freshness}

    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = make_request(endpoint, headers, body, timeout=timeout)
    payload = data.get("data", data)
    raw_results = payload.get("results", []) if isinstance(payload, dict) else []
    include_domains = list(getattr(args, "include_domains", None) or [])
    exclude_domains = list(getattr(args, "exclude_domains", None) or [])
    results = []
    for index, item in enumerate(raw_results):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        if not url:
            continue
        if include_domains and not any(_domain_matches(url, domain) for domain in include_domains):
            continue
        if any(_domain_matches(url, domain) for domain in exclude_domains):
            continue
        score = item.get("score") or item.get("quality_score")
        if not isinstance(score, (int, float)):
            score = max(0.0, 1.0 - index * 0.1)
        results.append(source_result(
            url,
            title=str(item.get("title") or ""),
            snippet=str(item.get("snippet") or item.get("description") or item.get("content") or ""),
            content=str(item.get("content") or ""),
            score=round(float(score), 3),
            date=item.get("published_at"),
            source=item.get("source", "web"),
        ))
        if len(results) >= int(getattr(args, "max_results", 5)):
            break
    return search_result(
        prov,
        body["query"],
        results,
        metadata={"code": data.get("code"), "message": data.get("message")},
    )


def execute_extract(
    extract_module,
    prov,
    urls,
    key,
    output_format,
    include_images,
    include_raw_html,
    render_js,
    config,
    keyless_allowed,
):
    section = config.get("anysearch", {}) if isinstance(config, dict) else {}
    if not isinstance(section, dict):
        section = {}
    endpoint = section.get("extract_url", "https://api.anysearch.com/mcp")
    timeout = int(section.get("extract_timeout", section.get("timeout", 60)))
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    results = []
    for url in urls:
        try:
            data = make_request(
                endpoint,
                headers,
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "extract", "arguments": {"url": url}},
                    "id": 1,
                },
                timeout=timeout,
            )
            rpc_result = data.get("result", data)
            blocks = rpc_result.get("content", []) if isinstance(rpc_result, dict) else []
            content = "\n".join(
                str(block.get("text") or "")
                for block in blocks
                if isinstance(block, dict) and block.get("type") == "text"
            )
            if not content and isinstance(rpc_result, dict):
                content = str(rpc_result.get("text") or "")
            if not content:
                results.append(source_result(str(url), error="anysearch_extract_empty"))
                continue
            item = source_result(str(url), title="", content=content)
            if include_raw_html:
                item["raw_content"] = content
            results.append(item)
        except Exception:
            results.append(source_result(str(url), error="anysearch_extract_failed"))
    return extract_result(prov, results)


PROVIDER = ProviderSpec(
    id="anysearch",
    kind="both",
    env_var="ANYSEARCH_API_KEY",
    display_name="AnySearch",
    description="AI-native vertical search for code, academic, security, legal, finance, and multilingual queries.",
    config_section="anysearch",
    capability_labels=("search", "extract", "vertical", "multilingual"),
    auto_allowed_by_default=True,
    recommended=True,
    supports_freshness=True,
    free_tier="1,000 free searches/day",
    signup_url="https://anysearch.com/console/api-keys",
    execute_search=execute_search,
    execute_extract=execute_extract,
)
