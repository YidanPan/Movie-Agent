"""Canonical production states and action specifications.

The persisted project status remains backwards compatible.  This module is
the single semantic source for new code: readiness, API guards and clients
consume the same action metadata instead of rebuilding stage rules locally.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from movie_agent.state import ProjectState, state_for_status


class ProductionAction(str, Enum):
    START_RENDER = "START_RENDER"
    RENDER_SHOT = "RENDER_SHOT"
    REPLAN_SHOT = "REPLAN_SHOT"
    START_AI_EDIT = "START_AI_EDIT"
    APPROVE_PREVIS = "APPROVE_PREVIS"
    APPROVE_SHOT = "APPROVE_SHOT"
    APPROVE_FINAL_CUT = "APPROVE_FINAL_CUT"
    GENERATE_FINAL_MASTER = "GENERATE_FINAL_MASTER"
    VERIFY_FINAL_MASTER = "VERIFY_FINAL_MASTER"
    REPLAN_AUDIO_TRACK = "REPLAN_AUDIO_TRACK"
    RENDER_AUDIO_TRACK = "RENDER_AUDIO_TRACK"
    APPLY_FINAL_LOOK = "APPLY_FINAL_LOOK"
    EXPORT = "EXPORT"
    EXPORT_FILM = "EXPORT_FILM"
    REVIEW_STORYBOARD = "REVIEW_STORYBOARD"
    REVIEW_STORY_WORLD = "REVIEW_STORY_WORLD"
    REVIEW_VISUAL_BIBLE = "REVIEW_VISUAL_BIBLE"
    OPEN_REFERENCE_BANK = "OPEN_REFERENCE_BANK"
    REVIEW_SHOT = "REVIEW_SHOT"
    REVIEW_AUDIO_TIMELINE = "REVIEW_AUDIO_TIMELINE"
    OPEN_SOUND = "OPEN_SOUND"
    OPEN_RENDER_DIAGNOSTICS = "OPEN_RENDER_DIAGNOSTICS"
    REVIEW_RENDER_DIAGNOSTICS = "REVIEW_RENDER_DIAGNOSTICS"
    LOCK_DIALOGUE = "LOCK_DIALOGUE"
    REVIEW_DELIVERY_PREFLIGHT = "REVIEW_DELIVERY_PREFLIGHT"
    REVIEW_AUDIO_TRACK = "REVIEW_AUDIO_TRACK"


class ProductionState(str, Enum):
    PLANNING = ProjectState.PLANNING.value
    PREVIS_READY = ProjectState.PREVIS_READY.value
    RENDER_READY = ProjectState.RENDER_READY.value
    RENDERING = ProjectState.RENDERING.value
    SHOTS_READY = ProjectState.SHOTS_READY.value
    EDITING = ProjectState.EDITING.value
    ROUGH_CUT_READY = ProjectState.ROUGH_CUT_READY.value
    FINAL_READY = ProjectState.FINAL_READY.value
    EXPORTED = ProjectState.EXPORTED.value
    FAILED = ProjectState.FAILED.value
    ARCHIVED = ProjectState.ARCHIVED.value


ALL_STATES = tuple(state.value for state in ProjectState)


@dataclass(frozen=True)
class TransitionResult:
    action: str
    current_state: str
    allowed: bool
    resulting_state: str | None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActionSpec:
    action: str
    scope: str
    kind: str
    label: str
    allowed_states: tuple[str, ...]
    required_conditions: tuple[str, ...] = ()
    blocker_codes: tuple[str, ...] = ()
    mutates_project: bool = False
    invalidation_effects: tuple[str, ...] = ()
    resulting_state: str | None = None
    idempotency_policy: str = "reject_active_same_project"
    requires_confirmation: bool = False
    confirmation_mode: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["allowed_states"] = list(self.allowed_states)
        payload["required_conditions"] = list(self.required_conditions)
        payload["blocker_codes"] = list(self.blocker_codes)
        payload["invalidation_effects"] = list(self.invalidation_effects)
        return payload


def _spec(
    action: ProductionAction | str,
    *,
    scope: str,
    kind: str,
    label: str,
    allowed_states: tuple[str, ...] = ALL_STATES,
    required_conditions: tuple[str, ...] = (),
    blocker_codes: tuple[str, ...] = (),
    mutates_project: bool = False,
    invalidation_effects: tuple[str, ...] = (),
    resulting_state: str | None = None,
    idempotency_policy: str = "reject_active_same_project",
    requires_confirmation: bool = False,
    confirmation_mode: str | None = None,
) -> ActionSpec:
    return ActionSpec(
        action=action.value if isinstance(action, ProductionAction) else str(action),
        scope=scope,
        kind=kind,
        label=label,
        allowed_states=allowed_states,
        required_conditions=required_conditions,
        blocker_codes=blocker_codes,
        mutates_project=mutates_project,
        invalidation_effects=invalidation_effects,
        resulting_state=resulting_state,
        idempotency_policy=idempotency_policy,
        requires_confirmation=requires_confirmation,
        confirmation_mode=confirmation_mode,
    )


ACTION_SPECS: dict[str, ActionSpec] = {
    "START_RENDER": _spec(
        ProductionAction.START_RENDER,
        scope="project", kind="execute", label="START RENDER",
        allowed_states=(ProductionState.PREVIS_READY.value, ProductionState.RENDER_READY.value, ProductionState.RENDERING.value, ProductionState.SHOTS_READY.value),
        required_conditions=("previs_approved", "renderer_contract_valid"),
        blocker_codes=("PREVIS_REVIEW_REQUIRED", "WORKFLOW_MISSING", "WORKFLOW_INVALID", "WORKFLOW_COMPILE_FAILED"),
        mutates_project=True, resulting_state=ProductionState.RENDERING.value,
    ),
    "RENDER_SHOT": _spec(
        ProductionAction.RENDER_SHOT,
        scope="shot", kind="execute", label="RENDER SHOT",
        allowed_states=(ProductionState.RENDER_READY.value, ProductionState.RENDERING.value, ProductionState.SHOTS_READY.value),
        required_conditions=("shot_reference_inputs_valid",),
        blocker_codes=("STALE", "MISSING_CHARACTER_LOCK", "MISSING_SCENE_LOCK", "MISSING_PROP_LOCK"),
        mutates_project=True, resulting_state=ProductionState.RENDERING.value,
    ),
    "REPLAN_SHOT": _spec(
        ProductionAction.REPLAN_SHOT,
        scope="shot", kind="plan", label="REPLAN SHOT",
        allowed_states=ALL_STATES, mutates_project=True,
        invalidation_effects=("shot_media", "downstream_edit",),
    ),
    "START_AI_EDIT": _spec(
        ProductionAction.START_AI_EDIT,
        scope="project", kind="execute", label="START AI EDIT",
        allowed_states=(ProductionState.SHOTS_READY.value, ProductionState.EDITING.value, ProductionState.ROUGH_CUT_READY.value, ProductionState.FINAL_READY.value),
        required_conditions=("all_shots_approved", "dialogue_locked",),
        blocker_codes=("MANUAL_VISUAL_REVIEW", "STALE", "DIALOGUE_UNLOCKED", "VOICE_PROVIDER_REQUIRED", "MUSIC_PROVIDER_REQUIRED"),
        mutates_project=True, resulting_state=ProductionState.EDITING.value,
    ),
    "APPROVE_PREVIS": _spec(
        ProductionAction.APPROVE_PREVIS,
        scope="project", kind="review", label="APPROVE PREVIS",
        allowed_states=(ProductionState.PREVIS_READY.value, ProductionState.RENDER_READY.value),
        required_conditions=("storyboard_review_passed",), mutates_project=True,
        resulting_state=ProductionState.RENDER_READY.value, requires_confirmation=True, confirmation_mode="inline",
    ),
    "APPROVE_SHOT": _spec(
        ProductionAction.APPROVE_SHOT,
        scope="shot", kind="review", label="APPROVE SHOT",
        allowed_states=(ProductionState.RENDERING.value, ProductionState.SHOTS_READY.value),
        required_conditions=("shot_media_present", "visual_review_complete"), mutates_project=True,
        resulting_state=ProductionState.SHOTS_READY.value,
    ),
    "APPROVE_FINAL_CUT": _spec(
        ProductionAction.APPROVE_FINAL_CUT,
        scope="project", kind="review", label="APPROVE FINAL CUT",
        allowed_states=(ProductionState.EDITING.value, ProductionState.ROUGH_CUT_READY.value),
        required_conditions=("rough_cut_present", "all_shots_approved", "dialogue_locked"),
        blocker_codes=("ROUGH_CUT_MISSING", "DIALOGUE_UNLOCKED", "MANUAL_VISUAL_REVIEW", "STALE"),
        mutates_project=True, resulting_state=ProductionState.EDITING.value,
        requires_confirmation=True, confirmation_mode="inline",
    ),
    "GENERATE_FINAL_MASTER": _spec(
        ProductionAction.GENERATE_FINAL_MASTER,
        scope="project", kind="execute", label="GENERATE FINAL MASTER",
        allowed_states=(ProductionState.EDITING.value, ProductionState.FINAL_READY.value),
        required_conditions=("final_cut_approved", "all_shots_approved", "dialogue_locked"),
        blocker_codes=("DIALOGUE_UNLOCKED", "MANUAL_VISUAL_REVIEW", "STALE", "VOICE_PROVIDER_REQUIRED", "MUSIC_PROVIDER_REQUIRED"),
        mutates_project=True, resulting_state=ProductionState.FINAL_READY.value,
    ),
    "VERIFY_FINAL_MASTER": _spec(
        ProductionAction.VERIFY_FINAL_MASTER,
        scope="project", kind="review", label="VERIFY MASTER",
        allowed_states=(ProductionState.EDITING.value, ProductionState.FINAL_READY.value, ProductionState.EXPORTED.value),
        required_conditions=("final_master_present",),
    ),
    "REPLAN_AUDIO_TRACK": _spec(
        ProductionAction.REPLAN_AUDIO_TRACK,
        scope="track", kind="plan", label="REPLAN TRACK", allowed_states=ALL_STATES,
        mutates_project=True, invalidation_effects=("audio_media", "edit_output",),
    ),
    "RENDER_AUDIO_TRACK": _spec(
        ProductionAction.RENDER_AUDIO_TRACK,
        scope="track", kind="execute", label="RENDER TRACK", allowed_states=ALL_STATES,
        required_conditions=("provider_available",), blocker_codes=("VOICE_PROVIDER_REQUIRED", "MUSIC_PROVIDER_REQUIRED"),
        mutates_project=True, resulting_state=ProductionState.EDITING.value,
    ),
    "APPLY_FINAL_LOOK": _spec(
        ProductionAction.APPLY_FINAL_LOOK,
        scope="project", kind="execute", label="APPLY FINAL LOOK",
        allowed_states=(ProductionState.FINAL_READY.value,), required_conditions=("final_master_present",),
        mutates_project=True, invalidation_effects=("final_master_verification",), resulting_state=ProductionState.FINAL_READY.value,
    ),
    "EXPORT": _spec(
        ProductionAction.EXPORT,
        scope="project", kind="execute", label="EXPORT",
        allowed_states=(ProductionState.FINAL_READY.value, ProductionState.EXPORTED.value),
        required_conditions=("final_master_verified",), blocker_codes=("FINAL_MASTER_MISSING", "DELIVERY_PREFLIGHT_FAILED"),
        idempotency_policy="same_key_returns_existing_operation", requires_confirmation=True, confirmation_mode="sheet",
    ),
    "REVIEW_STORYBOARD": _spec("REVIEW_STORYBOARD", scope="project", kind="review", label="REVIEW STORYBOARD"),
    "REVIEW_STORY_WORLD": _spec("REVIEW_STORY_WORLD", scope="project", kind="review", label="REVIEW STORY WORLD"),
    "REVIEW_VISUAL_BIBLE": _spec("REVIEW_VISUAL_BIBLE", scope="project", kind="review", label="OPEN VISUAL BIBLE"),
    "OPEN_REFERENCE_BANK": _spec("OPEN_REFERENCE_BANK", scope="project", kind="review", label="OPEN REFERENCES"),
    "REVIEW_SHOT": _spec("REVIEW_SHOT", scope="shot", kind="review", label="REVIEW SHOT"),
    "REVIEW_AUDIO_TIMELINE": _spec("REVIEW_AUDIO_TIMELINE", scope="project", kind="review", label="OPEN AUDIO"),
    "OPEN_SOUND": _spec("OPEN_SOUND", scope="project", kind="review", label="OPEN SOUND"),
    "OPEN_RENDER_DIAGNOSTICS": _spec("OPEN_RENDER_DIAGNOSTICS", scope="project", kind="review", label="OPEN RENDER"),
    "REVIEW_RENDER_DIAGNOSTICS": _spec("REVIEW_RENDER_DIAGNOSTICS", scope="project", kind="review", label="OPEN RENDER"),
    "LOCK_DIALOGUE": _spec("LOCK_DIALOGUE", scope="project", kind="plan", label="LOCK DIALOGUE", mutates_project=True),
    "REVIEW_DELIVERY_PREFLIGHT": _spec("REVIEW_DELIVERY_PREFLIGHT", scope="project", kind="review", label="REVIEW DELIVERY"),
    "REVIEW_AUDIO_TRACK": _spec("REVIEW_AUDIO_TRACK", scope="track", kind="review", label="REVIEW TRACK"),
}

# The values below are the only JSON-facing action catalog.
PRODUCTION_ACTIONS = {name: spec.to_dict() for name, spec in ACTION_SPECS.items()}
PRODUCTION_ACTION_CONTRACT = {"schema_version": 3, "actions": PRODUCTION_ACTIONS}
ACTION_CONTRACT_SCHEMA_VERSION = 3

LEGACY_ACTION_ALIASES = {
    "REGENERATE_SHOT": "RENDER_SHOT",
    "REGENERATE_AUDIO_TRACK": "REPLAN_AUDIO_TRACK",
    "REPLAN_STORYBOARD": "REVIEW_STORYBOARD",
    "REPLAN_STORY_WORLD": "REVIEW_STORY_WORLD",
    "EXPORT_FILM": "EXPORT",
}


def canonical_action(action: str | ProductionAction) -> str:
    requested = action.value if isinstance(action, ProductionAction) else str(action or "").upper()
    return LEGACY_ACTION_ALIASES.get(requested, requested)


def action_spec(action: str | ProductionAction) -> ActionSpec | None:
    return ACTION_SPECS.get(canonical_action(action))


def transition_for(status: str | None, action: str | ProductionAction) -> TransitionResult:
    canonical = canonical_action(action)
    spec = action_spec(canonical)
    current = state_for_status(status).value
    if spec is None:
        return TransitionResult(canonical, current, False, None, "unknown_action")
    allowed = current in spec.allowed_states
    return TransitionResult(
        canonical,
        current,
        allowed,
        spec.resulting_state if allowed else None,
        "" if allowed else f"{canonical} is not allowed from {current}",
    )


__all__ = [
    "ACTION_CONTRACT_SCHEMA_VERSION",
    "ACTION_SPECS",
    "ActionSpec",
    "LEGACY_ACTION_ALIASES",
    "PRODUCTION_ACTIONS",
    "PRODUCTION_ACTION_CONTRACT",
    "ProductionAction",
    "ProductionState",
    "TransitionResult",
    "action_spec",
    "canonical_action",
    "transition_for",
]
