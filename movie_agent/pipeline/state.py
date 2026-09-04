"""Compatibility exports for the canonical project state machine."""

from movie_agent.state import (
    ProjectState,
    STATUS_TO_STATE,
    STATE_TO_STAGE,
    describe_status,
    set_status,
    state_for_status,
)

__all__ = [
    "ProjectState",
    "STATUS_TO_STATE",
    "STATE_TO_STAGE",
    "describe_status",
    "set_status",
    "state_for_status",
]

