"""Storyboard agent: creates renderable, continuity-aware shots."""

from typing import Any

from movie_agent.models import Shot
from movie_agent.services.mock_creator import build_storyboard
from movie_agent.services.llm import CreativeLLM, require_fields
from movie_agent.services.storyboard_quality import StoryboardRelevanceGate
from movie_agent.services.narrative import allocate_two_stage_durations, normalise_story_beats, validate_beat_shot_mapping
from movie_agent.services.state_ledger import validate_state_delta
from movie_agent.services.subtitles import shot_count_for_duration
from movie_agent.services.story_world import (
    canonicalize_story_world_references,
    resolve_story_world_reference,
    story_world_prompt,
    validate_story_world_references,
    world_entities,
)

_MIN_SHOT_SECONDS = 4
_MAX_SHOT_SECONDS = 8


def _parse_duration(raw: object) -> int:
    try:
        return int(round(float(raw)))  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError("Storyboard agent returned an unparseable shot duration.") from error


def _fit_durations(durations: list[int], target_seconds: int) -> list[int] | None:
    """Clamp each shot into 4–8s, then redistribute the remainder to hit the target."""

    fitted = [max(_MIN_SHOT_SECONDS, min(_MAX_SHOT_SECONDS, duration)) for duration in durations]
    difference = target_seconds - sum(fitted)
    index = 0
    while difference > 0:
        if all(duration >= _MAX_SHOT_SECONDS for duration in fitted):
            return None
        if fitted[index % len(fitted)] < _MAX_SHOT_SECONDS:
            fitted[index % len(fitted)] += 1
            difference -= 1
        index += 1
    while difference < 0:
        if all(duration <= _MIN_SHOT_SECONDS for duration in fitted):
            return None
        if fitted[index % len(fitted)] > _MIN_SHOT_SECONDS:
            fitted[index % len(fitted)] -= 1
            difference += 1
        index += 1
    return fitted


def _beat_for_shot(story_beats: list[dict[str, Any]], shot_index: int, total_shots: int) -> dict[str, str]:
    """Map a shot index to the closest story beat for narrative continuity."""

    if not story_beats:
        return {}
    beat_index = min(shot_index, len(story_beats) - 1)
    if len(story_beats) >= total_shots:
        beat_index = min(shot_index, len(story_beats) - 1)
    else:
        ratio = shot_index / max(1, total_shots - 1)
        beat_index = min(int(ratio * (len(story_beats) - 1)), len(story_beats) - 1)
    return story_beats[beat_index]


def _beat_id(beat: dict[str, Any], index: int) -> str:
    return str(beat.get("beat_id") or beat.get("id") or f"beat-{index + 1:02d}")


def _character_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _complexity(raw: Any, action: str, image_description: str) -> str:
    value = str(raw or "").upper().strip()
    if value in {"LOW", "MEDIUM", "HIGH"}:
        return value
    clauses = sum(action.count(marker) for marker in (",", ";", " and ", " then "))
    if clauses >= 3 or len(image_description.split()) > 42:
        return "HIGH"
    if clauses >= 1:
        return "MEDIUM"
    return "LOW"


def _enrich_shot(shot: Shot, beat: dict[str, Any], index: int) -> Shot:
    """Fill canonical fields without discarding legacy storyboard data."""

    shot.beat_id = _beat_id(beat, index) if beat else shot.beat_id or f"beat-{index + 1:02d}"
    shot.scene_id = str(beat.get("scene_id") or beat.get("scene") or shot.scene_id or "")
    shot.character_ids = _character_ids(beat.get("character_ids") if beat else None) or shot.character_ids
    shot.prop_ids = _character_ids(beat.get("prop_ids") if beat else None) or shot.prop_ids
    shot.story_function = str(
        beat.get("story_function") or beat.get("narrative_purpose") or shot.story_function or shot.narrative_purpose
    )
    raw_gain = beat.get("information_gain") if beat else None
    try:
        shot.information_gain = float(raw_gain if raw_gain is not None else shot.information_gain or 0.0)
    except (TypeError, ValueError):
        shot.information_gain = 0.0
    shot.emotional_shift = str(beat.get("emotional_shift") or beat.get("emotional_arc") or shot.emotional_shift or "")
    shot.visual_motif = str(beat.get("visual_motif") or shot.visual_motif or "")
    shot.continuity_from = str(beat.get("continuity_from") or shot.continuity_from or shot.starting_state or "")
    shot.continuity_to = str(beat.get("continuity_to") or shot.continuity_to or shot.ending_state or "")
    shot.shot_complexity = _complexity(shot.shot_complexity, shot.action, shot.image_description)
    return shot


