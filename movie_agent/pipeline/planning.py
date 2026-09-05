"""Planning-stage read models.

These helpers intentionally return plain dictionaries.  They are safe to use
from an API, event callback, or future background worker without coupling the
planning agents to FastAPI.
"""

from __future__ import annotations

from typing import Any


def planning_snapshot(project: Any) -> dict[str, Any]:
    """Summarise the planning outputs without exposing mutable internals."""

    storyboard = list(getattr(project, "storyboard", []) or [])
    return {
        "project_id": str(getattr(project, "project_id", "")),
        "idea": str(getattr(project, "idea", "")),
        "film_language": str(getattr(project, "film_language", "en") or "en"),
        "story_beats": len(getattr(project, "story_beats", []) or []),
        "shots": len(storyboard),
        "shot_revisions": [int(getattr(shot, "revision", 1) or 1) for shot in storyboard],
        "dialogue_locked": bool((getattr(project, "script", {}) or {}).get("dialogue_locked")),
    }

