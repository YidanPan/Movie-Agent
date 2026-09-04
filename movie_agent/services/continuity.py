"""Whole-film continuity contracts shared by planning and rendering agents."""

from __future__ import annotations

from typing import Any


LOCK_KEYS = (
    "character_lock",
    "scene_lock",
    "cinematography_lock",
    "reference_seed",
)


def build_continuity_lock(visual_bible: dict[str, Any] | None, film_language: str = "en") -> dict[str, Any]:
    """Create the small, serialisable contract every shot renderer consumes."""

    bible = visual_bible or {}
    return {
        "film_language": str(film_language or "en").lower(),
        "prompt_strategy": "VISUAL BIBLE → LOCKS → SHOT DELTA",
        "reference_seed": str(bible.get("reference_seed") or "42"),
        "locks": {key: str(bible.get(key) or "") for key in LOCK_KEYS},
        "shared_across_shots": [
            "character",
            "costume",
            "scene",
            "palette",
            "lighting",
            "camera_language",
        ],
        "shot_instruction": "Describe only the change from the previous shot; never reset the world.",
        "qc_flags": ["STYLE_DRIFT", "CHARACTER_DRIFT", "SCENE_DRIFT"],
        "status": "LOCKED",
    }


def ensure_continuity_lock(project: Any) -> dict[str, Any]:
    """Backfill old project JSON and return the current continuity contract."""

    current = getattr(project, "continuity_lock", None) or {}
    if not current or current.get("status") != "LOCKED":
        current = build_continuity_lock(
            getattr(project, "visual_bible", {}) or {},
            getattr(project, "film_language", "en"),
        )
        project.continuity_lock = current
    return current
