"""Storyboard agent: creates renderable, continuity-aware shots."""

from typing import Any

from movie_agent.models import Shot
from movie_agent.services.mock_creator import build_storyboard
from movie_agent.services.llm import CreativeLLM

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


def _previous_ending(shots: list[Shot], current_index: int) -> str:
    """Return the ending state of the previous shot for delta-prompt continuity."""

    if current_index <= 0 or not shots:
        return ""
    return shots[current_index - 1].ending_state or shots[current_index - 1].action


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
    ) -> list[Shot]:
        beats = story_beats or []
        if self.llm:
            beats_context = ""
            if beats:
                beats_lines = [
                    f"  Beat {b.get('beat_number', i+1)}: purpose={b.get('narrative_purpose','')}, "
                    f"arc={b.get('emotional_arc','')}, start={b.get('starting_state','')}, "
                    f"end={b.get('ending_state','')}, hook={b.get('transition_hook','')}"
                    for i, b in enumerate(beats)
                ]
                beats_context = "\nStory beats (maintain continuity across shots):\n" + "\n".join(beats_lines)
            result = self.llm.complete_json(
                "You are a film storyboard artist. Break the story into a continuous sequence of "
                "original sci-fi shots that form a coherent film, not independent clips. "
                "Each shot 4-8 seconds, 6-10 shots total, avoid complex multi-person interactions and existing film/TV IP. "
                f"Available generation modes: {', '.join(sorted(self.allowed_generation_modes))}. "
                "The sum of all shot duration_seconds must equal the total duration exactly. "
                "IMPORTANT: Each shot prompt must describe only the DELTA from the previous shot — "
                "what changes, not a full scene reset. Include narrative continuity fields.",
                (
                    f"Idea: {idea}\nTotal duration: {duration_seconds} seconds\nStyle: {visual_style}\n"
                    f"Director brief: {brief}\nScript: {script}\nVisual bible: {visual_bible}"
                    f"{beats_context}\n"
                    "Keep text concise to control generation time: image_description and action each no more than 40 words, "
                    "sound_design no more than 15 words, prompt is a video generation prompt describing only the DELTA "
                    "from the previous shot in no more than 60 words. "
                    "Use English framing terms (wide shot, medium close-up, close-up, over-the-shoulder, low-angle medium, insert shot). "
                    "Return JSON: {\"shots\":[{\"duration_seconds\":6,\"framing\":\"medium close-up\","
                    "\"image_description\":\"...\",\"action\":\"...\",\"sound_design\":\"...\","
                    "\"generation_mode\":\"T2V\",\"prompt\":\"...\","
                    "\"narrative_purpose\":\"...\",\"starting_state\":\"...\",\"main_action\":\"...\","
                    "\"character_reaction\":\"...\",\"ending_state\":\"...\",\"transition_hook\":\"...\"}]}."
                ),
            )
            raw_shots = result.get("shots")
            if not isinstance(raw_shots, list) or not 6 <= len(raw_shots) <= 10:
                raise ValueError("Storyboard agent did not return 6-10 shots.")
            for raw_shot in raw_shots:
                if not isinstance(raw_shot, dict):
                    raise ValueError("Storyboard agent returned an invalid shot.")
            raw_durations = [_parse_duration(raw_shot.get("duration_seconds")) for raw_shot in raw_shots]
            fitted_durations = _fit_durations(raw_durations, duration_seconds)
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
                beat = _beat_for_shot(beats, number - 1, len(raw_shots))
                shots.append(
                    Shot(
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
                        character_reaction=str(raw_shot.get("character_reaction", "")),
                        ending_state=str(raw_shot.get("ending_state") or beat.get("ending_state", "")),
                        transition_hook=str(raw_shot.get("transition_hook") or beat.get("transition_hook", "")),
                    )
                )
            return shots
        shots = build_storyboard(idea, duration_seconds, visual_style, project_id, story_beats=beats)
        if self.allowed_generation_modes == {"T2V"}:
            for shot in shots:
                shot.generation_mode = "T2V"
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
        )
