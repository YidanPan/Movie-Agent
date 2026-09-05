"""Rendering-stage seams shared by ComfyUI and mock workers."""

from __future__ import annotations

from typing import Any

from movie_agent.services.continuity import ensure_continuity_lock


class RenderPipeline:
    """Own one real shot render + visual QC transaction."""

    def __init__(self, generation_agent: Any, reviewer: Any) -> None:
        self.generation_agent = generation_agent
        self.reviewer = reviewer

    def render_shot(self, project: Any, shot: Any, *, previous_shot: Any = None) -> str:
        message = self.generation_agent.generate(
            project.project_id,
            shot,
            visual_bible=project.visual_bible,
            previous_shot=previous_shot,
            target_resolution=project.target_resolution,
            film_language=project.film_language,
        )
        review = self.reviewer.review_generated(
            shot,
            project_id=project.project_id,
            visual_bible=project.visual_bible,
        )
        return f"{message}\n{review}"


def shot_render_context(project: Any, shot_number: int) -> dict[str, Any]:
    """Build the renderer context for one shot without doing any I/O."""

    shots = list(getattr(project, "storyboard", []) or [])
    if not 1 <= int(shot_number) <= len(shots):
        raise ValueError(f"Shot number must be between 1 and {len(shots)}.")
    index = int(shot_number) - 1
    ensure_continuity_lock(project)
    return {
        "project_id": str(getattr(project, "project_id", "")),
        "shot": shots[index],
        "previous_shot": shots[index - 1] if index else None,
        "visual_bible": getattr(project, "visual_bible", {}) or {},
        "continuity_lock": getattr(project, "continuity_lock", {}) or {},
        "target_resolution": str(getattr(project, "target_resolution", "1080p") or "1080p"),
        "film_language": str(getattr(project, "film_language", "en") or "en"),
    }

