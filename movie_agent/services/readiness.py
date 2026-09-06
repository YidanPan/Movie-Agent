"""Canonical production blockers and action readiness.

This module is deliberately data-only: it translates persisted project state
into a small, JSON-safe contract that diagnostics, API guards, and the UI can
all consume without re-inventing stage rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from movie_agent.agents.visual_bible import validate_visual_bible_bindings
from movie_agent.services.media_quality import best_master_path
from movie_agent.services.story_world import validate_story_world_references
from movie_agent.state import describe_status


DOMAINS = {"PLAN", "WORLD", "PREVIS", "RENDERER", "REFERENCE", "VISUAL", "AUDIO", "EDIT", "DELIVERY"}
SEVERITIES = {"INFO", "WARNING", "BLOCKING"}


@dataclass(frozen=True)
class ProductionBlocker:
    code: str
    domain: str
    severity: str
    message: str
    shot_number: int | None = None
    next_action: str | None = None
    blocking_stage: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _blocker(
    code: str,
    domain: str,
    message: str,
    *,
    severity: str = "BLOCKING",
    shot_number: int | None = None,
    next_action: str | None = None,
    blocking_stage: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProductionBlocker:
    return ProductionBlocker(
        code=code,
        domain=domain,
        severity=severity,
        message=message,
        shot_number=shot_number,
        next_action=next_action,
        blocking_stage=blocking_stage or domain,
        metadata=dict(metadata or {}),
    )


def _setting(settings: Any, name: str, default: Any = None) -> Any:
    return getattr(settings, name, default) if settings is not None else default


def _shot_source(shot: Any) -> dict[str, Any]:
    assets = getattr(shot, "media_assets", {}) or {}
    source = assets.get("source") if isinstance(assets, dict) else None
    return source if isinstance(source, dict) else {}


def _shot_reference_flags(shot: Any) -> list[str]:
    details = getattr(shot, "qc_details", {}) or {}
    flags: list[str] = []
    if isinstance(details, dict):
        for key in ("reference_flags",):
            values = details.get(key) or []
            if isinstance(values, str):
                values = [values]
            flags.extend(str(value).upper() for value in values)
        for key in ("reference_inputs", "reference_strategy"):
            value = details.get(key)
            if isinstance(value, dict):
                values = value.get("reference_flags") or []
                if isinstance(values, str):
                    values = [values]
                flags.extend(str(item).upper() for item in values)
    return list(dict.fromkeys(flags))


def _shot_qc_flags(shot: Any) -> list[str]:
    flags = [str(value).upper() for value in (getattr(shot, "qc_flags", []) or [])]
    details = getattr(shot, "qc_details", {}) or {}
    if isinstance(details, dict):
        for key in ("flags", "drift_flags"):
            values = details.get(key) or []
            if isinstance(values, str):
                values = [values]
            flags.extend(str(value).upper() for value in values)
        visual = details.get("visual")
        if isinstance(visual, dict):
            values = visual.get("drift_flags") or []
            if isinstance(values, str):
                values = [values]
            flags.extend(str(value).upper() for value in values)
    return list(dict.fromkeys(flags))


def _reference_blockers(project: Any, settings: Any) -> list[ProductionBlocker]:
    # Generation and QC persist the exact missing-reference flags on the shot.
    # Re-reading the bank here would make readiness depend on filesystem shape
    # rather than the saved revision contract.
    result: list[ProductionBlocker] = []
    for shot in list(getattr(project, "storyboard", []) or []):
        for code in _shot_reference_flags(shot):
            if code not in {"MISSING_CHARACTER_REFERENCE", "MISSING_SCENE_REFERENCE", "MISSING_PROP_REFERENCE", "MISSING_PREVIOUS_ENDING_REFERENCE"}:
                continue
            result.append(_blocker(
                code,
                "REFERENCE",
                {
                    "MISSING_CHARACTER_REFERENCE": "A current approved character reference is missing.",
                    "MISSING_SCENE_REFERENCE": "A current approved scene reference is missing.",
                    "MISSING_PROP_REFERENCE": "A current approved prop reference is missing.",
                    "MISSING_PREVIOUS_ENDING_REFERENCE": "The previous approved shot ending reference is missing.",
                }[code],
                shot_number=int(getattr(shot, "number", 0) or 0) or None,
                next_action="OPEN_REFERENCE_BANK",
                blocking_stage="RENDER",
            ))
    return result


def production_blockers(project: Any, settings: Any = None) -> list[ProductionBlocker]:
    """Collect all known blockers from the persisted project truth."""

    blockers: list[ProductionBlocker] = []
    status = str(getattr(project, "status", "") or "").lower()
    storyboard = list(getattr(project, "storyboard", []) or [])
    world = getattr(project, "story_world", {}) or {}
    visual_bible = getattr(project, "visual_bible", {}) or {}

    if status == "previs_review_required" or (getattr(project, "storyboard_review", {}) or {}).get("decision") not in {None, "PASS"}:
        blockers.append(_blocker("PREVIS_REVIEW_REQUIRED", "PREVIS", "Storyboard review must be approved before rendering.", next_action="APPROVE_PREVIS", blocking_stage="RENDER"))

    unknown = validate_story_world_references(storyboard, world)
    for key, code, label in (
        ("unknown_scene", "UNKNOWN_SCENE_ID", "scene"),
        ("unknown_character", "UNKNOWN_CHARACTER_ID", "character"),
        ("unknown_prop", "UNKNOWN_PROP_ID", "prop"),
    ):
        values = unknown.get(f"{key}s", []) or unknown.get(f"{key}s".replace("unknown_", ""), [])
        if not values:
            values = unknown.get({"unknown_scene": "unknown_scenes", "unknown_character": "unknown_characters", "unknown_prop": "unknown_props"}[key], [])
        for value in values:
            blockers.append(_blocker(code, "WORLD", f"Unknown {label} ID: {value}.", next_action="REPLAN_STORY_WORLD", blocking_stage="RENDER", metadata={"entity_id": value}))

    missing_locks = validate_visual_bible_bindings(visual_bible, world)
    for key, code, label in (
        ("missing_character_locks", "MISSING_CHARACTER_LOCK", "character"),
        ("missing_scene_locks", "MISSING_SCENE_LOCK", "scene"),
        ("missing_prop_locks", "MISSING_PROP_LOCK", "prop"),
    ):
        for value in missing_locks.get(key, []) or []:
            blockers.append(_blocker(code, "WORLD", f"Visual Bible has no locked {label}: {value}.", next_action="REVIEW_VISUAL_BIBLE", blocking_stage="RENDER", metadata={"entity_id": value}))

    video_mode = str(_setting(settings, "video_generation_mode", "mock") or "mock").lower()
    renderer = getattr(project, "renderer_contract", {}) or {}
    renderer_status = str(renderer.get("status") or "").upper() if isinstance(renderer, dict) else ""
    renderer_codes = {"WORKFLOW_MISSING", "WORKFLOW_INVALID", "WORKFLOW_COMPILE_FAILED", "UNSUPPORTED_GENERATION_MODE"}
    if video_mode == "comfyui" and renderer_status in renderer_codes:
        blockers.append(_blocker(renderer_status, "RENDERER", f"Renderer contract is {renderer_status.replace('_', ' ').lower()}.", next_action="OPEN_RENDER_DIAGNOSTICS", blocking_stage="RENDER"))

    for shot in storyboard:
        number = int(getattr(shot, "number", 0) or 0) or None
        source = _shot_source(shot)
        verification = str(source.get("renderer_verification_status") or "").upper()
        if bool(getattr(shot, "stale", False)) or bool(source.get("stale")):
            blockers.append(_blocker("STALE", "RENDERER", "Current shot media is stale and must be regenerated.", shot_number=number, next_action="REGENERATE_SHOT", blocking_stage="RENDER"))
        elif verification == "UNVERIFIED_LEGACY":
            blockers.append(_blocker("UNVERIFIED_LEGACY", "RENDERER", "Legacy shot media has not been verified against the renderer contract.", severity="WARNING", shot_number=number, next_action="REVIEW_RENDER_DIAGNOSTICS", blocking_stage="RENDER"))

        for code in _reference_blockers(project, settings):
            if code.shot_number == number:
                blockers.append(code)
        flags = _shot_qc_flags(shot)
        if str(getattr(shot, "status", "")).lower() == "awaiting_visual_review" or str(getattr(shot, "qc_status", "")).upper() in {"AWAITING_VISUAL_REVIEW", "PASSED_MANUAL_REVIEW_REQUIRED"} or "MANUAL_VISUAL_REVIEW" in flags:
            blockers.append(_blocker("MANUAL_VISUAL_REVIEW", "VISUAL", "Generated media is waiting for explicit human visual review.", shot_number=number, next_action="REVIEW_SHOT", blocking_stage="EDIT"))
        for code in ("CHARACTER_DRIFT", "SCENE_DRIFT", "PROP_DRIFT", "STYLE_DRIFT"):
            if code in flags:
                blockers.append(_blocker(code, "VISUAL", f"Visual QC flagged {code.replace('_', ' ').lower()}.", shot_number=number, next_action="REVIEW_SHOT", blocking_stage="EDIT"))

    script = getattr(project, "script", {}) or {}
    voice_timeline = script.get("voice_timeline") if isinstance(script, dict) else None
    if isinstance(voice_timeline, dict):
        timeline_status = str(voice_timeline.get("status") or "").upper()
        if timeline_status in {"SCRIPT_TIMING_REVIEW", "REVIEW_REQUIRED", "TIMING_REVIEW"}:
            blockers.append(_blocker("SCRIPT_TIMING_REVIEW", "AUDIO", "Voice timing needs review before edit approval.", next_action="REVIEW_AUDIO_TIMELINE", blocking_stage="EDIT"))
        if bool(voice_timeline.get("overflow")) or bool(voice_timeline.get("speech_overflow")):
            blockers.append(_blocker("SPEECH_OVERFLOW", "AUDIO", "Voice duration exceeds its available timing window.", next_action="REVIEW_AUDIO_TIMELINE", blocking_stage="EDIT"))
    voice = (getattr(project, "audio_tracks", {}) or {}).get("voice", {})
    if isinstance(voice, dict) and voice.get("status") in {"AUDIO PENDING", "PROVIDER REQUIRED", "VOICE_PROVIDER_REQUIRED"}:
        # Mock projects intentionally have no real voice renderer.  Keep that
        # fact visible as a warning, while real-provider projects treat it as
        # a production gate.
        severity = "WARNING" if bool(_setting(settings, "mock_mode", False)) else "BLOCKING"
        blockers.append(_blocker("VOICE_PROVIDER_REQUIRED", "AUDIO", "A voice provider or real voice asset is required.", severity=severity, next_action="OPEN_SOUND", blocking_stage="EDIT"))

    dialogue_locked = bool(script.get("dialogue_locked")) if isinstance(script, dict) else False
    if status in {"ready_for_ai_edit", "editing_rough_cut", "rough_cut_ready", "editing_final", "completed_mock", "completed_text_ai_video_mock", "completed_comfyui"} and not dialogue_locked:
        blockers.append(_blocker("DIALOGUE_UNLOCKED", "EDIT", "Dialogue and subtitle timing must be locked before editing.", next_action="LOCK_DIALOGUE", blocking_stage="EDIT"))
    has_rough_cut = bool(getattr(project, "rough_cut_placeholder", None) or (getattr(project, "edit_plan", {}) or {}).get("output_path"))
    if status == "rough_cut_ready" and not has_rough_cut:
        blockers.append(_blocker("ROUGH_CUT_MISSING", "EDIT", "The current rough cut output is missing.", next_action="START_AI_EDIT", blocking_stage="EDIT"))

    if status.startswith("completed") or status == "exported":
        master = (getattr(project, "video_assets", {}) or {}).get("final_master")
        master_path = best_master_path(project)
        if not (isinstance(master, dict) and not master.get("stale") and (master.get("exists") or (master_path and Path(master_path).is_file()))):
            blockers.append(_blocker("FINAL_MASTER_MISSING", "DELIVERY", "The current Final Master is missing.", next_action="VERIFY_FINAL_MASTER", blocking_stage="DELIVERY"))
    last_error = getattr(project, "last_error", {}) or {}
    if isinstance(last_error, dict) and str(last_error.get("stage") or "").lower() in {"export", "delivery"}:
        blockers.append(_blocker("DELIVERY_PREFLIGHT_FAILED", "DELIVERY", "Delivery preflight requires attention before export.", next_action="REVIEW_DELIVERY_PREFLIGHT", blocking_stage="DELIVERY"))

    deduped: list[ProductionBlocker] = []
    seen: set[tuple[Any, ...]] = set()
    for item in blockers:
        key = (item.code, item.domain, item.shot_number, item.metadata.get("entity_id"))
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    severity_order = {"BLOCKING": 0, "WARNING": 1, "INFO": 2}
    return sorted(deduped, key=lambda item: (severity_order.get(item.severity, 9), item.domain, item.shot_number or 0, item.code))


def production_readiness(project: Any, settings: Any = None) -> dict[str, Any]:
    """Return the one readiness contract used by API, diagnostics, and UI."""

    blockers = production_blockers(project, settings)
    blocking = [item for item in blockers if item.severity == "BLOCKING"]
    warnings = [item for item in blockers if item.severity == "WARNING"]
    next_action = next((item.next_action for item in blockers if item.next_action), None)
    state = describe_status(getattr(project, "status", "planning_live"))
    return {
        "ready": not blocking,
        "current_stage": state["stage"],
        "blockers": [item.to_dict() for item in blockers],
        "next_action": next_action,
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
    }


_ACTION_DOMAINS = {
    "START_RENDER": {"PLAN", "WORLD", "PREVIS", "RENDERER", "REFERENCE"},
    "START_AI_EDIT": {"VISUAL", "REFERENCE", "AUDIO", "EDIT", "RENDERER"},
    "APPROVE_FINAL_CUT": {"VISUAL", "AUDIO", "EDIT"},
    "GENERATE_FINAL_MASTER": {"DELIVERY", "VISUAL", "AUDIO", "EDIT"},
    "EXPORT": {"DELIVERY", "VISUAL", "AUDIO", "EDIT"},
}


def action_blockers(project: Any, settings: Any, action: str) -> list[ProductionBlocker]:
    domains = _ACTION_DOMAINS.get(str(action).upper(), set(DOMAINS))
    return [item for item in production_blockers(project, settings) if item.severity == "BLOCKING" and item.domain in domains]


def ensure_action_ready(project: Any, settings: Any, action: str) -> None:
    blockers = action_blockers(project, settings, action)
    if blockers:
        codes = ", ".join(item.code for item in blockers[:5])
        raise ValueError(f"PRODUCTION_BLOCKED: {codes}. {blockers[0].message}")


__all__ = [
    "DOMAINS",
    "SEVERITIES",
    "ProductionBlocker",
    "action_blockers",
    "ensure_action_ready",
    "production_blockers",
    "production_readiness",
]
