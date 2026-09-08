"""Incremental pipeline services used by :class:`MovieOrchestrator`.

The application still uses one JSON-backed orchestrator for the competition
runtime.  This package provides small, dependency-free seams so planning,
rendering, editing and state contracts can be moved independently over time.
"""

from .editing import EditPipeline, edit_output_exists, editing_snapshot
from .diagnostics import delivery_preflight, diagnostics_snapshot
from .jobs import JobAlreadyRunning, JobIdempotencyConflict, JobLedger
from .planning import PlanningPipeline, planning_snapshot
from .rendering import RenderPipeline, shot_render_context
from movie_agent.services.readiness import (
    PRODUCTION_ACTIONS,
    PRODUCTION_ACTION_CONTRACT,
    ProductionActionContext,
    ProductionBlocker,
    ProductionBlockedError,
    action_readiness,
    production_blockers,
    production_readiness,
)
from movie_agent.services.production_contract import (
    ACTION_SPECS,
    ActionSpec,
    ProductionAction,
    ProductionState,
    TransitionResult,
    action_spec,
    transition_for,
)

__all__ = [
    "edit_output_exists",
    "editing_snapshot",
    "EditPipeline",
    "delivery_preflight",
    "diagnostics_snapshot",
    "JobAlreadyRunning",
    "JobIdempotencyConflict",
    "JobLedger",
    "planning_snapshot",
    "PlanningPipeline",
    "RenderPipeline",
    "shot_render_context",
    "ProductionBlocker",
    "ProductionActionContext",
    "PRODUCTION_ACTIONS",
    "PRODUCTION_ACTION_CONTRACT",
    "ProductionBlockedError",
    "action_readiness",
    "production_blockers",
    "production_readiness",
    "ActionSpec",
    "ACTION_SPECS",
    "ProductionAction",
    "ProductionState",
    "TransitionResult",
    "action_spec",
    "transition_for",
]
