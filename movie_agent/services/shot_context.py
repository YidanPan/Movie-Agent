"""One resolved fact set shared by generation, memory, and visual QC."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from movie_agent.services.continuity import (
    resolve_character_locks,
    resolve_prop_locks,
    resolve_scene_lock,
)
from movie_agent.services.story_world import entity_ids


@dataclass(frozen=True)
class ResolvedShotContext:
    shot_number: int
    beat_id: str
    scene_id: str
    scene_lock: dict[str, Any]
    character_ids: list[str]
    character_locks: list[dict[str, Any]]
    prop_ids: list[str]
    prop_locks: list[dict[str, Any]]
    cinematography_lock: str
    previous_shot_number: int | None = None
    previous_scene_id: str = ""
    previous_ending_state: str = ""
    previous_transition_hook: str = ""
    transition_type: str = "CONTINUOUS"
    inherit_previous_narrative_context: bool = False
    allow_previous_visual_reference: bool = False
    previous_narrative_hook: str = ""
    previous_narrative_state: str = ""
    previous_visual_reference_role: str = "NONE"
    previous_context_mode: str = "NONE"
    reference_requirements: dict[str, Any] = field(default_factory=dict)
    missing_entities: dict[str, list[str]] = field(default_factory=dict)
    missing_locks: dict[str, list[str]] = field(default_factory=dict)
    context_flags: list[str] = field(default_factory=list)
    entity_state_before: dict[str, Any] = field(default_factory=dict)
    entity_state_delta: dict[str, Any] = field(default_factory=dict)
    entity_state_after: dict[str, Any] = field(default_factory=dict)

    @property
    def previous_visual_reference_allowed(self) -> bool:
        """Compatibility alias for older reference-bank consumers."""

        return self.allow_previous_visual_reference

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def transition_context_strategy(shot: Any, previous_shot: Any | None = None) -> dict[str, Any]:
    """Resolve both visual and narrative inheritance for one transition."""

    transition = str(getattr(shot, "transition_type", "CONTINUOUS") or "CONTINUOUS").upper()
    current_scene = str(getattr(shot, "scene_id", "") or "")
    previous_scene = str(getattr(previous_shot, "scene_id", "") or "") if previous_shot else ""
    same_scene = bool(previous_shot and (not current_scene or not previous_scene or current_scene == previous_scene))
    if transition == "CONTINUOUS":
        mode = "FULL_CONTINUITY" if same_scene else "NARRATIVE_ONLY"
        conflict = bool(previous_shot and current_scene and previous_scene and current_scene != previous_scene)
    elif transition == "ACTION_MATCH":
        mode, conflict = "ACTION_CONTINUITY", False
    elif transition == "MATCH_CUT":
        mode, conflict = "COMPOSITION_ONLY", False
    elif transition == "AUDIO_BRIDGE":
        mode, conflict = "NARRATIVE_ONLY", False
    elif transition in {"HARD_CUT", "ELLIPSIS"}:
        mode, conflict = "NARRATIVE_ONLY", False
    elif transition in {"FADE", "DISSOLVE"}:
        mode, conflict = ("FULL_CONTINUITY" if same_scene else "NARRATIVE_ONLY"), False
    else:
        mode, conflict = "NONE", False
    has_previous = bool(previous_shot)
    inherit_narrative = has_previous and transition != "MATCH_CUT" and transition != "NONE"
    if transition == "CONTINUOUS" and not same_scene:
        inherit_narrative = has_previous
    allow_visual = bool(has_previous and mode in {"FULL_CONTINUITY", "ACTION_CONTINUITY", "COMPOSITION_ONLY"} and not conflict)
    role = "NONE"
    if allow_visual:
        role = "COMPOSITION" if mode == "COMPOSITION_ONLY" else ("ACTION" if mode == "ACTION_CONTINUITY" else "FULL")
    return {
        "mode": mode,
        "inherit_previous_narrative_context": inherit_narrative,
        "allow_previous_visual_reference": allow_visual,
        "previous_visual_reference_role": role,
        "same_scene": same_scene,
        "conflict": conflict,
    }


def _structured_lock_exists(bible: dict[str, Any], kind: str, entity_id: str) -> bool:
    """Return whether a specific entity has a usable Visual Bible lock."""

    prefix = kind[:-1]
    value = bible.get(kind)
    if isinstance(value, dict):
        item = value.get(entity_id)
        if isinstance(item, dict):
            return any(str(item.get(key) or "").strip() for key in _LOCK_FIELDS[kind])
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and str(item.get(f"{prefix}_id") or item.get("id") or "") == entity_id:
                return any(str(item.get(key) or "").strip() for key in _LOCK_FIELDS[kind])
        return False
    # Legacy projects only have global lock cards. They remain usable when no
    # structured selector exists, but a structured selector must not silently
    # fall back to an unrelated global card.
    return bool(str(bible.get(_GLOBAL_LOCK_KEYS[kind]) or "").strip())


_LOCK_FIELDS = {
    "characters": ("appearance_lock", "face_lock", "hair_lock", "costume_lock", "silhouette_lock", "lock"),
    "scenes": ("environment_lock", "architecture_lock", "lighting_lock", "palette_lock", "lock"),
    "props": ("appearance_lock", "material_lock", "color_lock", "state_rules", "lock"),
}
_GLOBAL_LOCK_KEYS = {"characters": "character_lock", "scenes": "scene_lock", "props": "prop_lock"}


def _runtime_validation(
    scene_id: str,
    character_ids: list[str],
    prop_ids: list[str],
    story_world: dict[str, Any] | None,
    bible: dict[str, Any],
) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str]]:
    missing_entities = {"scenes": [], "characters": [], "props": []}
    missing_locks = {"scenes": [], "characters": [], "props": []}
    if story_world is None:
        return missing_entities, missing_locks, []
    requested = {"scenes": [scene_id] if scene_id else [], "characters": character_ids, "props": prop_ids}
    for kind, ids in requested.items():
        known = entity_ids(story_world, kind)
        for entity_id in ids:
            if entity_id not in known:
                missing_entities[kind].append(entity_id)
            elif not _structured_lock_exists(bible, kind, entity_id):
                missing_locks[kind].append(entity_id)
    flags: list[str] = []
    for kind, prefix in (("scenes", "SCENE"), ("characters", "CHARACTER"), ("props", "PROP")):
        if missing_entities[kind]:
            flags.append(f"UNKNOWN_{prefix}_ID")
        if missing_locks[kind]:
            flags.append(f"MISSING_{prefix}_LOCK")
    return missing_entities, missing_locks, flags


def _merge_state(before: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    result = {key: value.copy() if isinstance(value, dict) else value for key, value in (before or {}).items()}
    for entity, changes in (delta or {}).items():
        if isinstance(changes, dict):
            current = result.get(str(entity))
            if not isinstance(current, dict):
                current = {}
            current.update(changes)
            result[str(entity)] = current
        else:
            result[str(entity)] = changes
    return result


def resolve_shot_context(
    shot: Any,
    visual_bible: dict[str, Any] | None,
    story_world: dict[str, Any] | None = None,
    previous_shot: Any | None = None,
    *,
    entity_state_before: dict[str, Any] | None = None,
    entity_state_delta: dict[str, Any] | None = None,
    entity_state_after: dict[str, Any] | None = None,
) -> ResolvedShotContext:
    """Compile the exact active locks and transition semantics for a Shot."""

    bible = visual_bible or {}
    strategy = transition_context_strategy(shot, previous_shot)
    transition = str(getattr(shot, "transition_type", "CONTINUOUS") or "CONTINUOUS").upper()
    scene_id = str(getattr(shot, "scene_id", "") or "")
    character_ids = [str(value) for value in (getattr(shot, "character_ids", []) or []) if str(value).strip()]
    prop_ids = [str(value) for value in (getattr(shot, "prop_ids", []) or []) if str(value).strip()]
    narrative_previous = previous_shot if strategy["inherit_previous_narrative_context"] else None
    visual_previous = previous_shot if strategy["allow_previous_visual_reference"] else None
    missing_entities, missing_locks, context_flags = _runtime_validation(
        scene_id, character_ids, prop_ids, story_world, bible
    )
    before_state = dict(entity_state_before or {})
    delta_state = dict(entity_state_delta if entity_state_delta is not None else (getattr(shot, "state_delta", {}) or {}))
    after_state = dict(entity_state_after) if entity_state_after is not None else _merge_state(before_state, delta_state)
    requirements = {
        "character": bool(character_ids),
        "scene": bool(scene_id),
        "props": bool(prop_ids),
        "previous_frame": bool(strategy["allow_previous_visual_reference"]),
        "missing_previous_frame_flag": "MISSING_PREVIOUS_ENDING_REFERENCE" if strategy["allow_previous_visual_reference"] else None,
        "inherit_previous_narrative_context": bool(strategy["inherit_previous_narrative_context"]),
        "allow_previous_visual_reference": bool(strategy["allow_previous_visual_reference"]),
    }
    return ResolvedShotContext(
        shot_number=int(getattr(shot, "number", 0) or 0),
        beat_id=str(getattr(shot, "beat_id", "") or ""),
        scene_id=scene_id,
        scene_lock=resolve_scene_lock(bible, scene_id),
        character_ids=character_ids,
        character_locks=resolve_character_locks(bible, character_ids),
        prop_ids=prop_ids,
        prop_locks=resolve_prop_locks(bible, prop_ids),
        cinematography_lock=str(bible.get("cinematography_lock") or bible.get("style_card") or ""),
        previous_shot_number=int(getattr(narrative_previous or visual_previous, "number", 0)) if (narrative_previous or visual_previous) else None,
        previous_scene_id=str(getattr(narrative_previous or visual_previous, "scene_id", "") or "") if (narrative_previous or visual_previous) else "",
        previous_ending_state=str(getattr(narrative_previous, "ending_state", "") or getattr(narrative_previous, "action", "") or "") if narrative_previous else "",
        previous_transition_hook=str(getattr(narrative_previous, "transition_hook", "") or "") if narrative_previous else "",
        transition_type=transition,
        inherit_previous_narrative_context=bool(strategy["inherit_previous_narrative_context"]),
        allow_previous_visual_reference=bool(strategy["allow_previous_visual_reference"]),
        previous_narrative_hook=str(getattr(narrative_previous, "transition_hook", "") or "") if narrative_previous else "",
        previous_narrative_state=str(getattr(narrative_previous, "ending_state", "") or getattr(narrative_previous, "action", "") or "") if narrative_previous else "",
        previous_visual_reference_role=str(strategy["previous_visual_reference_role"]),
        previous_context_mode=str(strategy["mode"]),
        reference_requirements=requirements,
        missing_entities=missing_entities,
        missing_locks=missing_locks,
        context_flags=context_flags,
        entity_state_before=before_state,
        entity_state_delta=delta_state,
        entity_state_after=after_state,
    )


__all__ = ["ResolvedShotContext", "resolve_shot_context", "transition_context_strategy"]
