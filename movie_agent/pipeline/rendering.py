"""Rendering-stage seams shared by ComfyUI and mock workers."""

from __future__ import annotations

from typing import Any

from movie_agent.services.continuity import ensure_continuity_lock


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

