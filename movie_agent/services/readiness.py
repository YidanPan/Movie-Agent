"""Canonical production blockers and action readiness.

This module is deliberately data-only: it translates persisted project state
into a small, JSON-safe contract that diagnostics, API guards, and the UI can
all consume without re-inventing stage rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from movie_agent.agents.visual_bible import validate_visual_bible_bindings
from movie_agent.services.audio import TRACK_ORDER
from movie_agent.services.media_quality import best_master_path
from movie_agent.services.production_contract import (
    ACTION_CONTRACT_SCHEMA_VERSION,
    PRODUCTION_ACTIONS,
    PRODUCTION_ACTION_CONTRACT,
    canonical_action,
    LEGACY_ACTION_ALIASES,
    transition_for,
)
from movie_agent.services.story_world import validate_story_world_references
from movie_agent.state import describe_status


DOMAINS = {"PLAN", "WORLD", "PREVIS", "RENDERER", "REFERENCE", "VISUAL", "AUDIO", "EDIT", "DELIVERY"}
SEVERITIES = {"INFO", "WARNING", "BLOCKING"}
ACTION_ORDER = (
    "START_RENDER",
    "START_AI_EDIT",
    "APPROVE_FINAL_CUT",
    "GENERATE_FINAL_MASTER",
    "EXPORT",
)
DOMAIN_PRIORITY = ("PLAN", "WORLD", "PREVIS", "RENDERER", "REFERENCE", "VISUAL", "AUDIO", "EDIT", "DELIVERY")


_DEFAULT_BLOCKER_ACTIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "PREVIS_REVIEW_REQUIRED": (
        ("START_RENDER", "RENDER_SHOT", "START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"),
        ("APPROVE_PREVIS", "REVIEW_STORYBOARD"),
    ),
    "UNKNOWN_SCENE_ID": (("START_RENDER", "RENDER_SHOT"), ("REVIEW_STORY_WORLD",)),
    "UNKNOWN_CHARACTER_ID": (("START_RENDER", "RENDER_SHOT"), ("REVIEW_STORY_WORLD",)),
    "UNKNOWN_PROP_ID": (("START_RENDER", "RENDER_SHOT"), ("REVIEW_STORY_WORLD",)),
    "MISSING_CHARACTER_LOCK": (("START_RENDER", "RENDER_SHOT"), ("REVIEW_VISUAL_BIBLE",)),
    "MISSING_SCENE_LOCK": (("START_RENDER", "RENDER_SHOT"), ("REVIEW_VISUAL_BIBLE",)),
    "MISSING_PROP_LOCK": (("START_RENDER", "RENDER_SHOT"), ("REVIEW_VISUAL_BIBLE",)),
    "WORKFLOW_MISSING": (("START_RENDER", "RENDER_SHOT"), ("OPEN_RENDER_DIAGNOSTICS",)),
    "WORKFLOW_INVALID": (("START_RENDER", "RENDER_SHOT"), ("OPEN_RENDER_DIAGNOSTICS",)),
    "WORKFLOW_COMPILE_FAILED": (("START_RENDER", "RENDER_SHOT"), ("OPEN_RENDER_DIAGNOSTICS",)),
    "UNSUPPORTED_GENERATION_MODE": (("START_RENDER", "RENDER_SHOT"), ("REVIEW_STORYBOARD",)),
    "STALE": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("START_RENDER", "RENDER_SHOT")),
    "MANUAL_VISUAL_REVIEW": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("REVIEW_SHOT",)),
    "CHARACTER_DRIFT": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("REVIEW_SHOT",)),
    "SCENE_DRIFT": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("REVIEW_SHOT",)),
    "PROP_DRIFT": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("REVIEW_SHOT",)),
    "STYLE_DRIFT": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("REVIEW_SHOT",)),
    "SCRIPT_TIMING_REVIEW": (("APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("START_AI_EDIT", "REVIEW_AUDIO_TIMELINE")),
    "SPEECH_OVERFLOW": (("APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("START_AI_EDIT", "REVIEW_AUDIO_TIMELINE")),
    "DIALOGUE_UNLOCKED": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("LOCK_DIALOGUE",)),
    "ROUGH_CUT_MISSING": (("APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("START_AI_EDIT",)),
    "FINAL_MASTER_MISSING": (("EXPORT",), ("GENERATE_FINAL_MASTER", "VERIFY_FINAL_MASTER")),
    "DELIVERY_PREFLIGHT_FAILED": (("EXPORT",), ("REVIEW_DELIVERY_PREFLIGHT",)),
    "ACTIVE_PROJECT_MUTATION_JOB": ((), ("OPEN_RENDER_DIAGNOSTICS",)),
    "VOICE_PROVIDER_REQUIRED": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT", "RENDER_AUDIO_TRACK"), ("OPEN_SOUND",)),
    "MUSIC_PROVIDER_REQUIRED": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT", "RENDER_AUDIO_TRACK"), ("OPEN_SOUND",)),
}


@dataclass(frozen=True)
class ProductionBlocker:
    code: str
    domain: str
    severity: str
    message: str
    shot_number: int | None = None
    track_key: str | None = None
    next_action: str | None = None
    blocking_stage: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    blocks_actions: tuple[str, ...] = ()
    resolves_by_actions: tuple[str, ...] = ()
    applies_to_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warns_actions"] = list(self.applies_to_actions)
        return payload


class ProductionBlockedError(ValueError):
    """Structured action-gate failure that is safe to return from the API."""

    error_code = "PRODUCTION_BLOCKED"

    def __init__(self, action: str, blockers: list[ProductionBlocker], *, shot_number: int | None = None, track_key: str | None = None) -> None:
        self.action = canonical_action(action)
        self.shot_number = shot_number
        self.track_key = track_key
        self.blockers = tuple(blockers)
        self.next_actions = tuple(dict.fromkeys(
            action_name
            for blocker in blockers
            for action_name in blocker.resolves_by_actions
        ))
        codes = ", ".join(blocker.code for blocker in blockers[:5]) or "UNKNOWN"
        super().__init__(f"{self.action} is blocked by {codes}.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "action": self.action,
            "shot_number": self.shot_number,
            "track_key": self.track_key,
            "blockers": [blocker.to_dict() for blocker in self.blockers],
            "next_actions": list(self.next_actions),
            "recoverable": bool(self.next_actions),
            "error": str(self),
        }


def _blocker(
    code: str,
    domain: str,
    message: str,
    *,
    severity: str = "BLOCKING",
    shot_number: int | None = None,
    track_key: str | None = None,
    next_action: str | None = None,
    blocking_stage: str | None = None,
    metadata: dict[str, Any] | None = None,
    blocks_actions: tuple[str, ...] | None = None,
    resolves_by_actions: tuple[str, ...] | None = None,
    applies_to_actions: tuple[str, ...] | None = None,
) -> ProductionBlocker:
    default_blocks, default_resolves = _DEFAULT_BLOCKER_ACTIONS.get(code, ((), ()))
    return ProductionBlocker(
        code=code,
        domain=domain,
        severity=severity,
        message=message,
        shot_number=shot_number,
        track_key=track_key,
        next_action=canonical_action(next_action) if next_action else None,
        blocking_stage=blocking_stage or domain,
        metadata=dict(metadata or {}),
        blocks_actions=tuple(canonical_action(value) for value in (blocks_actions if blocks_actions is not None else default_blocks)),
        resolves_by_actions=tuple(canonical_action(value) for value in (resolves_by_actions if resolves_by_actions is not None else default_resolves)),
        applies_to_actions=tuple(canonical_action(value) for value in (applies_to_actions or ())),
    )


@dataclass(frozen=True)
class ProductionActionContext:
    action: str
    shot_number: int | None = None
    track_key: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", canonical_action(self.action))


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
    video_mode = str(_setting(settings, "video_generation_mode", "mock") or "mock").lower()
    for shot in list(getattr(project, "storyboard", []) or []):
        details = getattr(shot, "qc_details", {}) or {}
        strategy = str(details.get("reference_strategy") or "") if isinstance(details, dict) else ""
        required = bool(details.get("reference_required")) if isinstance(details, dict) else False
        if isinstance(details, dict):
            required = required or str(details.get("reference_policy") or "").lower() == "required"
        required = required or strategy.upper() in {"I2V", "R2V", "RENDER_REQUIRED"}
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
                severity="BLOCKING" if required and video_mode != "mock" else "WARNING",
                shot_number=int(getattr(shot, "number", 0) or 0) or None,
                next_action="OPEN_REFERENCE_BANK",
                blocking_stage="RENDER",
                blocks_actions=("START_RENDER", "RENDER_SHOT") if required and video_mode != "mock" else (),
                applies_to_actions=("START_RENDER", "RENDER_SHOT"),
                resolves_by_actions=("OPEN_REFERENCE_BANK", "REVIEW_VISUAL_BIBLE"),
            ))
    return result


def _runtime_job_blockers(runtime_state: dict[str, Any] | None) -> list[ProductionBlocker]:
    """Translate the single active project mutation into one action blocker."""

    result: list[ProductionBlocker] = []
    for job in (runtime_state or {}).get("active_jobs", []) if isinstance(runtime_state, dict) else []:
        if not isinstance(job, dict) or str(job.get("status") or "").lower() not in {"queued", "running", "active"}:
            continue
        if job.get("mutates_project") is False:
            continue
        kind = str(job.get("kind") or job.get("stage") or "pipeline").lower()
        shot_number = job.get("shot_number")
        track_key = str(job.get("track_key") or "").strip().lower() or None
        try:
            shot_number = int(shot_number) if shot_number is not None else None
        except (TypeError, ValueError):
            shot_number = None
        actions = tuple(
            action
            for action, metadata in PRODUCTION_ACTIONS.items()
            if metadata.get("mutates_project") is True
        )
        if track_key:
            target = f"AUDIO TRACK {track_key.upper()}"
        elif shot_number is not None:
            target = f"SHOT {shot_number:02d}"
        else:
            target = "PROJECT"
        message = f"{target} is currently being changed by an active {kind.replace('_', ' ')} job."
        next_action = "OPEN_SOUND" if track_key else "OPEN_RENDER_DIAGNOSTICS"
        result.append(_blocker(
            "ACTIVE_PROJECT_MUTATION_JOB",
            "AUDIO" if track_key else "RENDERER" if "render" in kind or "generation" in kind else "EDIT",
            message,
            shot_number=shot_number,
            track_key=track_key,
            next_action=next_action,
            blocking_stage="RENDER" if "render" in kind or "generation" in kind else "EDIT",
            blocks_actions=actions,
            resolves_by_actions=(next_action,),
            metadata={"job_id": str(job.get("job_id") or ""), "job_kind": kind},
        ))
    return result


def production_blockers(project: Any, settings: Any = None, runtime_state: dict[str, Any] | None = None) -> list[ProductionBlocker]:
    """Collect all known blockers from the persisted project truth."""

    blockers: list[ProductionBlocker] = []
    blockers.extend(_runtime_job_blockers(runtime_state))
    status = str(getattr(project, "status", "") or "").lower()
    storyboard = list(getattr(project, "storyboard", []) or [])
    world = getattr(project, "story_world", {}) or {}
    visual_bible = getattr(project, "visual_bible", {}) or {}

    def affected_shots(kind: str, entity_id: str) -> list[int]:
        result: list[int] = []
        for candidate in storyboard:
            number = int(getattr(candidate, "number", 0) or 0)
            if kind == "scene" and str(getattr(candidate, "scene_id", "") or "") == entity_id:
                result.append(number)
            elif kind == "character" and entity_id in {str(value) for value in (getattr(candidate, "character_ids", []) or [])}:
                result.append(number)
            elif kind == "prop" and entity_id in {str(value) for value in (getattr(candidate, "prop_ids", []) or [])}:
                result.append(number)
        return result

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
            blockers.append(_blocker(code, "WORLD", f"Unknown {label} ID: {value}.", next_action="REVIEW_STORY_WORLD", blocking_stage="RENDER", metadata={"entity_id": value, "affected_shots": affected_shots(label, str(value))}))

    missing_locks = validate_visual_bible_bindings(visual_bible, world)
    for key, code, label in (
        ("missing_character_locks", "MISSING_CHARACTER_LOCK", "character"),
        ("missing_scene_locks", "MISSING_SCENE_LOCK", "scene"),
        ("missing_prop_locks", "MISSING_PROP_LOCK", "prop"),
    ):
        for value in missing_locks.get(key, []) or []:
            blockers.append(_blocker(code, "WORLD", f"Visual Bible has no locked {label}: {value}.", next_action="REVIEW_VISUAL_BIBLE", blocking_stage="RENDER", metadata={"entity_id": value, "affected_shots": affected_shots(label, str(value))}))

    video_mode = str(_setting(settings, "video_generation_mode", "mock") or "mock").lower()
    renderer = getattr(project, "renderer_contract", {}) or {}
    renderer_status = str(renderer.get("status") or "").upper() if isinstance(renderer, dict) else ""
    renderer_codes = {"WORKFLOW_MISSING", "WORKFLOW_INVALID", "WORKFLOW_COMPILE_FAILED", "UNSUPPORTED_GENERATION_MODE"}
    if video_mode == "comfyui" and renderer_status in renderer_codes:
        blockers.append(_blocker(renderer_status, "RENDERER", f"Renderer contract is {renderer_status.replace('_', ' ').lower()}.", next_action="OPEN_RENDER_DIAGNOSTICS", blocking_stage="RENDER"))

    reference_blockers = _reference_blockers(project, settings)
    reference_by_shot: dict[int, list[ProductionBlocker]] = {}
    for item in reference_blockers:
        if item.shot_number is not None:
            reference_by_shot.setdefault(item.shot_number, []).append(item)

    for shot in storyboard:
        number = int(getattr(shot, "number", 0) or 0) or None
        source = _shot_source(shot)
        verification = str(source.get("renderer_verification_status") or "").upper()
        if bool(getattr(shot, "stale", False)) or bool(source.get("stale")):
            blockers.append(_blocker("STALE", "RENDERER", "Current shot media is stale and must be regenerated.", shot_number=number, next_action="RENDER_SHOT", blocking_stage="RENDER"))
        elif verification == "UNVERIFIED_LEGACY":
            blockers.append(_blocker("UNVERIFIED_LEGACY", "RENDERER", "Legacy shot media has not been verified against the renderer contract.", severity="WARNING", shot_number=number, next_action="REVIEW_RENDER_DIAGNOSTICS", blocking_stage="RENDER", applies_to_actions=("START_RENDER", "RENDER_SHOT", "START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT")))

        blockers.extend(reference_by_shot.get(number or 0, []))
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
    audio_tracks = getattr(project, "audio_tracks", {}) or {}
    audio_requirements = (
        ("voice", "VOICE_PROVIDER_REQUIRED", {"AUDIO PENDING", "PROVIDER REQUIRED", "VOICE_PROVIDER_REQUIRED"}, "A voice provider or real voice asset is required."),
        ("music", "MUSIC_PROVIDER_REQUIRED", {"AUDIO PENDING", "PROVIDER REQUIRED", "MUSIC_PROVIDER_REQUIRED", "BRIEF READY · AUDIO PENDING"}, "A music provider or real score asset is required."),
    )
    for track_key, code, pending_statuses, message in audio_requirements:
        track = audio_tracks.get(track_key, {}) if isinstance(audio_tracks, dict) else {}
        if not isinstance(track, dict) or str(track.get("status") or "").upper() not in pending_statuses:
            continue
        # Mock projects intentionally have no real renderer for every track.
        # Keep that fact visible as a warning, while real-provider projects
        # treat the affected track as a production gate.
        severity = "WARNING" if settings is None or bool(_setting(settings, "mock_mode", False)) else "BLOCKING"
        blocks = ("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT", "RENDER_AUDIO_TRACK")
        applies = ("REPLAN_AUDIO_TRACK", "RENDER_AUDIO_TRACK", "REVIEW_AUDIO_TRACK")
        blockers.append(_blocker(
            code,
            "AUDIO",
            message,
            severity=severity,
            track_key=track_key,
            next_action="OPEN_SOUND",
            blocking_stage="EDIT",
            blocks_actions=blocks,
            applies_to_actions=applies,
        ))

    dialogue_locked = bool(script.get("dialogue_locked")) if isinstance(script, dict) else False
    if status in {"ready_for_ai_edit", "editing_rough_cut", "rough_cut_ready", "editing_final", "final_cut_approved", "completed_mock", "completed_text_ai_video_mock", "completed_comfyui"} and not dialogue_locked:
        blockers.append(_blocker("DIALOGUE_UNLOCKED", "EDIT", "Dialogue and subtitle timing must be locked before editing.", next_action="LOCK_DIALOGUE", blocking_stage="EDIT"))
    has_rough_cut = bool(getattr(project, "rough_cut_placeholder", None) or (getattr(project, "edit_plan", {}) or {}).get("output_path"))
    if status == "rough_cut_ready" and not has_rough_cut:
        blockers.append(_blocker("ROUGH_CUT_MISSING", "EDIT", "The current rough cut output is missing.", next_action="START_AI_EDIT", blocking_stage="EDIT"))

    if status.startswith("completed") or status in {"final_cut_approved", "exported"}:
        master = (getattr(project, "video_assets", {}) or {}).get("final_master")
        master_path = best_master_path(project)
        if not (isinstance(master, dict) and not master.get("stale") and (master.get("exists") or (master_path and Path(master_path).is_file()))):
            blockers.append(_blocker(
                "FINAL_MASTER_MISSING",
                "DELIVERY",
                "The current Final Master is missing.",
                next_action="GENERATE_FINAL_MASTER",
                blocking_stage="DELIVERY",
                resolves_by_actions=("GENERATE_FINAL_MASTER", "VERIFY_FINAL_MASTER"),
            ))
    last_error = getattr(project, "last_error", {}) or {}
    if isinstance(last_error, dict) and str(last_error.get("stage") or "").lower() in {"export", "delivery"}:
        blockers.append(_blocker("DELIVERY_PREFLIGHT_FAILED", "DELIVERY", "Delivery preflight requires attention before export.", next_action="REVIEW_DELIVERY_PREFLIGHT", blocking_stage="DELIVERY"))

    deduped: list[ProductionBlocker] = []
    seen: set[tuple[Any, ...]] = set()
    for item in blockers:
        key = (item.code, item.domain, item.shot_number, item.track_key, item.metadata.get("entity_id"), item.metadata.get("job_id"))
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    severity_order = {"BLOCKING": 0, "WARNING": 1, "INFO": 2}
    stage = describe_status(status)["stage"]
    stage_domains = {
        "PLAN": {"PLAN", "WORLD", "PREVIS"},
        "PREVIS": {"PLAN", "WORLD", "PREVIS"},
        "RENDER": {"RENDERER", "REFERENCE", "VISUAL"},
        "DELIVER": {"VISUAL", "AUDIO", "EDIT", "DELIVERY"},
    }.get(stage, set())
    domain_rank = {domain: index for index, domain in enumerate(DOMAIN_PRIORITY)}
    return sorted(
        deduped,
        key=lambda item: (
            severity_order.get(item.severity, 9),
            0 if item.domain in stage_domains else 1,
            domain_rank.get(item.domain, 99),
            item.shot_number or 0,
            item.code,
        ),
    )


def production_readiness(project: Any, settings: Any = None, runtime_state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the one readiness contract used by API, diagnostics, and UI."""

    blockers = production_blockers(project, settings, runtime_state)
    storyboard = list(getattr(project, "storyboard", []) or [])
    blocking = [item for item in blockers if item.severity == "BLOCKING"]
    warnings = [item for item in blockers if item.severity == "WARNING"]
    global_blocking = [item for item in blocking if item.shot_number is None and item.track_key is None]
    next_action = next(
        (
            item.next_action
            for item in blockers
            if item.next_action and (item.severity == "BLOCKING" or item.track_key is None)
        ),
        None,
    )
    state = describe_status(getattr(project, "status", "planning_live"))
    actions = {
        action: _action_readiness_from_blockers(blockers, action)
        for action, metadata in PRODUCTION_ACTIONS.items()
        if metadata.get("scope") == "project"
    }
    shot_actions = {
        str(int(getattr(shot, "number", 0) or 0)): {
            "RENDER_SHOT": _action_readiness_from_blockers(blockers, "RENDER_SHOT", shot_number=int(getattr(shot, "number", 0) or 0)),
            "REPLAN_SHOT": _action_readiness_from_blockers(blockers, "REPLAN_SHOT", shot_number=int(getattr(shot, "number", 0) or 0)),
            "REVIEW_SHOT": _action_readiness_from_blockers(blockers, "REVIEW_SHOT", shot_number=int(getattr(shot, "number", 0) or 0)),
            "APPROVE_SHOT": _action_readiness_from_blockers(blockers, "APPROVE_SHOT", shot_number=int(getattr(shot, "number", 0) or 0)),
        }
        for shot in storyboard
        if int(getattr(shot, "number", 0) or 0)
    }
    track_actions = {
        track_key: {
            "REPLAN_AUDIO_TRACK": _action_readiness_from_blockers(blockers, "REPLAN_AUDIO_TRACK", track_key=track_key),
            "RENDER_AUDIO_TRACK": _action_readiness_from_blockers(blockers, "RENDER_AUDIO_TRACK", track_key=track_key),
            "REVIEW_AUDIO_TRACK": _action_readiness_from_blockers(blockers, "REVIEW_AUDIO_TRACK", track_key=track_key),
        }
        for track_key in TRACK_ORDER
    }
    return {
        "ready": not blocking,
        "global_clear": not global_blocking,
        "clear_of_blockers": not blocking,
        "current_stage": state["stage"],
        "blockers": [item.to_dict() for item in blockers],
        "next_action": next_action,
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "actions": actions,
        "shot_actions": shot_actions,
        "track_actions": track_actions,
    }


