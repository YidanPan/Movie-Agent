"""Small machine-addressable ledger for production-critical mutable state."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def ensure_state_ledger(project: Any) -> dict[str, Any]:
    ledger = getattr(project, "continuity_state_ledger", None)
    if not isinstance(ledger, dict):
        ledger = {"schema_version": 2, "shots": {}, "current": {}, "order": []}
        project.continuity_state_ledger = ledger
    ledger["schema_version"] = max(2, int(ledger.get("schema_version", 1) or 1))
    ledger.setdefault("shots", {})
    ledger.setdefault("current", {})
    ledger.setdefault("order", [])
    return ledger


def apply_shot_state_delta(project: Any, shot: Any) -> dict[str, Any]:
    """Apply only explicitly supplied entity deltas and persist before/after."""

    ledger = ensure_state_ledger(project)
    before = deepcopy(ledger.get("current") or {})
    after = deepcopy(before)
    delta = getattr(shot, "state_delta", None) or {}
    if isinstance(delta, dict):
        for entity, changes in delta.items():
            if isinstance(changes, dict):
                after.setdefault(str(entity), {}).update(deepcopy(changes))
            else:
                after[str(entity)] = deepcopy(changes)
    record = {
        "shot": int(getattr(shot, "number", 0) or 0),
        "before": before,
        "delta": deepcopy(delta),
        "after": after,
    }
    ledger["shots"][str(record["shot"])] = record
    if record["shot"] not in ledger["order"]:
        ledger["order"].append(record["shot"])
        ledger["order"].sort()
    ledger["current"] = after
    return record


def build_state_ledger(project: Any) -> dict[str, Any]:
    """Deterministically rebuild all mutable shot state from Shot 01 onward."""

    ledger = ensure_state_ledger(project)
    ledger["shots"] = {}
    ledger["current"] = {}
    ledger["order"] = []
    for shot in sorted(getattr(project, "storyboard", []) or [], key=lambda item: int(getattr(item, "number", 0) or 0)):
        apply_shot_state_delta(project, shot)
    return ledger


def rebuild_state_ledger(project: Any) -> dict[str, Any]:
    """Alias used by edit boundaries when any upstream state changes."""

    return build_state_ledger(project)


def rebuild_state_ledger_from_shot(project: Any, shot_number: int) -> dict[str, Any]:
    """Rebuild from the beginning; short films make this safer than patching."""

    del shot_number
    return build_state_ledger(project)


def state_record_for_shot(project: Any, shot_number: int) -> dict[str, Any]:
    ledger = ensure_state_ledger(project)
    record = ledger.get("shots", {}).get(str(int(shot_number)))
    return deepcopy(record) if isinstance(record, dict) else {"before": {}, "delta": {}, "after": {}}


__all__ = [
    "apply_shot_state_delta",
    "build_state_ledger",
    "ensure_state_ledger",
    "rebuild_state_ledger",
    "rebuild_state_ledger_from_shot",
    "state_record_for_shot",
]