def _previous_ending(shots: list[Shot], current_index: int) -> str:
    """Return the ending state of the previous shot for delta-prompt continuity."""

    if current_index <= 0 or not shots:
        return ""
    return shots[current_index - 1].ending_state or shots[current_index - 1].action


def _normalise_state_delta(
    raw: Any,
    story_world: dict[str, Any] | None,
    *,
    scene_id: str = "",
    character_ids: list[str] | None = None,
    prop_ids: list[str] | None = None,
) -> dict[str, Any]:
    delta = raw if isinstance(raw, dict) else {}
    active_ids = {
        "character": (character_ids or [""])[0] if len(character_ids or []) == 1 else "",
        "character_id": (character_ids or [""])[0] if len(character_ids or []) == 1 else "",
        "character_ids": (character_ids or [""])[0] if len(character_ids or []) == 1 else "",
        "scene": scene_id if scene_id else "",
        "scene_id": scene_id if scene_id else "",
        "prop": (prop_ids or [""])[0] if len(prop_ids or []) == 1 else "",
        "prop_id": (prop_ids or [""])[0] if len(prop_ids or []) == 1 else "",
        "prop_ids": (prop_ids or [""])[0] if len(prop_ids or []) == 1 else "",
    }
    normalized: dict[str, Any] = {}
    for entity, changes in delta.items():
        key = str(entity).strip()
        mapped = active_ids.get(key.casefold(), "")
        if not mapped:
            for kind in ("characters", "scenes", "props"):
                candidate = resolve_story_world_reference(key, story_world, kind)
                if candidate != key:
                    mapped = candidate
                    break
        target = mapped or key
        if target in normalized and isinstance(normalized[target], dict) and isinstance(changes, dict):
            normalized[target].update(changes)
        else:
            normalized[target] = changes
    delta = normalized
    validation = validate_state_delta(delta, story_world)
    if not validation["valid"]:
        raise ValueError(f"STATE_LEDGER_REVIEW_REQUIRED: {validation['errors']}")
    return delta


def _normalise_transition_types(shots: list[Shot]) -> None:
    """Make scene changes explicit when a model leaves the transition default."""

    previous_scene = ""
    for shot in shots:
        current_scene = str(shot.scene_id or "").strip()
        if previous_scene and current_scene and previous_scene != current_scene and shot.transition_type == "CONTINUOUS":
            shot.transition_type = "HARD_CUT"
            shot.qc_flags.append("TRANSITION_TYPE_NORMALIZED")
            details = dict(shot.qc_details or {})
            planning = dict(details.get("planning") or {})
            planning["transition_normalization"] = "scene_change_requires_hard_cut"
            details["planning"] = planning
            shot.qc_details = details
        previous_scene = current_scene or previous_scene


def _mock_state_delta(shot: Shot, index: int, total_shots: int, story_world: dict[str, Any] | None) -> dict[str, Any]:
    """Emit small deterministic deltas so Mock exercises the real state ledger."""

    characters = world_entities(story_world, "characters") if story_world else []
    props = world_entities(story_world, "props") if story_world else []
    character_id = str((characters[0] if characters else {}).get("character_id") or (shot.character_ids or ["protagonist"])[0])
    prop_id = str((props[0] if props else {}).get("prop_id") or (shot.prop_ids or [""])[0])
    scene_entities = world_entities(story_world, "scenes") if story_world else []
    scene_id = str(shot.scene_id or ((scene_entities[0] if scene_entities else {}).get("scene_id") or "primary"))
    if index == 0:
        return {character_id: {"emotion": "focused", "location": scene_id}}
    if index == min(2, max(0, total_shots - 1)):
        if prop_id:
            return {prop_id: {"status": "anomalous", "screen_state": "signal detected"}}
        return {character_id: {"emotion": "alert"}}
    if index == total_shots - 1:
        return {character_id: {"emotion": "resolved"}, scene_id: {"time_state": "after the turning point"}}
    return {}


