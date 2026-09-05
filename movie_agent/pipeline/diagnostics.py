"""Truthful project diagnostics and delivery preflight contracts.

P4 keeps recovery decisions in one small, JSON-safe module.  The frontend can
ask what a saved project is doing, what failed, and which action is safe next
without inspecting filesystem paths or inferring state from decorative text.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from movie_agent.pipeline.editing import editing_snapshot
from movie_agent.services.errors import error_info
from movie_agent.services.media_quality import (
    best_master_path,
    best_screening_path,
    export_dimensions,
    probe_media,
    quality_snapshot,
)
from movie_agent.state import describe_status


_VALID_RESOLUTIONS = {"720p", "1080p"}
_VALID_ASPECTS = {"16:9", "9:16", "1:1"}
_VALID_SUBTITLE_MODES = {"none", "soft", "burned"}
_SENSITIVE_FRAGMENT = re.compile(
    r"(?i)(authorization|api[\s_-]?key|access[\s_-]?token|password|secret|token)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"
)


def _safe_int(value: Any, default: int = 0, *, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed) if minimum is not None else parsed


def _safe_text(value: Any, limit: int = 1_000) -> str:
    """Keep diagnostics useful while preventing accidental secret leakage."""

    text = str(value or "").strip()
    if not text:
        return ""
    text = _SENSITIVE_FRAGMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    return text[:limit]


def _within_project_root(path: Path | None, project: Any, outputs_dir: Path | None) -> bool:
    """Return whether a media path is a current project-scoped file."""

    if path is None or not path.is_file():
        return False
    if outputs_dir is None:
        return True
    try:
        path.resolve().relative_to((Path(outputs_dir) / str(getattr(project, "project_id", ""))).resolve())
    except ValueError:
        return False
    return True


def _error_snapshot(target: Any, *, fallback_stage: str) -> dict[str, Any] | None:
    """Expose only redacted, stable failure fields."""

    code = _safe_text(getattr(target, "error_code", ""), 120)
    message = _safe_text(getattr(target, "error_message", ""))
    raw = getattr(target, "last_error", {}) or {}
    if isinstance(raw, dict):
        code = code or _safe_text(raw.get("error_code"), 120)
        message = message or _safe_text(raw.get("error_message"))
        stage = _safe_text(raw.get("stage"), 80) or fallback_stage
        created_at = _safe_text(raw.get("created_at"), 80)
        recoverable = bool(raw.get("recoverable", getattr(target, "recoverable", True)))
    else:
        stage = fallback_stage
        created_at = _safe_text(getattr(target, "last_error_at", ""), 80)
        recoverable = bool(getattr(target, "recoverable", True))
    if not code and not message:
        return None
    # Re-run the same redaction/classification boundary used by P3 when a
    # legacy project contains an old free-form message.
    if message:
        safe = error_info(RuntimeError(message), stage=stage)
        message = safe["error_message"]
    retry_count = _safe_int(getattr(target, "retry_count", 0), minimum=0)
    return {
        "error_code": code or "PIPELINE_FAILED",
        "error_message": message or "The production step failed.",
        "stage": stage,
        "retry_count": retry_count,
        "recoverable": recoverable,
        "created_at": created_at or _safe_text(getattr(target, "last_error_at", ""), 80),
    }


def _shot_ready(shot: Any) -> bool:
    return str(getattr(shot, "status", "")).startswith("approved") and not bool(getattr(shot, "stale", False))


def _shot_diagnostics(shot: Any) -> dict[str, Any]:
    error = _error_snapshot(shot, fallback_stage="generation")
    flags = [str(flag).upper() for flag in (getattr(shot, "qc_flags", []) or [])]
    retry_count = _safe_int(getattr(shot, "retry_count", 0), minimum=0)
    return {
        "number": _safe_int(getattr(shot, "number", 0), minimum=0),
        "status": str(getattr(shot, "status", "planned") or "planned"),
        "qc_status": str(getattr(shot, "qc_status", "PENDING") or "PENDING"),
        "ready": _shot_ready(shot),
        "stale": bool(getattr(shot, "stale", False)),
        "qc_flags": flags,
        "retry_count": retry_count,
        "recoverable": bool(getattr(shot, "recoverable", True)),
        "error": error,
    }


def _media_tier(record: Any) -> dict[str, Any]:
    """Strip paths from a quality record while keeping useful diagnostics."""

    if not isinstance(record, dict):
        return {"available": False, "stale": False, "quality": "NOT AVAILABLE"}
    width = record.get("width")
    height = record.get("height")
    resolution = record.get("source_resolution")
    if not resolution and isinstance(width, int) and isinstance(height, int):
        resolution = f"{width}x{height}"
    revision = _safe_int(record.get("revision", 1), default=1, minimum=1)
    return {
        "available": bool(record.get("exists")) and not bool(record.get("stale")),
        "stale": bool(record.get("stale")),
        "quality": str(record.get("quality") or "QUALITY UNKNOWN"),
        "resolution": resolution,
        "native_resolution": record.get("native_resolution") or resolution,
        "conformed_resolution": record.get("conformed_resolution") or resolution,
        "upscale_method": str(record.get("upscale_method") or "none"),
        "enhanced": bool(record.get("enhanced", False)),
        "resolution_label": str(record.get("resolution_label") or record.get("quality") or "QUALITY UNKNOWN"),
        "fps": record.get("fps") if record.get("fps") is not None else record.get("source_fps"),
        "duration_seconds": record.get("duration_seconds") if record.get("duration_seconds") is not None else record.get("source_duration"),
        "has_audio": bool(record.get("has_audio")),
        "qc_status": str(record.get("qc_status") or "PENDING"),
        "revision": revision,
    }


def _next_actions(
    project: Any,
    *,
    status: str,
    has_master: bool,
    has_screening: bool,
    shots_ready: bool,
    dialogue_locked: bool,
    has_rough_cut: bool,
) -> list[str]:
    """Return ordered, UI-friendly actions for the current persisted state."""

    error = getattr(project, "last_error", {}) or {}
    error_stage = str(error.get("stage") or "").lower() if isinstance(error, dict) else ""
    if status in {"render_failed", "failed"}:
        if error_stage in {"generation", "quality", "render"} or not shots_ready:
            return ["RETRY_RENDER", "REVIEW_FAILED_SHOTS"]
        if error_stage in {"ai_edit", "edit", "final_cut"}:
            return ["RETRY_AI_EDIT", "REVIEW_ROUGH_CUT"]
        return ["RETRY_LAST_STEP", "OPEN_PROJECT_LOG"]
    if status == "planning_live":
        return ["WAIT_FOR_PLAN"]
    if status in {"planned_mock", "planned_text_ai"}:
        return ["REVIEW_PREVIS", "START_RENDER"]
    if status == "ready_for_comfyui_render":
        return ["START_RENDER"]
    if status in {"generating_video_mock", "rendering_comfyui"}:
        return ["RESUME_RENDER"]
    if status == "ready_for_ai_edit":
        return ["START_AI_EDIT"] if dialogue_locked else ["LOCK_DIALOGUE"]
    if status == "editing_rough_cut":
        return ["WAIT_FOR_ROUGH_CUT"]
    if status == "rough_cut_ready":
        return ["APPROVE_FINAL_CUT", "REVIEW_SOUND_DESIGN"]
    if status == "editing_final":
        return ["WAIT_FOR_FINAL_CUT"]
    if status.startswith("completed"):
        if has_master:
            return ["APPLY_FINAL_LOOK", "EXPORT_FINAL_FILM"]
        return ["VERIFY_FINAL_MASTER", "OPEN_PROJECT_LOG"]
    if status == "exported":
        return ["VIEW_DELIVERY"]
    if status == "archived":
        return ["VIEW_ARCHIVE"]
    if has_rough_cut and not has_master:
        return ["APPROVE_FINAL_CUT"]
    if has_screening and shots_ready:
        return ["START_AI_EDIT"] if dialogue_locked else ["LOCK_DIALOGUE"]
    return ["OPEN_PROJECT_LOG"]


def diagnostics_snapshot(
    project: Any,
    *,
    ffprobe_bin: str = "ffprobe",
    outputs_dir: Path | None = None,
) -> dict[str, Any]:
    """Build a safe, resumability-oriented snapshot for one project.

    It intentionally contains no filesystem paths, prompts, API keys, or raw
    media manifests.  It is suitable for both the browser and an operations
    health panel.
    """

    status = str(getattr(project, "status", "planning_live") or "planning_live")
    state = describe_status(status)
    shots = list(getattr(project, "storyboard", []) or [])
    shot_items = [_shot_diagnostics(shot) for shot in shots]
    ready_count = sum(1 for item in shot_items if item["ready"])
    failed_items = [item for item in shot_items if item["error"] or item["status"] in {"generation_failed", "qc_failed_continuity"}]
    stale_items = [item for item in shot_items if item["stale"]]
    pending_count = max(0, len(shot_items) - ready_count - len(failed_items))

    quality = quality_snapshot(project, ffprobe_bin)
    assets = {
        "working_proxy": _media_tier(quality.get("working_proxy")),
        "screening_preview": _media_tier(quality.get("screening_preview")),
        "final_master": _media_tier(quality.get("final_master")),
    }
    master_path = best_master_path(project)
    screening_path = best_screening_path(project)
    has_master = _within_project_root(master_path, project, outputs_dir)
    has_screening = _within_project_root(screening_path, project, outputs_dir)
    if not assets["final_master"]["available"] and has_master:
        assets["final_master"]["available"] = True
    if not assets["screening_preview"]["available"] and has_screening:
        assets["screening_preview"]["available"] = True

    dialogue = getattr(project, "script", {}) or {}
    dialogue_locked = bool(dialogue.get("dialogue_locked")) if isinstance(dialogue, dict) else False
    editing = editing_snapshot(project)
    project_error = _error_snapshot(project, fallback_stage="pipeline")
    next_actions = _next_actions(
        project,
        status=status,
        has_master=has_master,
        has_screening=has_screening,
        shots_ready=bool(shots) and ready_count == len(shots),
        dialogue_locked=dialogue_locked,
        has_rough_cut=bool(editing.get("has_output")) and status in {"editing_rough_cut", "rough_cut_ready"},
    )
    progress = round((ready_count / len(shots)) * 100) if shots else 0
    return {
        "project_id": str(getattr(project, "project_id", "")),
        "status": status,
        "state": state["state"],
        "stage": state["stage"],
        "updated_at": str(getattr(project, "updated_at", "") or ""),
        "pipeline_state": state,
        "progress": {
            "shots_total": len(shots),
            "shots_ready": ready_count,
            "shots_failed": len(failed_items),
            "shots_stale": len(stale_items),
            "shots_pending": pending_count,
            "percent": progress,
        },
        "dialogue": {
            "locked": dialogue_locked,
            "revision": _safe_int(dialogue.get("dialogue_revision", 1), default=1, minimum=1) if isinstance(dialogue, dict) else 1,
            "subtitle_cues": len(dialogue.get("subtitle_track") or []) if isinstance(dialogue, dict) else 0,
        },
        "shots": shot_items,
        "errors": {
            "project": project_error,
            "shots": [item for item in failed_items if item["error"]],
        },
        "recoverability": {
            "can_resume": status not in {"archived", "exported"} and bool(next_actions),
            "next_action": next_actions[0] if next_actions else None,
            "actions": next_actions,
            "retryable_failures": sum(1 for item in failed_items if item["recoverable"]),
        },
        "media": {
            "target_resolution": str(getattr(project, "target_resolution", "1080p") or "1080p"),
            "target_fps": _safe_int(getattr(project, "target_fps", 24), default=24, minimum=1),
            "source_low_res": bool(quality.get("source_low_res")),
            "upscale_available": bool(quality.get("upscale_available")),
            "tiers": assets,
        },
        "editing": editing,
        "activity": {
            "count": len(getattr(project, "logs", []) or []),
            "recent": [_safe_text(item, 500) for item in (getattr(project, "logs", []) or [])[-12:] if _safe_text(item, 500)],
        },
    }


def _check(ok: bool, message: str, *, required: bool = True, warning: bool = False) -> dict[str, Any]:
    return {"ok": bool(ok), "required": bool(required), "warning": bool(warning), "message": str(message)}


def delivery_preflight(
    project: Any,
    *,
    resolution: str = "1080p",
    aspect: str = "16:9",
    subtitle_mode: str = "burned",
    ffmpeg_ready: bool = True,
    ffprobe_bin: str = "ffprobe",
    outputs_dir: Path | None = None,
) -> dict[str, Any]:
    """Check whether the requested delivery can be encoded safely.

    Warnings such as a low-resolution source remain visible, but only checks
    marked ``required`` can block export.  This mirrors EditorAgent's strict
    Final Master contract while giving the UI a preflight explanation first.
    """

    resolution = str(resolution or "1080p").lower().strip()
    aspect = str(aspect or "16:9").strip()
    subtitle_mode = str(subtitle_mode or "burned").lower().strip()
    valid_request = resolution in _VALID_RESOLUTIONS and aspect in _VALID_ASPECTS and subtitle_mode in _VALID_SUBTITLE_MODES
    expected_width, expected_height = export_dimensions(resolution, aspect)
    project_status = str(getattr(project, "status", "") or "")
    shots = list(getattr(project, "storyboard", []) or [])
    shots_ready = bool(shots) and all(_shot_ready(shot) for shot in shots)
    dialogue = getattr(project, "script", {}) or {}
    dialogue_locked = bool(dialogue.get("dialogue_locked")) if isinstance(dialogue, dict) else False
    master_path = best_master_path(project)
    master_scoped = _within_project_root(master_path, project, outputs_dir)
    metadata = probe_media(master_path, ffprobe_bin) if master_scoped and master_path else {}
    has_dimensions = isinstance(metadata.get("width"), int) and isinstance(metadata.get("height"), int)
    resolution_ok = not has_dimensions or (metadata["width"] >= expected_width and metadata["height"] >= expected_height)
    quality = quality_snapshot(project, ffprobe_bin)
    quality_warning = bool(quality.get("source_low_res")) or bool(metadata.get("quality") == "LOW RES SOURCE") or (
        has_dimensions and (metadata["width"] < expected_width or metadata["height"] < expected_height)
    )

    checks = {
        "request": _check(valid_request, "Delivery format is supported." if valid_request else "Choose a supported resolution, aspect ratio, and subtitle mode."),
        "final_cut": _check(project_status.startswith("completed"), "Final Cut is approved." if project_status.startswith("completed") else "Approve the Final Cut before exporting."),
        "final_master": _check(master_scoped, "Current Final Master is available." if master_scoped else "Current Final Master is missing or stale; a proxy cannot be exported."),
        "dialogue_lock": _check(dialogue_locked, "Locked Dialogue Book is attached." if dialogue_locked else "Lock the Dialogue Book before delivery."),
        "shots": _check(shots_ready, "All shot revisions passed QC." if shots_ready else "Every current shot must pass QC before delivery."),
        "resolution": _check(resolution_ok, "Master meets the requested resolution." if resolution_ok else f"Master is below {resolution.upper()} {aspect}; run Resolution Normalize or AI Upscale."),
        "ffmpeg": _check(ffmpeg_ready, "FFmpeg is available." if ffmpeg_ready else "FFmpeg is not available in the current runtime."),
        "quality": _check(not quality_warning, "Source quality is suitable for this delivery." if not quality_warning else "LOW RES SOURCE: export may not meet the requested quality.", required=False, warning=quality_warning),
    }
    blocking = [key for key, item in checks.items() if item["required"] and not item["ok"]]
    warnings = [key for key, item in checks.items() if item["warning"]]
    return {
        "ready": not blocking,
        "requested": {"resolution": resolution, "aspect": aspect, "subtitle_mode": subtitle_mode},
        "output": {"width": expected_width, "height": expected_height, "codec": "H.264"},
        "media_metadata": {
            "native_resolution": quality.get("native_resolution"),
            "conformed_resolution": (quality.get("final_master") or {}).get("conformed_resolution") if isinstance(quality.get("final_master"), dict) else None,
            "upscale_method": (quality.get("final_master") or {}).get("upscale_method") if isinstance(quality.get("final_master"), dict) else "none",
            "enhanced": bool((quality.get("final_master") or {}).get("enhanced", False)) if isinstance(quality.get("final_master"), dict) else False,
        },
        "checks": checks,
        "blocking": blocking,
        "warnings": warnings,
        "blocking_reasons": [checks[key]["message"] for key in blocking],
        "warning_messages": [checks[key]["message"] for key in warnings],
    }


__all__ = ["delivery_preflight", "diagnostics_snapshot"]