def _action_readiness_from_blockers(
    blockers: list[ProductionBlocker],
    action: str,
    *,
    shot_number: int | None = None,
    track_key: str | None = None,
) -> dict[str, Any]:
    action = canonical_action(action)
    blocking = [item for item in blockers if _blocker_matches_context(item, action, shot_number, track_key, blocking=True)]
    warnings = [item for item in blockers if _blocker_matches_context(item, action, shot_number, track_key, blocking=False)]
    resolution_actions = list(dict.fromkeys(
        action_name
        for item in blocking
        for action_name in item.resolves_by_actions
    ))
    return {
        "action": action,
        "shot_number": shot_number,
        "track_key": track_key,
        "ready": not blocking,
        "blockers": [item.to_dict() for item in blocking],
        "warnings": [item.to_dict() for item in warnings],
        "resolution_actions": resolution_actions,
        "blocking_count": len(blocking),
    }


def action_blockers(project: Any, settings: Any, action: str, *, shot_number: int | None = None, track_key: str | None = None, runtime_state: dict[str, Any] | None = None) -> list[ProductionBlocker]:
    """Return blockers that explicitly declare this action unsafe."""

    action = canonical_action(action)
    shot_number = _validate_shot_number(project, shot_number) if shot_number is not None else None
    blockers = production_blockers(project, settings, runtime_state)
    state_blocker = _action_state_blocker(project, action)
    if state_blocker:
        blockers.append(state_blocker)
    return [
        item
        for item in blockers
        if _blocker_matches_context(item, action, shot_number, track_key, blocking=True)
    ]


