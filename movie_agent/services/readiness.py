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
from movie_agent.services.media_quality import best_master_path
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
LEGACY_ACTION_ALIASES = {"REGENERATE_SHOT": "RENDER_SHOT"}
PRODUCTION_ACTIONS = {
    "START_RENDER": {"scope": "project", "kind": "execute"},
    "RENDER_SHOT": {"scope": "shot", "kind": "execute"},
    "REPLAN_SHOT": {"scope": "shot", "kind": "plan"},
    "START_AI_EDIT": {"scope": "project", "kind": "execute"},
    "APPROVE_FINAL_CUT": {"scope": "project", "kind": "review"},
    "GENERATE_FINAL_MASTER": {"scope": "project", "kind": "execute"},
    "EXPORT": {"scope": "project", "kind": "execute"},
    "APPROVE_PREVIS": {"scope": "project", "kind": "review"},
    "REPLAN_STORYBOARD": {"scope": "project", "kind": "plan"},
    "REPLAN_STORY_WORLD": {"scope": "project", "kind": "plan"},
    "REVIEW_VISUAL_BIBLE": {"scope": "project", "kind": "review"},
    "OPEN_REFERENCE_BANK": {"scope": "project", "kind": "review"},
    "REVIEW_SHOT": {"scope": "shot", "kind": "review"},
    "REVIEW_AUDIO_TIMELINE": {"scope": "project", "kind": "review"},
    "OPEN_SOUND": {"scope": "project", "kind": "review"},
    "OPEN_RENDER_DIAGNOSTICS": {"scope": "project", "kind": "review"},
    "REVIEW_RENDER_DIAGNOSTICS": {"scope": "project", "kind": "review"},
    "LOCK_DIALOGUE": {"scope": "project", "kind": "plan"},
    "VERIFY_FINAL_MASTER": {"scope": "project", "kind": "review"},
    "REVIEW_DELIVERY_PREFLIGHT": {"scope": "project", "kind": "review"},
}
DOMAIN_PRIORITY = ("PLAN", "WORLD", "PREVIS", "RENDERER", "REFERENCE", "VISUAL", "AUDIO", "EDIT", "DELIVERY")


