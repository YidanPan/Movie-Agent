"""Rendering-stage seams shared by ComfyUI and mock workers."""

from __future__ import annotations

from typing import Any

from movie_agent.services.continuity import ensure_continuity_lock
from movie_agent.services.shot_context import resolve_shot_context
from movie_agent.services.state_ledger import build_state_ledger, state_record_for_shot


class RenderPipeline:
    """Own one real shot render + visual QC transaction."""

    def __init__(self, generation_agent: Any, reviewer: Any) -> None:
        self.generation_agent = generation_agent
        self.reviewer = reviewer

    def render_shot(self, project: Any, shot: Any, *, previous_shot: Any = None) -> str:
        build_state_ledger(project)
        record = state_record_for_shot(project, int(getattr(shot, "number", 0) or 0))
        context = resolve_shot_context(
            shot,
            project.visual_bible,
            getattr(project, "story_world", {}) or {},
            previous_shot,
            entity_state_before=record.get("before"),
            entity_state_delta=record.get("delta"),
            entity_state_after=record.get("after"),
        )
        message = self.generation_agent.generate(
            project.project_id,
            shot,
            visual_bible=project.visual_bible,
            previous_shot=previous_shot,
            target_resolution=project.target_resolution,
            film_language=project.film_language,
            story_world=getattr(project, "story_world", {}) or {},
            context=context,
        )
        review = self.reviewer.review_generated(
            shot,
            project_id=project.project_id,
            visual_bible=project.visual_bible,
            previous_shot=previous_shot,
            story_world=getattr(project, "story_world", {}) or {},
            context=context,
        )
        return f"{message}\n{review}"


def shot_render_context(project: Any, shot_number: int) -> dict[str, Any]:
    """Build the renderer context for one shot without doing any I/O."""

    shots = list(getattr(project, "storyboard", []) or [])
    if not 1 <= int(shot_number) <= len(shots):
        raise ValueError(f"Shot number must be between 1 and {len(shots)}.")
    index = int(shot_number) - 1
    ensure_continuity_lock(project)
    build_state_ledger(project)
    state_record = state_record_for_shot(project, int(shot_number))
    return {
        "project_id": str(getattr(project, "project_id", "")),
        "shot": shots[index],
        "previous_shot": shots[index - 1] if index else None,
        "visual_bible": getattr(project, "visual_bible", {}) or {},
        "continuity_lock": getattr(project, "continuity_lock", {}) or {},
        "target_resolution": str(getattr(project, "target_resolution", "1080p") or "1080p"),
        "film_language": str(getattr(project, "film_language", "en") or "en"),
        "state_record": state_record,
    }