def _blocker_matches_context(
    item: ProductionBlocker,
    action: str,
    shot_number: int | None,
    track_key: str | None,
    *,
    blocking: bool,
) -> bool:
    action = canonical_action(action)
    if item.severity == "BLOCKING" and not blocking:
        return False
    if item.severity != "BLOCKING" and blocking:
        return False
    affected = item.metadata.get("affected_shots") if isinstance(item.metadata, dict) else None
    project_serialized_job = item.code == "ACTIVE_PROJECT_MUTATION_JOB"
    if shot_number is not None and not project_serialized_job:
        if item.shot_number is not None and item.shot_number != shot_number:
            return False
        if affected and shot_number not in {int(value) for value in affected}:
            return False
    if track_key is not None and item.track_key is not None and item.track_key != track_key and not project_serialized_job:
        return False
    if item.shot_number is not None and shot_number is None and action in {"RENDER_SHOT", "REPLAN_SHOT"} and not project_serialized_job:
        return False
    if blocking:
        return action in {canonical_action(value) for value in item.blocks_actions}
    applies = item.applies_to_actions
    return bool(applies) and action in {canonical_action(value) for value in applies}


def _action_state_blocker(project: Any, action: str) -> ProductionBlocker | None:
    transition = transition_for(getattr(project, "status", "planning_live"), action)
    if transition.allowed:
        return None
    return _blocker(
        "ACTION_STATE_INVALID",
        "PLAN",
        f"{transition.action} is not allowed from {transition.current_state.upper()}.",
        blocks_actions=(transition.action,),
        metadata={"current_state": transition.current_state, "action": transition.action},
    )


