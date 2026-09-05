"""Canonical project state and production-stage mapping.

The persisted ``MovieProject.status`` values are kept for backwards
compatibility with existing project JSON and API clients.  This module gives
those values one authoritative interpretation so the UI and orchestration
code do not need to invent their own stage semantics.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ProjectState(str, Enum):
    PLANNING = "planning"
    PREVIS_READY = "previs_ready"
    RENDER_READY = "render_ready"
    RENDERING = "rendering"
    SHOTS_READY = "shots_ready"
    EDITING = "editing"
    ROUGH_CUT_READY = "rough_cut_ready"
    FINAL_READY = "final_ready"
    EXPORTED = "exported"
    FAILED = "failed"
    ARCHIVED = "archived"


STATUS_TO_STATE: dict[str, ProjectState] = {
    "planning_live": ProjectState.PLANNING,
    "planned_mock": ProjectState.PREVIS_READY,
    "planned_text_ai": ProjectState.PREVIS_READY,
    "ready_for_comfyui_render": ProjectState.RENDER_READY,
    "generating_video_mock": ProjectState.RENDERING,
    "rendering_comfyui": ProjectState.RENDERING,
    "awaiting_visual_review": ProjectState.RENDERING,
    "ready_for_ai_edit": ProjectState.SHOTS_READY,
    "editing_rough_cut": ProjectState.EDITING,
    "rough_cut_ready": ProjectState.ROUGH_CUT_READY,
    "editing_final": ProjectState.EDITING,
    "completed_mock": ProjectState.FINAL_READY,
    "completed_text_ai_video_mock": ProjectState.FINAL_READY,
    "completed_comfyui": ProjectState.FINAL_READY,
    "exported": ProjectState.EXPORTED,
    "render_failed": ProjectState.FAILED,
    "failed": ProjectState.FAILED,
    "archived": ProjectState.ARCHIVED,
}

STATE_TO_STAGE: dict[ProjectState, str] = {
    ProjectState.PLANNING: "PLAN",
    ProjectState.PREVIS_READY: "PREVIS",
    ProjectState.RENDER_READY: "RENDER",
    ProjectState.RENDERING: "RENDER",
    ProjectState.SHOTS_READY: "DELIVER",
    ProjectState.EDITING: "DELIVER",
    ProjectState.ROUGH_CUT_READY: "DELIVER",
    ProjectState.FINAL_READY: "DELIVER",
    ProjectState.EXPORTED: "DELIVER",
    ProjectState.FAILED: "RENDER",
    ProjectState.ARCHIVED: "DELIVER",
}


def _pipeline_for_state(state: ProjectState) -> dict[str, str]:
    """Map the canonical state to the four visible production stages."""

    pipeline = {"plan": "todo", "previs": "todo", "render": "todo", "deliver": "todo"}
    if state is ProjectState.PLANNING:
        pipeline["plan"] = "active"
    elif state is ProjectState.PREVIS_READY:
        pipeline.update(plan="done", previs="ready")
    elif state is ProjectState.RENDER_READY:
        pipeline.update(plan="done", previs="done", render="ready")
    elif state in {ProjectState.RENDERING, ProjectState.FAILED}:
        pipeline.update(plan="done", previs="done", render="active")
    elif state is ProjectState.SHOTS_READY:
        pipeline.update(plan="done", previs="done", render="done", deliver="active")
    elif state in {ProjectState.EDITING, ProjectState.ROUGH_CUT_READY, ProjectState.FINAL_READY}:
        pipeline.update(plan="done", previs="done", render="done", deliver="ready")
    elif state is ProjectState.EXPORTED:
        pipeline.update(plan="done", previs="done", render="done", deliver="done")
    elif state is ProjectState.ARCHIVED:
        pipeline.update(plan="done", previs="done", render="done", deliver="archived")
    return pipeline


def state_for_status(status: str | None) -> ProjectState:
    """Resolve a legacy persisted status to its canonical state."""

    value = str(status or "").strip().lower()
    if value in STATUS_TO_STATE:
        return STATUS_TO_STATE[value]
    if value.startswith("completed"):
        return ProjectState.FINAL_READY
    if value.startswith("render") or value.startswith("generat"):
        return ProjectState.RENDERING
    if value.startswith("editing"):
        return ProjectState.EDITING
    if value.startswith("planned"):
        return ProjectState.PREVIS_READY
    return ProjectState.PLANNING


def describe_status(status: str | None) -> dict[str, Any]:
    """Return a JSON-safe state descriptor for API/UI consumers."""

    state = state_for_status(status)
    stage = STATE_TO_STAGE[state]
    return {
        "status": str(status or "planning_live"),
        "state": state.value,
        "stage": stage,
        "archived": state is ProjectState.ARCHIVED,
        "terminal": state in {ProjectState.FINAL_READY, ProjectState.EXPORTED, ProjectState.ARCHIVED},
        "review_required": str(status or "").strip().lower() == "awaiting_visual_review",
        "next_action": "APPROVE_SHOT" if str(status or "").strip().lower() == "awaiting_visual_review" else None,
        "pipeline": _pipeline_for_state(state),
        "labels": {
            "state": state.value.replace("_", " ").upper(),
            "stage": stage,
        },
    }


def set_status(project: Any, status: str | ProjectState) -> str:
    """Assign a persisted status while returning its canonical string.

    ``ProjectState`` values are accepted for new orchestration code; legacy
    string values remain valid so existing clients and saved projects are not
    broken during the incremental migration.
    """

    value = status.value if isinstance(status, ProjectState) else str(status)
    project.status = value
    return value
