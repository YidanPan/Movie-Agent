"""Writer agent: creates a screenplay plus the canonical dialogue/subtitle assets."""

from typing import Any

from movie_agent.services.llm import CreativeLLM
from movie_agent.services.subtitles import ensure_dialogue_assets, shot_count_for_duration


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

    def generate_story_beats(
        self,
        idea: str,
        brief: dict,
        script: dict,
        duration_seconds: int,
    ) -> list[dict[str, Any]]:
        """Break the screenplay into 6-10 narrative beats for storyboard continuity."""

        shot_count = shot_count_for_duration(duration_seconds)
        if self.llm:
            result = self.llm.complete_json(
                "You are a story structure analyst. Break a short film screenplay into narrative beats "
                "that maintain causal continuity. Each beat must have a clear narrative purpose, "
                "emotional arc, and transition hook. All output in English.",
                f"Idea: {idea}\nDirector brief: {brief}\n"
                f"Screenplay: {script.get('story', '')}\n"
                f"Outline: {script.get('outline', '')}\n"
                f"Break this into {shot_count} narrative beats. "
                "Return JSON: {\"beats\": [{beat_number, narrative_purpose, emotional_arc, "
                "starting_state, ending_state, transition_hook}]}. "
                "narrative_purpose: why this beat exists (e.g. 'establish the ordinary world'). "
                "emotional_arc: how the audience feels (e.g. 'calm → unease'). "
                "starting_state: what the viewer sees at the start of this beat. "
                "ending_state: what the viewer sees at the end. "
                "transition_hook: how this beat connects to the next.",
            )
            raw_beats = result.get("beats")
            if isinstance(raw_beats, list) and 4 <= len(raw_beats) <= 12:
                beats: list[dict[str, Any]] = []
                for index, raw in enumerate(raw_beats):
                    if not isinstance(raw, dict):
                        continue
                    beats.append({
                        "beat_number": int(raw.get("beat_number", index + 1)),
                        "narrative_purpose": str(raw.get("narrative_purpose", "")),
                        "emotional_arc": str(raw.get("emotional_arc", "")),
                        "starting_state": str(raw.get("starting_state", "")),
                        "ending_state": str(raw.get("ending_state", "")),
                        "transition_hook": str(raw.get("transition_hook", "")),
                    })
                if beats:
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
        for index in range(min(shot_count, len(phases))):
            purpose, arc, start, end, hook = phases[index]
            beats.append({
                "beat_number": index + 1,
                "narrative_purpose": purpose,
                "emotional_arc": arc,
                "starting_state": start,
                "ending_state": end,
                "transition_hook": hook,
            })
        while len(beats) < shot_count:
            beats.append({
                "beat_number": len(beats) + 1,
                "narrative_purpose": "sustain emotional resonance",
                "emotional_arc": "resonance → silence",
                "starting_state": "The aftermath continues to settle.",
                "ending_state": "The final image holds.",
                "transition_hook": "Cut to black.",
            })
        return beats