def _validate_shot_number(project: Any, shot_number: int | None) -> int | None:
    if shot_number is None:
        return None
    try:
        value = int(shot_number)
    except (TypeError, ValueError) as exc:
        raise ValueError("shot_number must be an integer") from exc
    valid = {int(getattr(shot, "number", 0) or 0) for shot in (getattr(project, "storyboard", []) or [])}
    if value not in valid:
        raise ValueError(f"Invalid shot number: {value}")
    return value


def _validate_track_key(action: str, track_key: str | None) -> str | None:
    scope = (PRODUCTION_ACTIONS.get(canonical_action(action)) or {}).get("scope")
    if scope == "track":
        value = str(track_key or "").strip().lower()
        if value not in TRACK_ORDER:
            raise ValueError(f"Invalid audio track: {track_key}")
        return value
    if track_key is not None:
        raise ValueError(f"Action {canonical_action(action)} does not accept an audio track target.")
    return None


def action_blockers_for_context(project: Any, settings: Any, context: ProductionActionContext, runtime_state: dict[str, Any] | None = None) -> list[ProductionBlocker]:
    blockers = production_blockers(project, settings, runtime_state)
    state_blocker = _action_state_blocker(project, context.action)
    if state_blocker:
        blockers.append(state_blocker)
    return [item for item in blockers if _blocker_matches_context(item, context.action, context.shot_number, context.track_key, blocking=True)]


