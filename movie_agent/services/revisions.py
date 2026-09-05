"""Revision metadata and dependency invalidation for production assets.

The project intentionally keeps JSON persistence and local media files.  This
module gives that small architecture the same safety property as a larger
pipeline: an upstream edit marks dependent outputs stale, but never destroys a
previous render.  New renders replace the current pointer only after they have
passed their stage's checks.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


DEPENDENCY_GRAPH: dict[str, tuple[str, ...]] = {
    "script": (
        "storyboard",
        "shot_media",
        "qc",
        "voice",
        "subtitles",
        "rough_cut",
        "final_cut",
        "final_look",
        "export",
    ),
    # Dialogue/Subtitle edits do not rewrite the visual storyboard.  They
    # invalidate the sound and editorial derivatives while preserving already
    # approved shot media.
    "dialogue": ("voice", "subtitles", "rough_cut", "final_cut", "final_look", "export"),
    "storyboard": (
        "shot_media",
        "qc",
        "voice",
        "subtitles",
        "rough_cut",
        "final_cut",
        "final_look",
        "export",
    ),
    "shot": (
        "shot_media",
        "qc",
        "rough_cut",
        "final_cut",
        "final_look",
        "export",
    ),
    "shot_timing": (
        "voice",
        "subtitles",
        "rough_cut",
        "final_cut",
        "final_look",
        "export",
    ),
    "voice": ("subtitles", "rough_cut", "final_cut", "final_look", "export"),
    "audio": ("rough_cut", "final_cut", "final_look", "export"),
    "rough_cut": ("final_cut", "final_look", "export"),
    "final_cut": ("final_look", "export"),
    "final_look": ("export",),
}


def utc_now() -> str:
    """Return a stable, JSON-friendly UTC timestamp."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def hash_shot_prompt(shot: Any) -> str:
    """Hash all renderer-facing shot inputs, not only the short Shot Delta."""

    payload = {
        "prompt": str(getattr(shot, "prompt", "") or ""),
        "image_description": str(getattr(shot, "image_description", "") or ""),
        "action": str(getattr(shot, "action", "") or ""),
        "framing": str(getattr(shot, "framing", "") or ""),
        "sound_design": str(getattr(shot, "sound_design", "") or ""),
        "generation_mode": str(getattr(shot, "generation_mode", "") or ""),
        "starting_state": str(getattr(shot, "starting_state", "") or ""),
        "main_action": str(getattr(shot, "main_action", "") or ""),
        "character_reaction": str(getattr(shot, "character_reaction", "") or ""),
        "ending_state": str(getattr(shot, "ending_state", "") or ""),
        "transition_hook": str(getattr(shot, "transition_hook", "") or ""),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def ensure_shot_metadata(
    shot: Any,
    *,
    provider: str = "mock",
    model: str = "mock",
    seed: int | None = None,
    created_at: str | None = None,
) -> Any:
    """Backfill metadata on old projects without changing their revision."""

    try:
        shot.revision = max(1, int(getattr(shot, "revision", 1) or 1))
    except (TypeError, ValueError):
        shot.revision = 1
    shot.prompt_hash = hash_shot_prompt(shot)
    if not getattr(shot, "provider", ""):
        shot.provider = str(provider or "mock")
    if not getattr(shot, "model", ""):
        shot.model = str(model or "mock")
    if seed is not None:
        shot.seed = int(seed)
        shot.generation_seed = int(seed)
    elif getattr(shot, "seed", None) is None and getattr(shot, "generation_seed", None) is not None:
        shot.seed = int(shot.generation_seed)
    if not getattr(shot, "created_at", ""):
        shot.created_at = created_at or utc_now()
    if not getattr(shot, "qc_status", ""):
        shot.qc_status = "PENDING"
    if not isinstance(getattr(shot, "asset_history", None), list):
        shot.asset_history = []
    if not isinstance(getattr(shot, "stale", False), bool):
        shot.stale = bool(shot.stale)
    return shot


def _stale_record(record: Any, *, reason: str, revision: int, now: str) -> dict[str, Any] | Any:
    if not isinstance(record, dict):
        return record
    stale = deepcopy(record)
    stale["stale"] = True
    stale["stale_at"] = now
    stale["stale_reason"] = reason
    stale["source_revision"] = int(record.get("revision", revision) or revision)
    return stale


def mark_shot_stale(shot: Any, reason: str, *, increment_revision: bool = True) -> Any:
    """Mark current shot media and QC stale while retaining rollback history."""

    ensure_shot_metadata(shot)
    if increment_revision:
        shot.revision = max(1, int(shot.revision or 1)) + 1
    now = utc_now()
    current_assets = getattr(shot, "media_assets", {}) or {}
    if isinstance(current_assets, dict):
        stale_assets = {
            key: _stale_record(value, reason=reason, revision=shot.revision, now=now)
            for key, value in current_assets.items()
        }
        # Keep the current records visible for diagnostics, and also append a
        # frozen snapshot so a future renderer can offer rollback/comparison.
        if stale_assets:
            history = getattr(shot, "asset_history", None)
            if not isinstance(history, list):
                history = []
                shot.asset_history = history
            history.append(
                {
                    "revision": max(1, int(shot.revision or 1) - 1),
                    "invalidated_at": now,
                    "invalidated_reason": reason,
                    "assets": deepcopy(stale_assets),
                }
            )
        shot.media_assets = stale_assets
    shot.stale = True
    shot.qc_status = "STALE"
    flags = [str(flag).upper() for flag in (getattr(shot, "qc_flags", None) or [])]
    if "STALE" not in flags:
        flags.append("STALE")
    shot.qc_flags = flags
    # A stale source must not be mistaken for an approved render on resume.
    if str(getattr(shot, "status", "")).startswith(("approved", "generated", "generating")):
        shot.status = "replanned"
    shot.prompt_hash = hash_shot_prompt(shot)
    return shot


def mark_current_assets_stale(project: Any, reason: str, *, source: str = "pipeline") -> list[dict[str, Any]]:
    """Mark project-level edit assets stale and return the snapshot."""

    now = utc_now()
    assets = getattr(project, "video_assets", {}) or {}
    if not isinstance(assets, dict):
        return []
    stale_assets: dict[str, Any] = {}
    snapshot: list[dict[str, Any]] = []
    for key, record in assets.items():
        stale = _stale_record(record, reason=reason, revision=1, now=now)
        stale_assets[key] = stale
        snapshot.append({"key": key, "asset": deepcopy(stale), "source": source})
    project.video_assets = stale_assets
    if snapshot:
        history = getattr(project, "video_asset_history", None)
        if not isinstance(history, list):
            history = []
            project.video_asset_history = history
        history.append({"invalidated_at": now, "reason": reason, "source": source, "assets": snapshot})
    return snapshot


def invalidate_downstream(
    project: Any,
    source: str,
    reason: str,
    *,
    shot: Any | None = None,
    mark_shot: bool = False,
) -> dict[str, Any]:
    """Propagate an upstream change through the persisted production graph.

    ``mark_shot`` is false for timeline-only edits: the original shot media is
    still valid, while every editorial derivative is stale.  Prompt and visual
    edits set it true so QC and media cannot be reused accidentally.
    """

    source_key = str(source or "pipeline").strip().lower()
    downstream = list(DEPENDENCY_GRAPH.get(source_key, ()))
    if mark_shot and shot is not None:
        mark_shot_stale(shot, reason)
    if "shot_media" in downstream and shot is None:
        for item in getattr(project, "storyboard", []) or []:
            mark_shot_stale(item, reason)
    snapshot = mark_current_assets_stale(project, reason, source=source_key)
    if getattr(project, "edit_plan", None):
        old_plan = deepcopy(project.edit_plan)
        old_plan["stale"] = True
        old_plan["stale_reason"] = reason
        old_plan["invalidated_at"] = utc_now()
        history = getattr(project, "edit_plan_history", None)
        if not isinstance(history, list):
            history = []
            project.edit_plan_history = history
        history.append(old_plan)
    project.edit_plan = {}
    # Audio records can contain generated voice/music files.  They are kept
    # for inspection but cannot silently be reused after source changes.
    if source_key in {"script", "shot_timing", "voice", "audio", "storyboard", "shot"}:
        for track in (getattr(project, "audio_tracks", {}) or {}).values():
            if isinstance(track, dict) and track.get("media_path"):
                track["stale"] = True
                track["stale_reason"] = reason
    # Final Look is a derivative of the previous final cut.  Resetting its
    # active pointer is safe; history remains in the invalidation event.
    look = getattr(project, "final_look", None)
    if isinstance(look, dict) and look:
        look["stale"] = True
        look["stale_reason"] = reason
    project.final_output_placeholder = None
    project.rough_cut_placeholder = None
    if not isinstance(getattr(project, "invalidation_events", None), list):
        project.invalidation_events = []
    event = {
        "source": source_key,
        "reason": reason,
        "created_at": utc_now(),
        "downstream": downstream,
        "shot_number": getattr(shot, "number", None),
        "stale_assets": [item.get("key") for item in snapshot],
    }
    project.invalidation_events.append(event)
    shots = getattr(project, "storyboard", []) or []
    shots_ready = bool(shots) and all(str(getattr(item, "status", "")).startswith("approved") and not getattr(item, "stale", False) for item in shots)
    if shots_ready:
        project.status = "ready_for_ai_edit"
    elif str(getattr(project, "status", "")) not in {"planning_live", "rendering_comfyui", "generating_video_mock"}:
        project.status = "ready_for_comfyui_render"
    return event


def ensure_project_revision_metadata(project: Any, *, provider: str = "mock", model: str = "mock") -> Any:
    """Backfill metadata for a project loaded from a pre-P2 JSON file."""

    shots = list(getattr(project, "storyboard", []) or [])
    for shot in shots:
        ensure_shot_metadata(shot, provider=provider, model=model)
        media_assets = getattr(shot, "media_assets", {}) or {}
        if isinstance(media_assets, dict):
            for record in media_assets.values():
                _ensure_asset_metadata(record, shot, provider=provider, model=model)
    project_assets = getattr(project, "video_assets", {}) or {}
    if isinstance(project_assets, dict):
        project_revision = max((int(getattr(shot, "revision", 1) or 1) for shot in shots), default=1)
        for record in project_assets.values():
            _ensure_asset_metadata(record, None, provider=provider, model=model, revision=project_revision)
    if not isinstance(getattr(project, "video_asset_history", None), list):
        project.video_asset_history = []
    if not isinstance(getattr(project, "edit_plan_history", None), list):
        project.edit_plan_history = []
    if not isinstance(getattr(project, "invalidation_events", None), list):
        project.invalidation_events = []
    try:
        project.schema_version = max(2, int(getattr(project, "schema_version", 2) or 2))
    except (TypeError, ValueError):
        project.schema_version = 2
    return project


def _ensure_asset_metadata(
    record: Any,
    shot: Any | None,
    *,
    provider: str,
    model: str,
    revision: int | None = None,
) -> Any:
    """Add the P2 audit fields to legacy asset records without probing media."""

    if not isinstance(record, dict):
        return record
    shot_revision = int(revision or getattr(shot, "revision", 1) or 1)
    record.setdefault("revision", max(1, shot_revision))
    record.setdefault("prompt_hash", str(getattr(shot, "prompt_hash", "") or ""))
    record.setdefault("provider", str(getattr(shot, "provider", "") or provider or ""))
    record.setdefault("model", str(getattr(shot, "model", "") or model or ""))
    seed = getattr(shot, "seed", None) if shot is not None else None
    if seed is None and shot is not None:
        seed = getattr(shot, "generation_seed", None)
    record.setdefault("seed", int(seed) if seed is not None else None)
    record.setdefault("created_at", str(getattr(shot, "created_at", "") or utc_now()))
    record.setdefault("qc_status", "PENDING")
    if "source_resolution" not in record:
        width, height = record.get("width"), record.get("height")
        record["source_resolution"] = f"{width}x{height}" if width and height else getattr(shot, "source_resolution", None)
    record.setdefault("source_fps", record.get("fps", getattr(shot, "source_fps", None)))
    record.setdefault("source_duration", record.get("duration_seconds", getattr(shot, "source_duration", None)))
    record.setdefault("stale", bool(getattr(shot, "stale", False)) if shot is not None else False)
    return record


def dependency_chain(source: str) -> tuple[str, ...]:
    """Public read-only view used by diagnostics and regression tests."""

    return tuple(DEPENDENCY_GRAPH.get(str(source or "").lower(), ()))
