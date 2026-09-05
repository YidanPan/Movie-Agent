"""Whole-film continuity contracts shared by planning and rendering agents.

The continuity module owns the small pieces of state that must remain stable
between planning and media generation.  In particular, the project reference
seed is persisted once and every shot receives a deterministic derivative.
That keeps a retry or a resumed Spark render from silently changing the visual
identity of an otherwise unchanged shot.
"""

from __future__ import annotations

import hashlib
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


def derive_shot_seed(project_id: str, reference_seed: str | int | None, shot_number: int) -> int:
    """Derive a stable ComfyUI seed for one shot in one project.

    A cryptographic digest is used instead of Python's process-randomised
    ``hash()`` so the value is reproducible across restarts, machines, and
    Python versions.  The result stays inside the positive signed 63-bit range
    accepted by the verified ComfyUI workflow.
    """

    material = f"{str(project_id).strip()}|{str(reference_seed or '42').strip()}|{int(shot_number)}".encode(
        "utf-8"
    )
    digest = hashlib.sha256(material).digest()
    seed = int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)
    return seed or 1
