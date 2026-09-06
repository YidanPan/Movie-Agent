"""Canonical Story Beat/Shot planning contracts."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


STORY_FUNCTIONS = {"SETUP", "ROUTINE", "ANOMALY", "RECOGNITION", "ESCALATION", "CLIMAX", "AFTERMATH", "ATMOSPHERE", "RHYTHM", "FORESHADOW"}
TRANSITION_TYPES = {"CONTINUOUS", "HARD_CUT", "MATCH_CUT", "AUDIO_BRIDGE", "ACTION_MATCH", "ELLIPSIS", "FADE", "DISSOLVE"}


def beat_count_for_duration(duration_seconds: int) -> int:
    duration = int(duration_seconds)
    if duration <= 40:
        return 4
    if duration <= 55:
        return 5
    if duration <= 70:
        return 6
    return 7


def _ids(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _weight(value: Any, default: float = 1.0) -> float:
    try:
        return max(0.1, float(value))
    except (TypeError, ValueError):
        return default


def normalise_story_beat(raw: dict[str, Any], index: int) -> dict[str, Any]:
    """Return one stable beat without overwriting valid legacy fields."""

    beat_id = str(raw.get("beat_id") or f"beat-{index + 1:02d}")
    beat_number = int(raw.get("beat_number") or index + 1)
    purpose = str(raw.get("narrative_purpose") or raw.get("story_function") or "develop the story").strip()
    story_function = str(raw.get("story_function") or purpose).strip()
    return {
        **raw,
        "beat_id": beat_id,
        "beat_number": beat_number,
        "scene_id": str(raw.get("scene_id") or "").strip(),
        "character_ids": _ids(raw.get("character_ids")),
        "prop_ids": _ids(raw.get("prop_ids")),
        "story_function": story_function,
        "narrative_purpose": purpose,
        "information_gain": _float(raw.get("information_gain"), 0.35),
        "emotional_shift": str(raw.get("emotional_shift") or raw.get("emotional_arc") or "").strip(),
        "visual_motif": str(raw.get("visual_motif") or "").strip(),
        "starting_state": str(raw.get("starting_state") or "").strip(),
        "ending_state": str(raw.get("ending_state") or "").strip(),
        "transition_hook": str(raw.get("transition_hook") or "").strip(),
        "importance": _float(raw.get("importance"), 0.5),
        "duration_weight": _weight(raw.get("duration_weight"), 1.0),
    }


def normalise_story_beats(beats: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [normalise_story_beat(beat, index) for index, beat in enumerate(beats or []) if isinstance(beat, dict)]


def validate_beat_shot_mapping(shots: Iterable[Any], beats: Iterable[dict[str, Any]]) -> dict[str, Any]:
    beats_list = normalise_story_beats(beats)
    valid_ids = [str(beat["beat_id"]) for beat in beats_list]
    valid_set = set(valid_ids)
    shot_list = list(shots)
    shot_ids = [str(getattr(shot, "beat_id", "") or "") for shot in shot_list]
    covered = sorted({beat_id for beat_id in shot_ids if beat_id in valid_set}, key=valid_ids.index)
    uncovered = [beat_id for beat_id in valid_ids if beat_id not in covered]
    orphan = [int(getattr(shot, "number", index + 1)) for index, shot in enumerate(shot_list) if str(getattr(shot, "beat_id", "") or "") not in valid_set]
    return {
        "covered_beats": covered,
        "uncovered_beats": uncovered,
        "orphan_shots": orphan,
        "coverage_ratio": round(len(covered) / max(1, len(valid_ids)), 3),
        "valid": not uncovered and not orphan,
    }


def allocate_weighted_durations(weights: Iterable[float], target_seconds: int, minimum: int = 4, maximum: int = 8) -> list[int] | None:
    values = [max(0.1, float(value)) for value in weights]
    if not values or target_seconds < len(values) * minimum or target_seconds > len(values) * maximum:
        return None
    total = sum(values)
    durations = [max(minimum, min(maximum, int(target_seconds * value / total))) for value in values]
    remaining = target_seconds - sum(durations)
    order = sorted(range(len(values)), key=lambda index: (values[index], -index), reverse=remaining > 0)
    cursor = 0
    while remaining:
        index = order[cursor % len(order)]
        if remaining > 0 and durations[index] < maximum:
            durations[index] += 1
            remaining -= 1
        elif remaining < 0 and durations[index] > minimum:
            durations[index] -= 1
            remaining += 1
        cursor += 1
        if cursor > len(order) * (maximum - minimum + abs(target_seconds)):
            return None
    return durations


def allocate_beat_budgets(
    beat_ids: Iterable[str],
    beats: Iterable[dict[str, Any]],
    target_seconds: int,
    *,
    minimum_per_shot: int = 4,
    shot_counts: dict[str, int] | None = None,
    maximum_per_shot: int = 8,
) -> dict[str, int] | None:
    """Allocate film time to beats before distributing time within each beat."""

    ids = list(dict.fromkeys(str(value) for value in beat_ids))
    beat_map = {str(beat.get("beat_id")): beat for beat in beats if isinstance(beat, dict)}
    counts = shot_counts or {beat_id: 1 for beat_id in ids}
    minimums = {beat_id: max(1, int(counts.get(beat_id, 1))) * minimum_per_shot for beat_id in ids}
    capacities = {beat_id: max(minimums[beat_id], int(counts.get(beat_id, 1)) * maximum_per_shot) for beat_id in ids}
    if not ids or target_seconds < sum(minimums.values()) or target_seconds > sum(capacities.values()):
        return None
    budgets = dict(minimums)
    remaining = target_seconds - sum(budgets.values())
    weights = {
        beat_id: max(0.1, float(beat_map.get(beat_id, {}).get("duration_weight", 1.0)))
        * max(0.1, float(beat_map.get(beat_id, {}).get("importance", 0.5)))
        for beat_id in ids
    }
    # Largest-remainder allocation makes absolute weight differences matter,
    # while capacity-aware redistribution keeps every shot within 4–8s.
    while remaining > 0:
        eligible = [beat_id for beat_id in ids if budgets[beat_id] < capacities[beat_id]]
        if not eligible:
            return None
        total_weight = sum(weights[beat_id] for beat_id in eligible)
        quotas = {beat_id: remaining * weights[beat_id] / total_weight for beat_id in eligible}
        allocations = {beat_id: min(capacities[beat_id] - budgets[beat_id], int(quotas[beat_id])) for beat_id in eligible}
        applied = sum(allocations.values())
        if applied == 0:
            beat_id = max(eligible, key=lambda value: (quotas[value] - int(quotas[value]), weights[value], -ids.index(value)))
            allocations[beat_id] = 1
            applied = 1
        for beat_id in eligible:
            addition = min(capacities[beat_id] - budgets[beat_id], allocations[beat_id])
            budgets[beat_id] += addition
        remaining -= sum(allocations.values())
    return budgets


def allocate_two_stage_durations(
    shot_beat_ids: Iterable[str],
    beats: Iterable[dict[str, Any]],
    target_seconds: int,
    *,
    shot_weights: Iterable[float] | None = None,
    minimum: int = 4,
    maximum: int = 8,
) -> list[int] | None:
    """Allocate Beat budget first, then Shot budget inside each Beat."""

    ids = [str(value) for value in shot_beat_ids]
    beat_order = list(dict.fromkeys(ids))
    counts = {beat_id: ids.count(beat_id) for beat_id in beat_order}
    budgets = allocate_beat_budgets(
        beat_order,
        beats,
        target_seconds,
        minimum_per_shot=minimum,
        shot_counts=counts,
        maximum_per_shot=maximum,
    )
    if budgets is None:
        return None
    weights = list(shot_weights or [])
    result: list[int] = [0] * len(ids)
    indices_by_beat: dict[str, list[int]] = {beat_id: [] for beat_id in beat_order}
    for index, beat_id in enumerate(ids):
        indices_by_beat[beat_id].append(index)
    for beat_id in beat_order:
        indices = indices_by_beat[beat_id]
        group_weights = [weights[index] for index in indices] if weights else [1.0] * len(indices)
        group = allocate_weighted_durations(group_weights, budgets[beat_id], minimum, maximum)
        if group is None:
            return None
        for index, duration in zip(indices, group):
            result[index] = duration
    return result


__all__ = [
    "STORY_FUNCTIONS",
    "TRANSITION_TYPES",
    "allocate_beat_budgets",
    "allocate_two_stage_durations",
    "allocate_weighted_durations",
    "beat_count_for_duration",
    "normalise_story_beat",
    "normalise_story_beats",
    "validate_beat_shot_mapping",
]
