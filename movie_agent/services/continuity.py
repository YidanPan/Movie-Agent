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


def should_use_previous_frame(current_shot: Any, previous_shot: Any | None = None) -> bool:
    """Choose visual conditioning from editorial transition semantics."""

    transition = str(getattr(current_shot, "transition_type", "CONTINUOUS") or "CONTINUOUS").upper()
    if transition in {"HARD_CUT", "AUDIO_BRIDGE", "ELLIPSIS"}:
        return False
    if transition in {"CONTINUOUS", "ACTION_MATCH", "MATCH_CUT"}:
        if transition == "CONTINUOUS" and previous_shot is not None:
            previous_scene = str(getattr(previous_shot, "scene_id", "") or "")
            current_scene = str(getattr(current_shot, "scene_id", "") or "")
            return not previous_scene or not current_scene or previous_scene == current_scene
        return True
    if transition in {"FADE", "DISSOLVE"}:
        if previous_shot is None:
            return True
        previous_scene = str(getattr(previous_shot, "scene_id", "") or "")
        current_scene = str(getattr(current_shot, "scene_id", "") or "")
        return not previous_scene or not current_scene or previous_scene == current_scene
    return False


def _lock_text(value: Any) -> str:
    if isinstance(value, dict):
        preferred = ("appearance_lock", "face_lock", "hair_lock", "costume_lock", "silhouette_lock", "prop_lock", "environment_lock", "architecture_lock", "lighting_lock", "palette_lock")
        parts = [str(value[key]).strip() for key in preferred if value.get(key)]
        return " ".join(parts) or str(value.get("lock") or value)
    return str(value or "").strip()


def resolve_character_locks(visual_bible: dict[str, Any] | None, character_ids: list[str] | None) -> list[dict[str, Any]]:
    """Resolve only the characters present in the current shot."""

    bible = visual_bible or {}
    requested = {str(item) for item in (character_ids or []) if str(item).strip()}
    structured = bible.get("characters")
    if isinstance(structured, list):
        matches = [
            item for item in structured
            if isinstance(item, dict) and (not requested or str(item.get("character_id") or "") in requested)
        ]
        if matches:
            return [
                {"character_id": str(item.get("character_id") or ""), "name": str(item.get("name") or ""), "lock": _lock_text(item)}
                for item in matches
            ]
    fallback = _lock_text(bible.get("character_lock") or bible.get("character_card"))
    return [{"character_id": ",".join(sorted(requested)) or "global", "name": "", "lock": fallback}] if fallback else []


def resolve_scene_lock(visual_bible: dict[str, Any] | None, scene_id: str | None) -> dict[str, str]:
    """Resolve the current scene without leaking an unrelated scene lock."""

    bible = visual_bible or {}
    requested = str(scene_id or "").strip()
    structured = bible.get("scenes")
    if isinstance(structured, list) and requested:
        for item in structured:
            if isinstance(item, dict) and str(item.get("scene_id") or "") == requested:
                return {"scene_id": requested, "lock": _lock_text(item)}
    fallback = _lock_text(bible.get("scene_lock") or bible.get("scene_card"))
    return {"scene_id": requested or "global", "lock": fallback}


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