_DEFAULT_BLOCKER_ACTIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "PREVIS_REVIEW_REQUIRED": (
        ("START_RENDER", "RENDER_SHOT", "START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"),
        ("APPROVE_PREVIS", "REPLAN_STORYBOARD"),
    ),
    "UNKNOWN_SCENE_ID": (("START_RENDER", "RENDER_SHOT"), ("REPLAN_STORY_WORLD",)),
    "UNKNOWN_CHARACTER_ID": (("START_RENDER", "RENDER_SHOT"), ("REPLAN_STORY_WORLD",)),
    "UNKNOWN_PROP_ID": (("START_RENDER", "RENDER_SHOT"), ("REPLAN_STORY_WORLD",)),
    "MISSING_CHARACTER_LOCK": (("START_RENDER", "RENDER_SHOT"), ("REVIEW_VISUAL_BIBLE",)),
    "MISSING_SCENE_LOCK": (("START_RENDER", "RENDER_SHOT"), ("REVIEW_VISUAL_BIBLE",)),
    "MISSING_PROP_LOCK": (("START_RENDER", "RENDER_SHOT"), ("REVIEW_VISUAL_BIBLE",)),
    "WORKFLOW_MISSING": (("START_RENDER", "RENDER_SHOT"), ("OPEN_RENDER_DIAGNOSTICS",)),
    "WORKFLOW_INVALID": (("START_RENDER", "RENDER_SHOT"), ("OPEN_RENDER_DIAGNOSTICS",)),
    "WORKFLOW_COMPILE_FAILED": (("START_RENDER", "RENDER_SHOT"), ("OPEN_RENDER_DIAGNOSTICS",)),
    "UNSUPPORTED_GENERATION_MODE": (("START_RENDER", "RENDER_SHOT"), ("REPLAN_STORYBOARD",)),
    "STALE": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("START_RENDER", "RENDER_SHOT")),
    "MANUAL_VISUAL_REVIEW": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("REVIEW_SHOT",)),
    "CHARACTER_DRIFT": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("REVIEW_SHOT",)),
    "SCENE_DRIFT": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("REVIEW_SHOT",)),
    "PROP_DRIFT": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("REVIEW_SHOT",)),
    "STYLE_DRIFT": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("REVIEW_SHOT",)),
    "SCRIPT_TIMING_REVIEW": (("APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("START_AI_EDIT", "REVIEW_AUDIO_TIMELINE")),
    "SPEECH_OVERFLOW": (("APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("START_AI_EDIT", "REVIEW_AUDIO_TIMELINE")),
    "VOICE_PROVIDER_REQUIRED": (("APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("START_AI_EDIT", "OPEN_SOUND")),
    "DIALOGUE_UNLOCKED": (("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("LOCK_DIALOGUE",)),
    "ROUGH_CUT_MISSING": (("APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT"), ("START_AI_EDIT",)),
    "FINAL_MASTER_MISSING": (("EXPORT",), ("GENERATE_FINAL_MASTER", "VERIFY_FINAL_MASTER")),
    "DELIVERY_PREFLIGHT_FAILED": (("EXPORT",), ("REVIEW_DELIVERY_PREFLIGHT",)),
}


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
        next_action=next_action,
        blocking_stage=blocking_stage or domain,
        metadata=dict(metadata or {}),
        blocks_actions=tuple(blocks_actions if blocks_actions is not None else default_blocks),
        resolves_by_actions=tuple(resolves_by_actions if resolves_by_actions is not None else default_resolves),
        applies_to_actions=tuple(applies_to_actions or ()),
    )


@dataclass(frozen=True)
class ProductionActionContext:
    action: str
    shot_number: int | None = None
    track_key: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", canonical_action(self.action))


def canonical_action(action: str) -> str:
    requested = str(action or "").upper()
    return LEGACY_ACTION_ALIASES.get(requested, requested)


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
                severity="BLOCKING" if required and video_mode == "comfyui" else "WARNING",
                shot_number=int(getattr(shot, "number", 0) or 0) or None,
                next_action="OPEN_REFERENCE_BANK",
                blocking_stage="RENDER",
                blocks_actions=("START_RENDER", "RENDER_SHOT") if required and video_mode == "comfyui" else (),
                applies_to_actions=("START_RENDER", "RENDER_SHOT"),
                resolves_by_actions=("OPEN_REFERENCE_BANK", "REVIEW_VISUAL_BIBLE"),
            ))
    return result


def production_blockers(project: Any, settings: Any = None) -> list[ProductionBlocker]:
    """Collect all known blockers from the persisted project truth."""

    blockers: list[ProductionBlocker] = []
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
            blockers.append(_blocker(code, "WORLD", f"Unknown {label} ID: {value}.", next_action="REPLAN_STORY_WORLD", blocking_stage="RENDER", metadata={"entity_id": value, "affected_shots": affected_shots(label, str(value))}))

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
    voice = (getattr(project, "audio_tracks", {}) or {}).get("voice", {})
    if isinstance(voice, dict) and voice.get("status") in {"AUDIO PENDING", "PROVIDER REQUIRED", "VOICE_PROVIDER_REQUIRED"}:
        # Mock projects intentionally have no real voice renderer.  Keep that
        # fact visible as a warning, while real-provider projects treat it as
        # a production gate.
        severity = "WARNING" if bool(_setting(settings, "mock_mode", False)) else "BLOCKING"
        blockers.append(_blocker("VOICE_PROVIDER_REQUIRED", "AUDIO", "A voice provider or real voice asset is required.", severity=severity, next_action="OPEN_SOUND", blocking_stage="EDIT", applies_to_actions=("START_AI_EDIT", "APPROVE_FINAL_CUT", "GENERATE_FINAL_MASTER", "EXPORT")))

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


def production_readiness(project: Any, settings: Any = None) -> dict[str, Any]:
    """Return the one readiness contract used by API, diagnostics, and UI."""

    blockers = production_blockers(project, settings)
    storyboard = list(getattr(project, "storyboard", []) or [])
    blocking = [item for item in blockers if item.severity == "BLOCKING"]
    warnings = [item for item in blockers if item.severity == "WARNING"]
    global_blocking = [item for item in blocking if item.shot_number is None]
    next_action = next((item.next_action for item in blockers if item.next_action), None)
    state = describe_status(getattr(project, "status", "planning_live"))
    actions = {
        action: _action_readiness_from_blockers(blockers, action)
        for action in ACTION_ORDER
    }
    shot_actions = {
        str(int(getattr(shot, "number", 0) or 0)): {
            "RENDER_SHOT": _action_readiness_from_blockers(blockers, "RENDER_SHOT", shot_number=int(getattr(shot, "number", 0) or 0)),
            "REPLAN_SHOT": _action_readiness_from_blockers(blockers, "REPLAN_SHOT", shot_number=int(getattr(shot, "number", 0) or 0)),
        }
        for shot in storyboard
        if int(getattr(shot, "number", 0) or 0)
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
    }


def _action_readiness_from_blockers(
    blockers: list[ProductionBlocker],
    action: str,
    *,
    shot_number: int | None = None,
    track_key: str | None = None,
) -> dict[str, Any]:
    del track_key  # Reserved for audio-scoped actions in the next contract phase.
    action = canonical_action(action)
    blocking = [item for item in blockers if _blocker_matches_context(item, action, shot_number, blocking=True)]
    warnings = [item for item in blockers if _blocker_matches_context(item, action, shot_number, blocking=False)]
    resolution_actions = list(dict.fromkeys(
        action_name
        for item in blocking
        for action_name in item.resolves_by_actions
    ))
    return {
        "action": action,
        "ready": not blocking,
        "blockers": [item.to_dict() for item in blocking],
        "warnings": [item.to_dict() for item in warnings],
        "resolution_actions": resolution_actions,
        "blocking_count": len(blocking),
    }


def action_blockers(project: Any, settings: Any, action: str, *, shot_number: int | None = None, track_key: str | None = None) -> list[ProductionBlocker]:
    """Return blockers that explicitly declare this action unsafe."""

    action = canonical_action(action)
    shot_number = _validate_shot_number(project, shot_number) if shot_number is not None else None
    del track_key
    return [
        item
        for item in production_blockers(project, settings)
        if _blocker_matches_context(item, action, shot_number, blocking=True)
    ]


def _blocker_matches_context(
    item: ProductionBlocker,
    action: str,
    shot_number: int | None,
    *,
    blocking: bool,
) -> bool:
    action = canonical_action(action)
    if item.severity == "BLOCKING" and not blocking:
        return False
    if item.severity != "BLOCKING" and blocking:
        return False
    affected = item.metadata.get("affected_shots") if isinstance(item.metadata, dict) else None
    if shot_number is not None:
        if item.shot_number is not None and item.shot_number != shot_number:
            return False
        if affected and shot_number not in {int(value) for value in affected}:
            return False
    if item.shot_number is not None and shot_number is None and action in {"RENDER_SHOT", "REPLAN_SHOT"}:
        return False
    if blocking:
        return action in {canonical_action(value) for value in item.blocks_actions}
    applies = item.applies_to_actions
    return bool(applies) and action in {canonical_action(value) for value in applies}


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


def action_blockers_for_context(project: Any, settings: Any, context: ProductionActionContext) -> list[ProductionBlocker]:
    blockers = production_blockers(project, settings)
    return [item for item in blockers if _blocker_matches_context(item, context.action, context.shot_number, blocking=True)]


def action_readiness(project: Any, settings: Any, action: str, *, shot_number: int | None = None, track_key: str | None = None) -> dict[str, Any]:
    shot_number = _validate_shot_number(project, shot_number) if shot_number is not None else None
    blockers = production_blockers(project, settings)
    return _action_readiness_from_blockers(blockers, action, shot_number=shot_number, track_key=track_key)


def ensure_action_ready(project: Any, settings: Any, action: str, *, shot_number: int | None = None, track_key: str | None = None) -> None:
    canonical = canonical_action(action)
    shot_number = _validate_shot_number(project, shot_number) if shot_number is not None else None
    context = ProductionActionContext(canonical, shot_number=shot_number, track_key=track_key)
    blockers = action_blockers_for_context(project, settings, context)
    if blockers:
        raise ProductionBlockedError(canonical, blockers, shot_number=shot_number, track_key=track_key)


__all__ = [
    "ACTION_ORDER",
    "PRODUCTION_ACTIONS",
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
