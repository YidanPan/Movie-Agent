"""Incremental pipeline services used by :class:`MovieOrchestrator`.

The application still uses one JSON-backed orchestrator for the competition
runtime.  This package provides small, dependency-free seams so planning,
rendering, editing and state contracts can be moved independently over time.
"""

from .editing import edit_output_exists, editing_snapshot
from .planning import planning_snapshot
from .rendering import shot_render_context

__all__ = [
    "edit_output_exists",
    "editing_snapshot",
    "planning_snapshot",
    "shot_render_context",
]

