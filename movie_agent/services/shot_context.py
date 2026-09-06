"""One resolved fact set shared by generation, memory, and visual QC."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from movie_agent.services.continuity import (
    resolve_character_locks,
    resolve_prop_locks,
    resolve_scene_lock,
)


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
    previous_visual_reference_allowed: bool = False
    previous_context_mode: str = "NONE"
    reference_requirements: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def transition_context_strategy(shot: Any, previous_shot: Any | None = None) -> dict[str, Any]:
    """Resolve both visual and narrative inheritance for one transition."""

    transition = str(getattr(shot, "transition_type", "CONTINUOUS") or "CONTINUOUS").upper()
    current_scene = str(getattr(shot, "scene_id", "") or "")
    previous_scene = str(getattr(previous_shot, "scene_id", "") or "") if previous_shot else ""
    same_scene = bool(previous_shot and (not current_scene or not previous_scene or current_scene == previous_scene))
    if transition == "CONTINUOUS":
        mode = "FULL_CONTINUITY" if same_scene else "NONE"
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
    allow_previous = bool(previous_shot and mode in {"FULL_CONTINUITY", "ACTION_CONTINUITY", "COMPOSITION_ONLY"} and not conflict)
    return {"mode": mode, "allow_previous": allow_previous, "same_scene": same_scene, "conflict": conflict}


def resolve_shot_context(
    shot: Any,
    visual_bible: dict[str, Any] | None,
    story_world: dict[str, Any] | None = None,
    previous_shot: Any | None = None,
) -> ResolvedShotContext:
    """Compile the exact active locks and transition semantics for a Shot."""

    del story_world  # Selectors are validated upstream; locks live in the Visual Bible.
    bible = visual_bible or {}
    strategy = transition_context_strategy(shot, previous_shot)
    transition = str(getattr(shot, "transition_type", "CONTINUOUS") or "CONTINUOUS").upper()
    scene_id = str(getattr(shot, "scene_id", "") or "")
    character_ids = [str(value) for value in (getattr(shot, "character_ids", []) or []) if str(value).strip()]
    prop_ids = [str(value) for value in (getattr(shot, "prop_ids", []) or []) if str(value).strip()]
    previous = previous_shot if strategy["allow_previous"] else None
    requirements = {
        "character": bool(character_ids),
        "scene": bool(scene_id),
        "props": bool(prop_ids),
        "previous_frame": bool(strategy["allow_previous"]),
        "missing_previous_frame_flag": "MISSING_PREVIOUS_ENDING_REFERENCE" if strategy["allow_previous"] else None,
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
        previous_shot_number=int(getattr(previous, "number", 0)) if previous else None,
        previous_scene_id=str(getattr(previous, "scene_id", "") or "") if previous else "",
        previous_ending_state=str(getattr(previous, "ending_state", "") or getattr(previous, "action", "") or "") if previous else "",
        previous_transition_hook=str(getattr(previous, "transition_hook", "") or "") if previous else "",
        transition_type=transition,
        previous_visual_reference_allowed=bool(strategy["allow_previous"]),
        previous_context_mode=str(strategy["mode"]),
        reference_requirements=requirements,
    )


__all__ = ["ResolvedShotContext", "resolve_shot_context", "transition_context_strategy"]
