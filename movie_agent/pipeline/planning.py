"""Planning-stage read models.

These helpers intentionally return plain dictionaries.  They are safe to use
from an API, event callback, or future background worker without coupling the
planning agents to FastAPI.
"""

from __future__ import annotations

from typing import Any

from movie_agent.services.quality import ContinuityQualityGate, PlanningQualityGate, SemanticCopyrightReviewer


def planning_snapshot(project: Any) -> dict[str, Any]:
    """Summarise the planning outputs without exposing mutable internals."""

    storyboard = list(getattr(project, "storyboard", []) or [])
    return {
        "project_id": str(getattr(project, "project_id", "")),
        "idea": str(getattr(project, "idea", "")),
        "film_language": str(getattr(project, "film_language", "en") or "en"),
        "story_beats": len(getattr(project, "story_beats", []) or []),
        "shots": len(storyboard),
        "shot_revisions": [int(getattr(shot, "revision", 1) or 1) for shot in storyboard],
        "dialogue_locked": bool((getattr(project, "script", {}) or {}).get("dialogue_locked")),
    }


class PlanningPipeline:
    """Own the planning quality boundary used before a project is saved."""

    def __init__(
        self,
        quality_gate: PlanningQualityGate,
        continuity_gate: ContinuityQualityGate,
        copyright_reviewer: SemanticCopyrightReviewer,
    ) -> None:
        self.quality_gate = quality_gate
        self.continuity_gate = continuity_gate
        self.copyright_reviewer = copyright_reviewer

    def review(
        self,
        *,
        idea: str,
        duration_seconds: int,
        script: dict[str, Any],
        visual_bible: dict[str, Any],
        storyboard: list[Any],
        continuity_lock: dict[str, Any],
    ) -> list[str]:
        """Run all planning QC without making orchestration decisions."""

        report = self.quality_gate.review(
            duration_seconds=duration_seconds,
            script=script,
            visual_bible=visual_bible,
            storyboard=storyboard,
        )
        report.extend(self.copyright_reviewer.review(idea=idea, script=script, visual_bible=visual_bible, storyboard=storyboard))
        report.extend(
            self.continuity_gate.review(
                visual_bible=visual_bible,
                storyboard=storyboard,
                continuity_lock=continuity_lock,
            )
        )
        return report

