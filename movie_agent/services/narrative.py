"""Canonical Story Beat/Shot planning contracts."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


STORY_FUNCTIONS = {"SETUP", "ROUTINE", "ANOMALY", "RECOGNITION", "ESCALATION", "CLIMAX", "AFTERMATH", "ATMOSPHERE", "RHYTHM", "FORESHADOW"}
TRANSITION_TYPES = {"CONTINUOUS", "HARD_CUT", "MATCH_CUT", "AUDIO_BRIDGE", "ACTION_MATCH", "ELLIPSIS", "FADE", "DISSOLVE"}


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


__all__ = ["STORY_FUNCTIONS", "TRANSITION_TYPES", "allocate_weighted_durations", "normalise_story_beat", "normalise_story_beats", "validate_beat_shot_mapping"]
