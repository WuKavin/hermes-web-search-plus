import socket

import pytest

import cache
import extract
import extract_load_balancer
import provider_stats
import search


@pytest.fixture(autouse=True)
def _isolate_runtime_state(tmp_path, monkeypatch):
    """Keep mutable runtime state out of real paths and isolate every test.

    Search tests record outcomes for mocked providers; without isolation those
    samples would pollute the operator's provider_stats.json and, worse, feed
    back into routing decisions and make routing tests order-dependent.
    """
    monkeypatch.setattr(provider_stats, "PROVIDER_STATS_FILE", tmp_path / "provider_stats.json")
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(search, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(extract, "CACHE_DIR", tmp_path)
    real_getaddrinfo = socket.getaddrinfo

    def deterministic_example_dns(host, port, *args, **kwargs):
        if str(host).lower().rstrip(".") in {"example.com", "example.org", "example.net"}:
            return [
                (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port))
            ]
        return real_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(extract.socket, "getaddrinfo", deterministic_example_dns)
    monkeypatch.setattr(
        extract_load_balancer,
        "EXTRACT_ROUTING_STATE_FILE",
        tmp_path / "extract_routing_state.json",
    )
