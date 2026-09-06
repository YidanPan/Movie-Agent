"""Small machine-addressable ledger for production-critical mutable state."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from movie_agent.services.story_world import entity_ids


MAX_STATE_ENTITIES = 12
MAX_STATE_FIELDS_PER_ENTITY = 24
MAX_STATE_STRING_LENGTH = 500
STATE_DELTA_REVIEW_REQUIRED = "STATE_LEDGER_REVIEW_REQUIRED"


def _validate_state_value(value: Any, *, path: str, errors: list[str], depth: int = 0) -> None:
    """Keep API-provided state deltas shallow and JSON-safe."""

    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > MAX_STATE_STRING_LENGTH:
            errors.append(f"{path} exceeds {MAX_STATE_STRING_LENGTH} characters")
        return
    if depth >= 1 and isinstance(value, (dict, list, tuple)):
        errors.append(f"{path} must not contain nested objects")
        return
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_STATE_FIELDS_PER_ENTITY:
            errors.append(f"{path} contains too many items")
        for index, item in enumerate(value):
            _validate_state_value(item, path=f"{path}[{index}]", errors=errors, depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > MAX_STATE_FIELDS_PER_ENTITY:
            errors.append(f"{path} contains too many keys")
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                errors.append(f"{path} contains an invalid key")
                continue
            if len(key) > 120:
                errors.append(f"{path}.{key[:24]} exceeds the key length limit")
            _validate_state_value(item, path=f"{path}.{key}", errors=errors, depth=depth + 1)
        return
    errors.append(f"{path} contains a non-JSON value")


def validate_state_delta_shape(state_delta: Any) -> list[str]:
    """Validate the size/type contract without requiring a Story World."""

    errors: list[str] = []
    if not isinstance(state_delta, dict):
        return ["state_delta must be an object"]
    if len(state_delta) > MAX_STATE_ENTITIES:
        errors.append(f"state_delta may contain at most {MAX_STATE_ENTITIES} entities")
    for entity, changes in state_delta.items():
        if not isinstance(entity, str) or not entity.strip():
            errors.append("state_delta entity IDs must be non-empty strings")
            continue
        if not isinstance(changes, dict):
            errors.append(f"state_delta.{entity} must be an object")
            continue
        if len(changes) > MAX_STATE_FIELDS_PER_ENTITY:
            errors.append(f"state_delta.{entity} may contain at most {MAX_STATE_FIELDS_PER_ENTITY} fields")
        for key, value in changes.items():
            if not isinstance(key, str) or not key.strip():
                errors.append(f"state_delta.{entity} contains an invalid field")
                continue
            _validate_state_value(value, path=f"state_delta.{entity}.{key}", errors=errors)
    return errors


def validate_state_delta(state_delta: Any, story_world: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate canonical entity IDs and the bounded mutable-state shape."""

    errors = validate_state_delta_shape(state_delta)
    unknown: set[str] = set()
    if isinstance(state_delta, dict) and story_world:
        known = set().union(*(entity_ids(story_world, kind) for kind in ("characters", "scenes", "props")))
        unknown = {str(entity) for entity in state_delta if str(entity) not in known}
        if unknown:
            errors.append(f"Unknown state entities: {', '.join(sorted(unknown))}")
    return {
        "valid": not errors,
        "errors": errors,
        "unknown_state_entities": sorted(unknown),
    }


def validate_state_delta_or_raise(state_delta: Any, story_world: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a delta or raise the explicit review error used by production gates."""

    result = validate_state_delta(state_delta, story_world)
    if not result["valid"]:
        raise ValueError(f"{STATE_DELTA_REVIEW_REQUIRED}: {result['errors']}")
    return state_delta


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
    validation = validate_state_delta(delta, getattr(project, "story_world", {}) or {})
    if not validation["valid"]:
        raise ValueError(f"{STATE_DELTA_REVIEW_REQUIRED}: {validation['errors']}")
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
    "MAX_STATE_ENTITIES",
    "MAX_STATE_FIELDS_PER_ENTITY",
    "MAX_STATE_STRING_LENGTH",
    "STATE_DELTA_REVIEW_REQUIRED",
    "apply_shot_state_delta",
    "build_state_ledger",
    "ensure_state_ledger",
    "rebuild_state_ledger",
    "rebuild_state_ledger_from_shot",
    "state_record_for_shot",
    "validate_state_delta",
    "validate_state_delta_or_raise",
    "validate_state_delta_shape",
]