class StoryboardAgent:
    def __init__(
        self,
        llm: CreativeLLM | None = None,
        allowed_generation_modes: set[str] | None = None,
    ) -> None:
        self.llm = llm
        self.allowed_generation_modes = allowed_generation_modes or {"T2V", "I2V", "R2V"}

    def create(
        self,
        idea: str,
        duration_seconds: int,
        visual_style: str,
        project_id: str,
        brief: dict[str, str],
        script: dict[str, str],
        visual_bible: dict[str, str],
        story_beats: list[dict[str, Any]] | None = None,
        story_world: dict[str, Any] | None = None,
    ) -> list[Shot]:
        beats = normalise_story_beats(story_beats)
        if story_world:
            unknown = validate_story_world_references(beats, story_world)
            if any(unknown.values()):
                raise ValueError(f"STORY_WORLD_REVIEW_REQUIRED: {unknown}")
        if self.llm:
            requested_shot_count = shot_count_for_duration(duration_seconds)
            beats_context = ""
            if beats:
                beats_lines = [
                    f"  Beat {b.get('beat_id')}: scene={b.get('scene_id','')}, characters={b.get('character_ids',[])}, "
                    f"function={b.get('story_function','')}, purpose={b.get('narrative_purpose','')}, "
                    f"information_gain={b.get('information_gain',0)}, duration_weight={b.get('duration_weight',1)}, "
                    f"arc={b.get('emotional_arc','')}, start={b.get('starting_state','')}, "
                    f"end={b.get('ending_state','')}, hook={b.get('transition_hook','')}"
                    for i, b in enumerate(beats)
                ]
                beats_context = "\nStory beats (maintain continuity across shots):\n" + "\n".join(beats_lines)
            result = self.llm.complete_json(
                "You are a film storyboard artist. Break the story into a continuous sequence of "
                "original sci-fi shots that form a coherent film, not independent clips. "
                f"Each shot 4-8 seconds. Return exactly {requested_shot_count} shots (not fewer or more), "
                "avoid complex multi-person interactions and existing film/TV IP. "
                f"Available generation modes: {', '.join(sorted(self.allowed_generation_modes))}. "
                "The sum of all shot duration_seconds must equal the total duration exactly. "
                "IMPORTANT: Each shot prompt must describe only the DELTA from the previous shot — "
                "what changes, not a full scene reset. Every shot MUST explicitly reference one beat_id from the supplied beats. "
                "Do not invent beat IDs or emit orphan shots. Include every requested schema field.",
                (
                    f"Idea: {idea}\nTotal duration: {duration_seconds} seconds\nStyle: {visual_style}\n"
                    f"{story_world_prompt(story_world)}\n"
                    f"Director brief: {brief}\nScript: {script}\nVisual bible: {visual_bible}"
                    f"{beats_context}\n"
                    "Keep text concise to control generation time: image_description and action each no more than 40 words, "
                    "sound_design no more than 15 words, prompt is a video generation prompt describing only the DELTA "
                    "from the previous shot in no more than 60 words. "
                    "STATE DELTA RULES: Only emit mutable production state that changes during this shot. "
                    "Good examples: prop.status, prop.owner, prop.position, prop.screen_state; "
                    "character.emotion, character.location, character.held_props, character.costume_state, character.physical_condition; "
                    "scene.time_state, scene.lighting_state, scene.environment_change. "
                    "Bad examples: character.name, character.face, scene architecture, permanent appearance. "
                    "Those belong to Story World or Visual Bible. Every state_delta top-level key MUST be a canonical "
                    "character_id, scene_id, or prop_id from the registry; use {} when no mutable state changes. "
                    "Use English framing terms (wide shot, medium close-up, close-up, over-the-shoulder, low-angle medium, insert shot). "
                    "Return JSON: {\"shots\":[{\"duration_seconds\":6,\"framing\":\"medium close-up\","
                    "\"image_description\":\"...\",\"action\":\"...\",\"sound_design\":\"...\","
                    "\"generation_mode\":\"T2V\",\"prompt\":\"...\",\"beat_id\":\"beat-01\","
                    "\"scene_id\":\"...\",\"character_ids\":[],\"prop_ids\":[],\"story_function\":\"...\","
                    "\"narrative_purpose\":\"...\",\"information_gain\":0.5,\"emotional_shift\":\"...\","
                    "\"visual_motif\":\"...\",\"starting_state\":\"...\",\"main_action\":\"...\","
                    "\"secondary_action\":\"...\",\"environment_reaction\":\"...\",\"character_reaction\":\"...\","
                    "\"ending_state\":\"...\",\"transition_hook\":\"...\",\"transition_type\":\"CONTINUOUS\",\"speech_policy\":\"SILENT|DIALOGUE|NARRATION|VOICE_OVER|SYSTEM_VOICE|AMBIENCE_ONLY\","
                    "\"shot_complexity\":\"LOW|MEDIUM|HIGH\",\"state_delta\":{}}]}."
                ),
            )
            raw_shots = result.get("shots")
            raw_shots = canonicalize_story_world_references(raw_shots, story_world)
            if not isinstance(raw_shots, list) or not 6 <= len(raw_shots) <= 10:
                raise ValueError("Storyboard agent did not return 6-10 shots.")
            for raw_shot in raw_shots:
                if not isinstance(raw_shot, dict):
                    raise ValueError("Storyboard agent returned an invalid shot.")
                require_fields(
                    raw_shot,
                    ("duration_seconds", "framing", "image_description", "action", "sound_design", "generation_mode", "prompt"),
                    agent="Storyboard",
                )
            raw_durations = [_parse_duration(raw_shot.get("duration_seconds")) for raw_shot in raw_shots]
            beat_by_id = {str(beat["beat_id"]): beat for beat in beats}
            requested_beats = [
                beat_by_id.get(str(raw.get("beat_id"))) or _beat_for_shot(beats, index, len(raw_shots))
                for index, raw in enumerate(raw_shots)
            ]
            fitted_durations = allocate_two_stage_durations(
                [str(raw.get("beat_id") or _beat_id(beat, index)) for index, (raw, beat) in enumerate(zip(raw_shots, requested_beats))],
                beats,
                duration_seconds,
                shot_weights=[1.25 if str(raw.get("shot_complexity", "")).upper() == "HIGH" else 1.0 for raw in raw_shots],
            ) or _fit_durations(raw_durations, duration_seconds)
            if fitted_durations is None:
                raise ValueError(
                    f"Storyboard agent's shots cannot fit within 4-8 second range to total {duration_seconds} seconds; please restart."
                )
            shots: list[Shot] = []
            for number, raw_shot in enumerate(raw_shots, start=1):
                shot_duration = fitted_durations[number - 1]
                mode = str(raw_shot["generation_mode"]).upper()
                if mode not in self.allowed_generation_modes:
                    allowed = ", ".join(sorted(self.allowed_generation_modes))
                    raise ValueError(f"Storyboard agent used unsupported generation mode: {mode} (only {allowed} supported).")
                beat = beat_by_id.get(str(raw_shot.get("beat_id"))) or requested_beats[number - 1]
                shots.append(
                    _enrich_shot(Shot(
                        number=number,
                        duration_seconds=shot_duration,
                        framing=str(raw_shot["framing"]),
                        image_description=str(raw_shot["image_description"]),
                        action=str(raw_shot["action"]),
                        sound_design=str(raw_shot["sound_design"]),
                        generation_mode=mode,
                        prompt=str(raw_shot["prompt"]),
                        output_placeholder=f"outputs/{project_id}/shot-{number:02d}.mp4",
                        narrative_purpose=str(raw_shot.get("narrative_purpose") or beat.get("narrative_purpose", "")),
                        starting_state=str(raw_shot.get("starting_state") or beat.get("starting_state", "")),
                        main_action=str(raw_shot.get("main_action") or raw_shot["action"]),
                        secondary_action=str(raw_shot.get("secondary_action", "")),
                        environment_reaction=str(raw_shot.get("environment_reaction", "")),
                        character_reaction=str(raw_shot.get("character_reaction", "")),
                        ending_state=str(raw_shot.get("ending_state") or beat.get("ending_state", "")),
                        transition_hook=str(raw_shot.get("transition_hook") or beat.get("transition_hook", "")),
                        beat_id=str(raw_shot.get("beat_id") or _beat_id(beat, number - 1)),
                        scene_id=str(raw_shot.get("scene_id") or beat.get("scene_id") or beat.get("scene") or ""),
                        character_ids=_character_ids(raw_shot.get("character_ids") or beat.get("character_ids")),
                        prop_ids=_character_ids(raw_shot.get("prop_ids") or beat.get("prop_ids")),
                        story_function=str(raw_shot.get("story_function") or raw_shot.get("narrative_purpose") or beat.get("story_function") or beat.get("narrative_purpose", "")),
                        information_gain=float(raw_shot.get("information_gain") or beat.get("information_gain") or 0.0),
                        emotional_shift=str(raw_shot.get("emotional_shift") or beat.get("emotional_shift") or beat.get("emotional_arc", "")),
                        visual_motif=str(raw_shot.get("visual_motif") or beat.get("visual_motif", "")),
                        continuity_from=str(raw_shot.get("continuity_from") or beat.get("continuity_from") or raw_shot.get("starting_state") or ""),
                        continuity_to=str(raw_shot.get("continuity_to") or beat.get("continuity_to") or raw_shot.get("ending_state") or ""),
                        shot_complexity=_complexity(raw_shot.get("shot_complexity"), str(raw_shot["action"]), str(raw_shot["image_description"])),
                        transition_type=str(raw_shot.get("transition_type") or "CONTINUOUS").upper(),
                        speech_policy=str(raw_shot.get("speech_policy") or "NARRATION").upper(),
                        state_delta=_normalise_state_delta(
                            raw_shot.get("state_delta") or {},
                            story_world,
                            scene_id=str(raw_shot.get("scene_id") or beat.get("scene_id") or beat.get("scene") or ""),
                            character_ids=_character_ids(raw_shot.get("character_ids") or beat.get("character_ids")),
                            prop_ids=_character_ids(raw_shot.get("prop_ids") or beat.get("prop_ids")),
                        ),
                    ), beat, number - 1)
                )
            if story_world:
                unknown = validate_story_world_references([shot.to_dict() for shot in shots], story_world)
                if any(unknown.values()):
                    raise ValueError(f"STORY_WORLD_REVIEW_REQUIRED: {unknown}")
            _normalise_transition_types(shots)
            mapping = validate_beat_shot_mapping(shots, beats)
            for shot in shots:
                planning = dict((shot.qc_details or {}).get("planning") or {})
                planning["beat_mapping"] = mapping
                shot.qc_details = {**(shot.qc_details or {}), "planning": planning}
                if not mapping["valid"] and "BEAT_MAPPING_REVIEW" not in shot.qc_flags:
                    shot.qc_flags.append("BEAT_MAPPING_REVIEW")
            StoryboardRelevanceGate().annotate(shots, beats)
            return shots
        shots = build_storyboard(idea, duration_seconds, visual_style, project_id, story_beats=beats)
        mock_durations = allocate_two_stage_durations(
            [shot.beat_id for shot in shots],
            beats,
            duration_seconds,
        )
        if mock_durations:
            for shot, shot_duration in zip(shots, mock_durations):
                shot.duration_seconds = shot_duration
                shot.source_duration_seconds = shot_duration
                shot.desired_duration = float(shot_duration)
        if self.allowed_generation_modes == {"T2V"}:
            for shot in shots:
                shot.generation_mode = "T2V"
        for index, shot in enumerate(shots):
            shot.state_delta = _normalise_state_delta(
                _mock_state_delta(shot, index, len(shots), story_world),
                story_world,
            )
        mapping = validate_beat_shot_mapping(shots, beats)
        if story_world:
            unknown = validate_story_world_references([shot.to_dict() for shot in shots], story_world)
            if any(unknown.values()):
                raise ValueError(f"STORY_WORLD_REVIEW_REQUIRED: {unknown}")
        _normalise_transition_types(shots)
        for shot in shots:
            planning = dict((shot.qc_details or {}).get("planning") or {})
            planning["beat_mapping"] = mapping
            shot.qc_details = {**(shot.qc_details or {}), "planning": planning}
        StoryboardRelevanceGate().annotate(shots, beats)
        return shots

    @staticmethod
    def review_storyboard(shots: list[Shot], story_beats: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return StoryboardRelevanceGate().review_storyboard(shots, story_beats)

    def repair_shots(
        self,
        shots: list[Shot],
        story_beats: list[dict[str, Any]],
        visual_bible: dict[str, Any] | None = None,
        story_world: dict[str, Any] | None = None,
        *,
        max_passes: int = 1,
    ) -> list[Shot]:
        """Repair only flagged shots once, preserving the board structure."""

        if max_passes < 1:
            return shots
        beats = normalise_story_beats(story_beats)
        beat_by_id = {str(beat["beat_id"]): beat for beat in beats}
        repair_flags = {"LOW_RELEVANCE_SHOT", "REDUNDANT_SHOT", "SHOT_TOO_COMPLEX", "NARRATIVE_STATE_DRIFT", "TRANSITION_CONFLICT"}
        for index, shot in enumerate(shots):
            flags = [flag for flag in shot.qc_flags if flag in repair_flags]
            if not flags:
                continue
            beat = beat_by_id.get(shot.beat_id) or {}
            previous = shots[index - 1] if index else None
            following = shots[index + 1] if index + 1 < len(shots) else None
            payload: dict[str, Any] | None = None
            if self.llm:
                result = self.llm.complete_json(
                    "You are repairing one flagged storyboard shot. Return only the repaired shot fields. "
                    "Preserve beat_id, narrative purpose, story structure, visual continuity, and English output. "
                    "Do not rewrite unrelated shots.",
                    f"FLAGS: {flags}\nBEAT: {beat}\nPREVIOUS: {previous.to_dict() if previous else {}}\n"
                    f"CURRENT: {shot.to_dict()}\nNEXT: {following.to_dict() if following else {}}\n"
                    f"CANONICAL STORY WORLD: {story_world or {}}\nVISUAL BIBLE: {visual_bible or {}}\n"
                    "Preserve the structural selectors beat_id, scene_id, character_ids, and prop_ids unless this is explicitly a WORLD_CONTEXT_REPAIR. "
                    "Return JSON with beat_id, scene_id, character_ids, prop_ids, story_function, narrative_purpose, "
                    "information_gain, emotional_shift, visual_motif, starting_state, main_action, "
                    "secondary_action, environment_reaction, character_reaction, ending_state, transition_hook, "
                    "transition_type, shot_complexity, prompt, state_delta. Preserve the existing state_delta for "
                    "ordinary relevance repairs; if main_action or ending_state changes its meaning, return a new "
                    "canonical state_delta that matches the repaired action.",
                )
                payload = result.get("shot") if isinstance(result.get("shot"), dict) else result
            if not isinstance(payload, dict):
                payload = {}
                if "LOW_RELEVANCE_SHOT" in flags:
                    shot.information_gain = max(shot.information_gain, 0.65)
                    shot.secondary_action = shot.secondary_action or "The protagonist notices a consequential change."
                if "REDUNDANT_SHOT" in flags:
                    shot.story_function = f"{shot.story_function} with a new consequence".strip()
                    shot.information_gain = max(shot.information_gain, 0.6)
                    shot.image_description = "A distinct consequence appears in a new composition."
                    shot.main_action = "The protagonist reacts to the changed signal."
                if "SHOT_TOO_COMPLEX" in flags:
                    shot.main_action = shot.main_action.split(",", 1)[0].strip() or shot.action
                    shot.secondary_action = ""
                    shot.environment_reaction = ""
                    shot.shot_complexity = "MEDIUM"
                if "NARRATIVE_STATE_DRIFT" in flags and previous:
                    shot.starting_state = previous.ending_state or previous.action
                    shot.continuity_from = shot.starting_state
                    shot.transition_hook = shot.transition_hook or "Continue directly from the previous state."
                continue
            # The beat and world selectors are structural and may not be
            # changed by an ordinary relevance repair.
            payload["beat_id"] = shot.beat_id or str(beat.get("beat_id") or "")
            for selector in ("scene_id", "character_ids", "prop_ids"):
                if selector in payload and payload[selector] != getattr(shot, selector):
                    if "WORLD_CONTEXT_REPAIR" not in flags:
                        payload[selector] = getattr(shot, selector)
                    else:
                        shot.qc_flags.append("WORLD_CONTEXT_REPAIR")
            for key in (
                "story_function", "narrative_purpose", "information_gain",
                "emotional_shift", "visual_motif", "starting_state", "main_action", "secondary_action",
                "environment_reaction", "character_reaction", "ending_state", "transition_hook",
                "transition_type", "shot_complexity", "prompt", "speech_policy",
            ):
                if key in payload:
                    setattr(shot, key, payload[key])
            if "state_delta" in payload:
                shot.state_delta = _normalise_state_delta(payload["state_delta"], story_world)
        if story_world:
            unknown = validate_story_world_references([shot.to_dict() for shot in shots], story_world)
            if any(unknown.values()):
                raise ValueError(f"REPAIR_WORLD_CONFLICT: {unknown}")
        StoryboardRelevanceGate().annotate(shots, beats)
        return shots

    def revise(self, shot: Shot, visual_bible: dict[str, str], previous_shot: Shot | None = None) -> Shot:
        """Refresh one render prompt while retaining narrative beat and duration."""

        continuity_prefix = ""
        if previous_shot:
            prev_ending = previous_shot.ending_state or previous_shot.action
            continuity_prefix = f"Continuing from previous shot: {prev_ending}. "
        revised_prompt = f"{continuity_prefix}Shot delta revision: {shot.prompt}"
        return Shot(
            number=shot.number,
            duration_seconds=shot.duration_seconds,
            framing=shot.framing,
            image_description=shot.image_description,
            action=shot.action,
            sound_design=shot.sound_design,
            generation_mode=shot.generation_mode,
            prompt=revised_prompt,
            output_placeholder=shot.output_placeholder,
            status="replanned",
            attempts=shot.attempts + 1,
            narrative_purpose=shot.narrative_purpose,
            starting_state=shot.starting_state,
            main_action=shot.main_action,
            secondary_action=shot.secondary_action,
            environment_reaction=shot.environment_reaction,
            character_reaction=shot.character_reaction,
            ending_state=shot.ending_state,
            transition_hook=shot.transition_hook,
            desired_duration=shot.desired_duration,
            source_duration_seconds=shot.source_duration_seconds,
            timing_mode=shot.timing_mode,
            qc_flags=list(shot.qc_flags),
            media_assets={key: dict(value) if isinstance(value, dict) else value for key, value in shot.media_assets.items()},
            compiled_generation_prompt="",
            generation_seed=None,
            revision=shot.revision,
            prompt_hash=shot.prompt_hash,
            provider=shot.provider,
            model=shot.model,
            seed=shot.seed,
            created_at=shot.created_at,
            qc_status="STALE",
            source_resolution=shot.source_resolution,
            source_fps=shot.source_fps,
            source_duration=shot.source_duration,
            stale=True,
            asset_history=list(shot.asset_history),
            beat_id=shot.beat_id,
            scene_id=shot.scene_id,
            character_ids=list(shot.character_ids),
            prop_ids=list(shot.prop_ids),
            story_function=shot.story_function,
            information_gain=shot.information_gain,
            emotional_shift=shot.emotional_shift,
            visual_motif=shot.visual_motif,
            continuity_from=shot.continuity_from,
            continuity_to=shot.continuity_to,
            shot_complexity=shot.shot_complexity,
            transition_type=shot.transition_type,
            speech_policy=shot.speech_policy,
            state_delta=dict(shot.state_delta or {}),
        )
