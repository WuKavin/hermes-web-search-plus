from __future__ import annotations

import json
import multiprocessing
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest

import config
import extract
import extract_load_balancer
from compat_v3 import legacy_request_to_v3
from contract_v3 import Capability


WEIGHTED_CONFIG = {
    "auto_routing": {
        "extract_strategy": "weighted_round_robin",
        "extract_weights": {"anysearch": 5, "tavily": 3, "exa": 2},
    }
}
CANDIDATES = ["tavily", "exa", "anysearch"]


def _select_in_process(args):
    state_path, candidates, runtime_config = args
    import extract_load_balancer as worker_balancer

    worker_balancer.EXTRACT_ROUTING_STATE_FILE = Path(state_path)
    return worker_balancer.order_extract_candidates(candidates, runtime_config)[0]


def test_default_extract_strategy_and_weights():
    auto = config.DEFAULT_CONFIG["auto_routing"]

    assert auto["extract_strategy"] == "weighted_round_robin"
    assert auto["extract_weights"] == {"anysearch": 5, "tavily": 3, "exa": 2}


def test_weighted_round_robin_selects_exact_50_30_20_distribution():
    orders = [
        extract_load_balancer.order_extract_candidates(CANDIDATES, WEIGHTED_CONFIG)
        for _ in range(10)
    ]

    assert Counter(order[0] for order in orders) == {
        "anysearch": 5,
        "tavily": 3,
        "exa": 2,
    }
    assert all(set(order) == set(CANDIDATES) and len(order) == 3 for order in orders)


def test_v3_extract_plan_uses_weighted_primary_and_preserves_fallbacks(monkeypatch):
    monkeypatch.setattr(
        extract,
        "get_api_key",
        lambda provider, _config=None: "configured" if provider in set(CANDIDATES) else None,
    )
    request = legacy_request_to_v3(
        Capability.EXTRACT,
        {"urls": ["https://example.com"], "provider": "auto"},
    )

    plans = [extract._plan_extract_v3(request, WEIGHTED_CONFIG) for _ in range(10)]

    assert Counter(plan.selected_provider for plan in plans) == {
        "anysearch": 5,
        "tavily": 3,
        "exa": 2,
    }
    assert all(set(plan.candidate_order) == set(CANDIDATES) for plan in plans)


def test_weighted_primary_failure_falls_back_to_remaining_provider(monkeypatch):
    calls = []

    def anysearch_adapter(*_args):
        calls.append("anysearch")
        return {
            "provider": "anysearch",
            "results": [{"url": "https://example.com", "error": "upstream failed"}],
        }

    def tavily_adapter(*_args):
        calls.append("tavily")
        return {
            "provider": "tavily",
            "results": [{"url": "https://example.com", "content": "fallback content"}],
        }

    monkeypatch.setattr(extract, "_validate_extract_urls", lambda urls, _config: urls)
    monkeypatch.setattr(
        extract,
        "get_api_key",
        lambda provider, _config=None: "configured" if provider in set(CANDIDATES) else None,
    )
    monkeypatch.setattr(extract, "execute_provider_with_retry", lambda _provider, call: call())
    monkeypatch.setattr(extract, "provider_in_cooldown", lambda _provider: (False, 0))
    monkeypatch.setitem(extract.EXTRACT_DISPATCH, "anysearch", anysearch_adapter)
    monkeypatch.setitem(extract.EXTRACT_DISPATCH, "tavily", tavily_adapter)

    result = extract._extract_plus_core(
        ["https://example.com"],
        provider="auto",
        config=WEIGHTED_CONFIG,
    )

    assert calls == ["anysearch", "tavily"]
    assert result["provider"] == "tavily"
    assert result["routing"]["fallback_used"] is True
    assert result["routing"]["fallback_errors"][0]["provider"] == "anysearch"


def test_weighted_round_robin_state_is_cross_process_safe(tmp_path):
    state_path = tmp_path / "shared-extract-routing-state.json"
    work = [(str(state_path), CANDIDATES, WEIGHTED_CONFIG) for _ in range(20)]

    with ProcessPoolExecutor(
        max_workers=4,
        mp_context=multiprocessing.get_context("spawn"),
    ) as pool:
        selected = list(pool.map(_select_in_process, work))

    assert Counter(selected) == {"anysearch": 10, "tavily": 6, "exa": 4}
    assert json.loads(state_path.read_text(encoding="utf-8"))["cursor"] == 20


def test_priority_strategy_preserves_existing_order():
    runtime_config = {"auto_routing": {"extract_strategy": "priority"}}

    assert extract_load_balancer.order_extract_candidates(CANDIDATES, runtime_config) == CANDIDATES
    assert not extract_load_balancer.EXTRACT_ROUTING_STATE_FILE.exists()


def test_weights_apply_only_to_available_candidates():
    selected = [
        extract_load_balancer.order_extract_candidates(["tavily", "exa"], WEIGHTED_CONFIG)[0]
        for _ in range(5)
    ]

    assert Counter(selected) == {"tavily": 3, "exa": 2}


@pytest.mark.parametrize(
    "strategy,weights,error",
    [
        ("random", {"anysearch": 5}, "extract_strategy"),
        ("weighted_round_robin", {"brave": 1}, "does not support extraction"),
        ("weighted_round_robin", {"anysearch": 0}, "between 1 and 100"),
        ("weighted_round_robin", {"anysearch": True}, "between 1 and 100"),
    ],
)
def test_extract_balancer_config_rejects_invalid_values(strategy, weights, error):
    runtime_config = config._deepcopy_default_config()
    runtime_config["auto_routing"]["extract_strategy"] = strategy
    runtime_config["auto_routing"]["extract_weights"] = weights

    with pytest.raises(ValueError, match=error):
        config._validate_runtime_config(runtime_config)


def test_self_hosted_profile_forces_priority_strategy():
    runtime_config = config._deepcopy_default_config()
    runtime_config["profile"] = "self_hosted"

    effective = config.apply_profile_effects(runtime_config)

    assert effective["auto_routing"]["extract_strategy"] == "priority"
