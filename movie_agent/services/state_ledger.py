"""Small machine-addressable ledger for production-critical mutable state."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def ensure_state_ledger(project: Any) -> dict[str, Any]:
    ledger = getattr(project, "continuity_state_ledger", None)
    if not isinstance(ledger, dict):
        ledger = {"schema_version": 1, "shots": {}, "current": {}}
        project.continuity_state_ledger = ledger
    ledger.setdefault("schema_version", 1)
    ledger.setdefault("shots", {})
    ledger.setdefault("current", {})
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
    record = {
        "shot": int(getattr(shot, "number", 0) or 0),
        "before": before,
        "delta": deepcopy(delta),
        "after": after,
    }
    ledger["shots"][str(record["shot"])] = record
    ledger["current"] = after
    return record


__all__ = ["apply_shot_state_delta", "ensure_state_ledger"]
