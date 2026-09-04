"""Deterministic planning generator used before model integration."""

from __future__ import annotations

from math import ceil
from typing import Any

from movie_agent.models import Shot


def _english_style(style: str) -> str:
    """Keep generation prompts English even when the UI preset is Chinese."""

    aliases = {
        "写实近未来": "grounded near-future realism",
        "胶片科幻": "analog film science fiction",
        "极简冷色": "minimal cool-toned cinema",
        "梦境超现实": "dreamlike surreal cinema",
        "冷灰未来": "cool gray future",
        "赛博夜色": "restrained cyber night",
    }
    return aliases.get(str(style).strip(), str(style).strip() or "cinematic realism")


def build_storyboard(
    idea: str,
    duration: int,
    style: str,
    project_id: str,
    story_beats: list[dict[str, Any]] | None = None,
) -> list[Shot]:
    shot_count = max(6, ceil(duration / 8))
    shot_count = min(10, shot_count)
    base_duration, remainder = divmod(duration, shot_count)
    framings = ["wide shot", "medium close-up", "close-up", "over-the-shoulder", "low-angle medium", "insert shot"]
    shots: list[Shot] = []
    english_style = _english_style(style)
    for index in range(shot_count):
        shot_duration = base_duration + (1 if index < remainder else 0)
        beat = _beat_for_index(story_beats, index, shot_count)
        narrative_purpose = beat.get("narrative_purpose", "") if beat else ""
        starting_state = beat.get("starting_state", "") if beat else ""
        ending_state = beat.get("ending_state", "") if beat else ""
        transition_hook = beat.get("transition_hook", "") if beat else ""
        emotional_arc = beat.get("emotional_arc", "") if beat else ""
        phase = (
            "establish the quiet routine" if index < 2
            else "let the anomaly gradually emerge" if index < shot_count - 2
            else "complete the emotional turn and lingering resonance"
        )
        image = f"{english_style} film cinematography, same protagonist and same core space, {phase}."
        action = f"The protagonist carries the previous beat forward, completing a restrained action in narrative beat {index + 1}."
        sound = "Low-frequency ambience, spatial reverb, and restrained musical progression; no copyrighted material."
        delta = f"Delta from previous shot: {ending_state}" if index > 0 and ending_state else "Opening shot establishing the world."
        prompt = (
            f"{image} {action} [{0}s-{shot_duration}s] {delta} Camera movement is natural and steady. {sound} "
            "No existing film/TV characters, titles, brand logos, real likenesses, or copyrighted designs."
        )
        main_action = f"Narrative beat {index + 1}: {narrative_purpose or phase}. {emotional_arc}"
        character_reaction = f"The protagonist responds to the evolving situation with {emotional_arc.split(' → ')[-1] if ' → ' in emotional_arc else 'measured composure'}." if emotional_arc else ""
        shots.append(
            Shot(
                number=index + 1,
                duration_seconds=shot_duration,
                framing=framings[index % len(framings)],
                image_description=image,
                action=action,
                sound_design=sound,
                generation_mode="T2V",
                prompt=prompt,
                output_placeholder=f"outputs/{project_id}/shot-{index + 1:02d}.mp4",
                narrative_purpose=narrative_purpose or f"narrative beat {index + 1}",
                starting_state=starting_state or f"Shot {index} conclusion.",
                main_action=main_action,
                character_reaction=character_reaction,
                ending_state=ending_state or f"Shot {index + 1} resolves into the next beat.",
                transition_hook=transition_hook or "Cut to next shot.",
            )
        )
    return shots


def _beat_for_index(
    story_beats: list[dict[str, Any]] | None,
    shot_index: int,
    total_shots: int,
) -> dict[str, Any] | None:
    if not story_beats:
        return None
    if len(story_beats) >= total_shots:
        return story_beats[min(shot_index, len(story_beats) - 1)]
    ratio = shot_index / max(1, total_shots - 1)
    beat_index = min(int(ratio * (len(story_beats) - 1)), len(story_beats) - 1)
    return story_beats[beat_index]
