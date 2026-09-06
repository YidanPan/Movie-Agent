"""Writer agent: creates a screenplay plus the canonical dialogue/subtitle assets."""

from typing import Any

from movie_agent.services.llm import CreativeLLM
from movie_agent.services.subtitles import align_script_to_shots, ensure_dialogue_assets, shot_count_for_duration
from movie_agent.services.narrative import beat_count_for_duration, normalise_story_beats
from movie_agent.services.story_world import story_world_prompt, validate_story_world_references


def _as_text(value: Any) -> str:
    """Flatten structured model output (list/dict) into readable prose."""

    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, (list, tuple)):
        parts = [_as_text(item) for item in value]
        return "; ".join(part for part in parts if part)
    return str(value)


class WriterAgent:
    def __init__(self, llm: CreativeLLM | None = None) -> None:
        self.llm = llm

    def write(
        self,
        idea: str,
        brief: dict[str, str],
        *,
        duration_seconds: int = 48,
        shot_count: int | None = None,
    ) -> dict[str, Any]:
        planned_shot_count = shot_count or shot_count_for_duration(duration_seconds)
        if self.llm:
            result = self.llm.complete_json(
                "You are a sci-fi short film screenwriter. Stories must be original, concise, "
                "decomposable into 4-8 second shots, avoid existing film/TV IP. All output must be in English.",
                f"Idea: {idea}\nDirector brief: {brief}\n"
                f"Write a 30-80 second short film, pre-broken into {planned_shot_count} shots. "
                "Return keys: story, narration, outline, dialogue_book, subtitle_track. "
                "story and narration must be coherent English paragraphs, not lists or JSON fragments. "
                "outline should be 3-5 sentences summarising the story arc. "
                "dialogue_book and subtitle_track return arrays keyed by shot number, "
                "each item containing shot, speaker, text, kind, start_seconds, end_seconds; "
                "if there is no character dialogue, use speaker=NARRATOR, kind=narration; lines should be short and audible.",
            )
            script = {
                "story": _as_text(result["story"]),
                "narration": _as_text(result["narration"]),
                "outline": _as_text(result.get("outline", "")),
            }
            script["dialogue_book"] = result.get("dialogue_book")
            script["subtitle_track"] = result.get("subtitle_track")
            return ensure_dialogue_assets(
                script,
                duration_seconds=duration_seconds,
                shot_count=planned_shot_count,
            )
        script = {
            "story": (
                f"The protagonist occupies a quiet, highly automated space. {idea} "
                "They first dismiss the anomaly as system noise, then realise the subtle change "
                "is forcing them to make a choice. "
                "The ending explains nothing — it leaves only an action that echoes the opening."
            ),
            "narration": "Perhaps the hardest thing to automate in the future is not work, but deciding when to trust yourself.",
            "outline": (
                "Opening: the protagonist carries out routine tasks in an automated space; everything is orderly. "
                "Development: a small anomaly appears; the protagonist initially treats it as system noise. "
                "Turning point: the anomaly accumulates; the protagonist is forced to confront what it means. "
                "Climax: the protagonist makes a choice that breaks convention. "
                "Ending: the camera returns to the opening scene; the same action now carries a completely different meaning."
            ),
        }
        return ensure_dialogue_assets(
            script,
            duration_seconds=duration_seconds,
            shot_count=planned_shot_count,
        )

    def supervise_storyboard(
        self,
        idea: str,
        brief: dict[str, Any],
        script: dict[str, Any],
        storyboard: list[Any],
        *,
        duration_seconds: int,
    ) -> dict[str, Any]:
        """Create the second-pass, shot-aware dialogue and narration assets.

        The first writing pass establishes the screenplay and broad story arc.
        This pass runs only after the storyboard is locked, so every line can
        refer to an actual visual event instead of repeating a generic theme.
        ``dialogue_book`` remains the canonical editable source and the
        subtitle track is derived from it by the shared subtitle service.
        """

        shot_count = len(storyboard)
        if self.llm:
            shot_context = "\n".join(
                self._shot_context(shot, index)
                for index, shot in enumerate(storyboard, start=1)
            )
            result = self.llm.complete_json(
                "You are a script supervisor finishing an English sci-fi short after the storyboard is locked. "
                "Write concise, speakable narration or dialogue only where speech adds information, inner conflict, irony, thematic contrast, foreshadowing, dialogue, or system-world information. "
                "Do not narrate what the image already shows. Silent and ambience-only shots must have no cue. All output must be English. "
                "Return 0..N cues, not one cue per shot; preserve causal and emotional continuity.",
                f"Idea: {idea}\nDirector brief: {brief}\nExisting screenplay: {script.get('story', '')}\n"
                f"Existing outline: {script.get('outline', '')}\nLOCKED STORYBOARD:\n{shot_context}\n"
                "Return JSON with narration (one coherent English paragraph), dialogue_book and subtitle_track arrays. "
                "Each cue must contain shot, speaker, kind, text, start_seconds, end_seconds; arrays may be empty and a shot may have no cue. "
                "Use speaker=NARRATOR and kind=narration when appropriate. Keep each line natural for voice performance.",
            )
            result_script = {
                **script,
                "narration": _as_text(result.get("narration") or script.get("narration", "")),
                "dialogue_book": result.get("dialogue_book"),
                "subtitle_track": result.get("subtitle_track"),
                "narrative_source": "storyboard_supervisor",
            }
            return align_script_to_shots(result_script, storyboard, allow_silent=True)

        # Mock mode still needs to demonstrate the same contract.  Build lines
        # from the actual narrative purpose/action/reaction fields rather than
        # reusing the first-pass theme sentence for every shot.
        dialogue: list[dict[str, Any]] = []
        narration_lines: list[str] = []
        for index, shot in enumerate(storyboard, start=1):
            speech_policy = self._shot_value(shot, "speech_policy").upper() or "NARRATION"
            purpose = self._shot_value(shot, "narrative_purpose") or f"the next beat unfolds"
            action = self._shot_value(shot, "main_action") or self._shot_value(shot, "action")
            reaction = self._shot_value(shot, "character_reaction")
            line_parts = [self._as_sentence(purpose), self._as_sentence(action)]
            if reaction:
                line_parts.append(self._as_sentence(reaction))
            line = " ".join(part for part in line_parts if part)
            if speech_policy not in {"SILENT", "AMBIENCE_ONLY"}:
                narration_lines.append(line)
                dialogue.append(
                    {
                        "shot": index,
                        "speaker": "SYSTEM" if speech_policy == "SYSTEM_VOICE" else "NARRATOR",
                        "kind": speech_policy.lower(),
                        "text": line or "The moment holds.",
                    }
                )
        result_script = {
            **script,
            "narration": " ".join(line for line in narration_lines if line),
            "dialogue_book": dialogue,
            "subtitle_track": dialogue,
            "speech_policy_by_shot": {
                str(index): self._shot_value(shot, "speech_policy").upper() or "NARRATION"
                for index, shot in enumerate(storyboard, start=1)
            },
            "narrative_source": "storyboard_supervisor",
        }
        return align_script_to_shots(result_script, storyboard, allow_silent=True)

    @staticmethod
    def _shot_value(shot: Any, key: str) -> str:
        if isinstance(shot, dict):
            return str(shot.get(key) or "").strip()
        return str(getattr(shot, key, "") or "").strip()

    @classmethod
    def _as_sentence(cls, value: str) -> str:
        text = " ".join(str(value or "").split()).strip()
        if not text:
            return ""
        return text if text[-1] in ".!?" else f"{text}."

    @classmethod
    def _shot_context(cls, shot: Any, index: int) -> str:
        return (
            f"Shot {index}: purpose={cls._shot_value(shot, 'narrative_purpose')}; "
            f"speech_policy={cls._shot_value(shot, 'speech_policy')}; "
            f"starting_state={cls._shot_value(shot, 'starting_state')}; "
            f"main_action={cls._shot_value(shot, 'main_action') or cls._shot_value(shot, 'action')}; "
            f"character_reaction={cls._shot_value(shot, 'character_reaction')}; "
            f"ending_state={cls._shot_value(shot, 'ending_state')}; "
            f"transition_hook={cls._shot_value(shot, 'transition_hook')}; "
            f"visual={cls._shot_value(shot, 'image_description')}"
        )

    def generate_story_beats(
        self,
        idea: str,
        brief: dict,
        script: dict,
        duration_seconds: int,
        story_world: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Break the screenplay into dramatic state changes, not shot slots."""

        beat_count = beat_count_for_duration(duration_seconds)
        if self.llm:
            result = self.llm.complete_json(
                "You are a story structure analyst. Break a short film screenplay into narrative beats "
                "that maintain causal continuity. Each beat must have a clear narrative purpose, "
                "emotional arc, and transition hook. All output in English.",
                f"Idea: {idea}\nDirector brief: {brief}\n"
                f"Screenplay: {script.get('story', '')}\n"
                f"Outline: {script.get('outline', '')}\n"
                f"{story_world_prompt(story_world)}\n"
                f"Break this into {beat_count} narrative beats. A beat is one dramatic state change, not one shot; multiple shots may express one beat. "
                "Return JSON: {\"beats\": [{beat_id, beat_number, scene_id, character_ids, story_function, "
                "prop_ids, narrative_purpose, information_gain, emotional_shift, visual_motif, starting_state, "
                "ending_state, transition_hook, importance, duration_weight}]}. "
                "narrative_purpose: why this beat exists (e.g. 'establish the ordinary world'). "
                "emotional_arc: how the audience feels (e.g. 'calm → unease'). "
                "starting_state: what the viewer sees at the start of this beat. "
                "ending_state: what the viewer sees at the end. "
                "transition_hook: how this beat connects to the next. scene_id, character_ids, and prop_ids must come only from the supplied Story World, "
                "importance and duration_weight are numeric values reflecting narrative weight. Do not omit fields.",
            )
            raw_beats = result.get("beats")
            if isinstance(raw_beats, list) and 4 <= len(raw_beats) <= 12:
                beats: list[dict[str, Any]] = []
                for index, raw in enumerate(raw_beats):
                    if not isinstance(raw, dict):
                        continue
                    beats.append({
                        "beat_id": str(raw.get("beat_id") or f"beat-{index + 1:02d}"),
                        "beat_number": int(raw.get("beat_number", index + 1)),
                        "scene_id": str(raw.get("scene_id", "")),
                        "character_ids": raw.get("character_ids") or [],
                        "prop_ids": raw.get("prop_ids") or [],
                        "story_function": str(raw.get("story_function") or raw.get("narrative_purpose", "")),
                        "narrative_purpose": str(raw.get("narrative_purpose", "")),
                        "information_gain": raw.get("information_gain", 0.5),
                        "emotional_shift": str(raw.get("emotional_shift") or raw.get("emotional_arc", "")),
                        "visual_motif": str(raw.get("visual_motif", "")),
                        "emotional_arc": str(raw.get("emotional_arc", "")),
                        "starting_state": str(raw.get("starting_state", "")),
                        "ending_state": str(raw.get("ending_state", "")),
                        "transition_hook": str(raw.get("transition_hook", "")),
                        "importance": raw.get("importance", 0.5),
                        "duration_weight": raw.get("duration_weight", 1.0),
                    })
                if beats:
                    beats = normalise_story_beats(beats)
                    if story_world:
                        unknown = validate_story_world_references(beats, story_world)
                        if any(unknown.values()):
                            raise ValueError(f"STORY_WORLD_REVIEW_REQUIRED: {unknown}")
                    return beats
        phases = [
            ("establish the ordinary world", "calm → curiosity", "The automated space hums with routine order.", "A faint irregularity appears at the edge of perception.", "The camera lingers on a detail that doesn't quite fit."),
            ("introduce the anomaly", "curiosity → unease", "The protagonist notices something off but dismisses it.", "The anomaly persists and grows slightly.", "A beat of hesitation before the next action."),
            ("escalate tension", "unease → suspicion", "The protagonist investigates cautiously.", "Evidence accumulates that this is no glitch.", "The protagonist pauses, weighing whether to act."),
            ("confront the truth", "suspicion → dread", "The protagonist faces what the anomaly really means.", "Old assumptions crumble.", "A moment of stillness before the choice."),
            ("the irreversible choice", "dread → resolve", "The protagonist commits to breaking convention.", "The space reacts to the choice.", "Consequences ripple outward."),
            ("consequences unfold", "resolve → acceptance", "The world reshapes around the decision.", "The protagonist observes the new state.", "The camera begins to pull back."),
            ("echo the opening", "acceptance → resonance", "The same space, the same routine gesture.", "Everything looks identical but means something different.", "Hold on the protagonist's face; cut to black."),
            ("lingering resonance", "resonance → silence", "The aftermath settles.", "The audience is left with a question, not an answer.", "Silence over the final frame."),
        ]
        beats = []
        for index in range(min(beat_count, len(phases))):
            purpose, arc, start, end, hook = phases[index]
            beats.append({
                "beat_id": f"beat-{index + 1:02d}",
                "beat_number": index + 1,
                "scene_id": "primary",
                "character_ids": ["protagonist"],
                "prop_ids": [],
                "story_function": purpose,
                "narrative_purpose": purpose,
                "information_gain": 0.5 if index < 2 else 0.8,
                "emotional_shift": arc,
                "visual_motif": "",
                "emotional_arc": arc,
                "starting_state": start,
                "ending_state": end,
                "transition_hook": hook,
                "importance": 0.5 if index < 2 else 0.8,
                "duration_weight": 1.0 if index < 2 else 1.25,
            })
        while len(beats) < beat_count:
            beats.append({
                "beat_id": f"beat-{len(beats) + 1:02d}",
                "beat_number": len(beats) + 1,
                "scene_id": "primary",
                "character_ids": ["protagonist"],
                "prop_ids": [],
                "story_function": "AFTERMATH",
                "narrative_purpose": "sustain emotional resonance",
                "information_gain": 0.35,
                "emotional_shift": "resonance → silence",
                "visual_motif": "",
                "emotional_arc": "resonance → silence",
                "starting_state": "The aftermath continues to settle.",
                "ending_state": "The final image holds.",
                "transition_hook": "Cut to black.",
                "importance": 0.6,
                "duration_weight": 1.0,
            })
        beats = normalise_story_beats(beats)
        if story_world:
            unknown = validate_story_world_references(beats, story_world)
            if any(unknown.values()):
                raise ValueError(f"STORY_WORLD_REVIEW_REQUIRED: {unknown}")
        return beats
