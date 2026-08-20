"""Persistent extraction-provider load balancing for automatic routing."""

from __future__ import annotations

import json
import os
import secrets
import stat
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

from cache import CACHE_DIR

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows only
    fcntl = None
    import msvcrt


EXTRACT_ROUTING_STATE_FILE = CACHE_DIR / "extract_routing_state.json"
_STATE_LOCK = threading.Lock()
_STATE_VERSION = 1


def _smooth_weighted_cycle(providers: List[str], weights: Dict[str, int]) -> List[str]:
    """Build one deterministic smooth weighted-round-robin cycle."""
    current = {provider: 0 for provider in providers}
    total = sum(weights[provider] for provider in providers)
    cycle: List[str] = []
    for _ in range(total):
        for provider in providers:
            current[provider] += weights[provider]
        selected = max(providers, key=lambda provider: current[provider])
        current[selected] -= total
        cycle.append(selected)
    return cycle


def _lock_descriptor(descriptor: int) -> None:
    if fcntl is not None:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        return
    os.lseek(descriptor, 0, os.SEEK_SET)  # pragma: no cover - Windows only
    if os.fstat(descriptor).st_size == 0:  # pragma: no cover - Windows only
        os.write(descriptor, b" ")
        os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
    msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)  # pragma: no cover - Windows only


def _unlock_descriptor(descriptor: int) -> None:
    if fcntl is not None:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return
    os.lseek(descriptor, 0, os.SEEK_SET)  # pragma: no cover - Windows only
    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)  # pragma: no cover - Windows only


def _next_cursor(path: Path | None = None) -> int:
    """Atomically return and advance the cross-process extraction cursor."""
    state_path = path or EXTRACT_ROUTING_STATE_FILE
    state_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    with _STATE_LOCK:
        for attempt in range(3):
            try:
                descriptor = os.open(state_path, flags, 0o600)
                break
            except FileNotFoundError:
                if attempt == 2:
                    raise
                time.sleep(0.001 * (attempt + 1))
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise OSError("extract routing state is not a regular file")
            if hasattr(os, "geteuid") and opened.st_uid != os.geteuid():
                raise OSError("extract routing state is not owned by the current user")
            if hasattr(os, "fchmod"):
                os.fchmod(descriptor, 0o600)
            _lock_descriptor(descriptor)
            try:
                os.lseek(descriptor, 0, os.SEEK_SET)
                raw = os.read(descriptor, 4096).decode("utf-8", errors="replace")
                try:
                    payload = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError:
                    payload = {}
                cursor = payload.get("cursor", 0) if isinstance(payload, dict) else 0
                if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0:
                    cursor = 0
                encoded = json.dumps(
                    {"version": _STATE_VERSION, "cursor": cursor + 1},
                    separators=(",", ":"),
                ).encode("utf-8")
                os.lseek(descriptor, 0, os.SEEK_SET)
                os.ftruncate(descriptor, 0)
                os.write(descriptor, encoded)
                os.fsync(descriptor)
                return cursor
            finally:
                _unlock_descriptor(descriptor)
        finally:
            if descriptor >= 0:
                os.close(descriptor)


def order_extract_candidates(candidates: List[str], config: Dict[str, Any]) -> List[str]:
    """Select one weighted primary and preserve every remaining fallback."""
    if len(candidates) < 2:
        return list(candidates)
    auto = config.get("auto_routing", {}) if isinstance(config, dict) else {}
    if not isinstance(auto, dict) or auto.get("extract_strategy", "priority") != "weighted_round_robin":
        return list(candidates)
    raw_weights = auto.get("extract_weights", {})
    if not isinstance(raw_weights, dict):
        return list(candidates)
    weights = {
        provider: weight
        for provider, weight in raw_weights.items()
        if provider in candidates
        and isinstance(weight, int)
        and not isinstance(weight, bool)
        and weight > 0
    }
    candidate_positions = {provider: index for index, provider in enumerate(candidates)}
    weighted = sorted(
        weights,
        key=lambda provider: (-weights[provider], candidate_positions[provider]),
    )
    if not weighted:
        return list(candidates)
    cycle = _smooth_weighted_cycle(weighted, weights)
    try:
        cursor = _next_cursor()
    except OSError:
        cursor = secrets.randbelow(len(cycle))
    selected = cycle[cursor % len(cycle)]
    fallback = [provider for provider in candidates if provider != selected]
    return [selected, *fallback]