def action_readiness(project: Any, settings: Any, action: str, *, shot_number: int | None = None, track_key: str | None = None, runtime_state: dict[str, Any] | None = None) -> dict[str, Any]:
    action = canonical_action(action)
    shot_number = _validate_shot_number(project, shot_number) if shot_number is not None else None
    track_key = _validate_track_key(action, track_key)
    scope = (PRODUCTION_ACTIONS.get(action) or {}).get("scope")
    if scope == "shot" and shot_number is None:
        raise ValueError(f"Action {action} requires a shot target.")
    blockers = production_blockers(project, settings, runtime_state)
    state_blocker = _action_state_blocker(project, action)
    if state_blocker:
        blockers.append(state_blocker)
    return _action_readiness_from_blockers(blockers, action, shot_number=shot_number, track_key=track_key)


def ensure_action_ready(project: Any, settings: Any, action: str, *, shot_number: int | None = None, track_key: str | None = None, runtime_state: dict[str, Any] | None = None) -> None:
    canonical = canonical_action(action)
    shot_number = _validate_shot_number(project, shot_number) if shot_number is not None else None
    track_key = _validate_track_key(canonical, track_key)
    scope = (PRODUCTION_ACTIONS.get(canonical) or {}).get("scope")
    if scope == "shot" and shot_number is None:
        raise ValueError(f"Action {canonical} requires a shot target.")
    context = ProductionActionContext(canonical, shot_number=shot_number, track_key=track_key)
    blockers = action_blockers_for_context(project, settings, context, runtime_state)
    if blockers:
        raise ProductionBlockedError(canonical, blockers, shot_number=shot_number, track_key=track_key)


__all__ = [
    "ACTION_ORDER",
    "ACTION_CONTRACT_SCHEMA_VERSION",
    "PRODUCTION_ACTIONS",
    "PRODUCTION_ACTION_CONTRACT",
    "DOMAINS",
    "DOMAIN_PRIORITY",
    "SEVERITIES",
    "ProductionBlocker",
    "ProductionActionContext",
    "ProductionBlockedError",
    "action_blockers",
    "action_blockers_for_context",
    "action_readiness",
    "canonical_action",
    "ensure_action_ready",
    "production_blockers",
    "production_readiness",
]
