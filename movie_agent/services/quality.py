"""Pre-render structural and semantic quality gates."""

from __future__ import annotations

from typing import Any

from movie_agent.models import Shot
from movie_agent.services.llm import CreativeLLM


class PlanningQualityGate:
    """Reject invalid plans early and record readable non-blocking review notes."""

    prohibited_references = ("Star Wars", "Marvel", "Harry Potter", "Lord of the Rings", "Matrix")

    def review(
        self,
        *,
        duration_seconds: int,
        script: dict[str, str],
        visual_bible: dict[str, str],
        storyboard: list[Shot],
    ) -> list[str]:
        errors: list[str] = []
        if not script.get("story") or not script.get("narration"):
            errors.append("Script or narration is empty.")
        if not {"character_card", "scene_card", "style_card"}.issubset(visual_bible):
            errors.append("Visual bible is missing character_card, scene_card, or style_card.")
        if not 6 <= len(storyboard) <= 10:
            errors.append("Shot count must be 6-10.")
        if any(not 4 <= shot.duration_seconds <= 8 for shot in storyboard):
            errors.append("Each shot duration must be 4-8 seconds.")
        if sum(shot.duration_seconds for shot in storyboard) != duration_seconds:
            errors.append("Total shot duration does not match target duration.")
        if any(len(shot.prompt.strip()) < 20 for shot in storyboard):
            errors.append("One or more final video prompts are too short.")
        combined_text = "\n".join(
            [script.get("story", ""), script.get("narration", "")]
            + [shot.image_description + shot.prompt for shot in storyboard]
        ).lower()
        if any(reference.lower() in combined_text for reference in self.prohibited_references):
            errors.append("Detected possible reference to existing film/TV IP.")
        if errors:
            raise ValueError("Quality gate failed: " + "; ".join(errors))
        return [
            "Quality Agent: Shot count, duration, and prompt completeness checks passed.",
            "Quality Agent: No preset film/TV IP references detected.",
            "Quality Agent: character_card, scene_card, and style_card are all present; ready for video generation queue.",
        ]


class ContinuityQualityGate:
    """Validate the whole-film handoff contract before media generation.

    This is intentionally structural in mock mode. When a vision model is
    available, :class:`ReviewerAgent` adds frame-level scores and drift flags.
    Keeping both layers means a malformed plan is blocked early while visual
    drift is still caught after rendering.
    """

    required_shot_fields = (
        "narrative_purpose",
        "starting_state",
        "main_action",
        "ending_state",
        "transition_hook",
    )
    drift_tokens = {
        "STYLE_DRIFT": ("different style", "new visual style", "style reset"),
        "CHARACTER_DRIFT": ("different character", "new costume", "new protagonist", "different outfit"),
        "SCENE_DRIFT": ("new location", "different location", "scene reset", "another environment"),
    }

    def review(
        self,
        *,
        visual_bible: dict[str, Any],
        storyboard: list[Shot],
        continuity_lock: dict[str, Any] | None = None,
    ) -> list[str]:
        errors: list[str] = []
        lock = continuity_lock or {}
        if lock.get("status") != "LOCKED":
            errors.append("Continuity lock is missing or not locked.")
        if not {"character_lock", "scene_lock", "cinematography_lock"}.issubset(visual_bible):
            errors.append("Visual continuity requires character, scene, and cinematography locks.")
        for shot in storyboard:
            missing = [field for field in self.required_shot_fields if not str(getattr(shot, field, "")).strip()]
            if missing:
                errors.append(f"Shot {shot.number} is missing continuity fields: {', '.join(missing)}.")
        if errors:
            raise ValueError("Continuity QC failed: " + "; ".join(errors))

        notes = [
            "Continuity QC: Visual Bible, Character Lock, Scene Lock, and Cinematography Lock are active.",
            "Continuity QC: Narrative state and transition hooks are present for every shot.",
            "Continuity QC: Generation prompts use a shared lock plus shot-level delta strategy.",
        ]
        for shot in storyboard:
            text = " ".join(
                str(getattr(shot, field, ""))
                for field in ("image_description", "action", "prompt")
            ).lower()
            for flag, tokens in self.drift_tokens.items():
                if any(token in text for token in tokens):
                    notes.append(f"{flag}: Shot {shot.number} contains a possible continuity drift; manual review required.")
        return notes


class SemanticCopyrightReviewer:
    """Use an opt-in LLM to detect lookalike references beyond fixed keywords."""

    def __init__(self, llm: CreativeLLM | None) -> None:
        self.llm = llm

    def review(
        self,
        *,
        idea: str,
        script: dict[str, str],
        visual_bible: dict[str, str],
        storyboard: list[Shot],
    ) -> list[str]:
        if self.llm is None:
            return ["Copyright review: No text review model configured; rule-based IP filter applied; manual review still recommended."]

        result = self.llm.complete_json(
            "You are a film copyright and originality reviewer. Identify substantial similarities to existing film/TV IP, characters, titles, iconic settings, dialogue, or shot language. "
            "Do not flag general sci-fi themes, common genre elements, or public domain material.",
            "Review the following original film proposal. Return only JSON: "
            '{"risk_level":"low|medium|high","reasons":["up to 3 reasons in English"],'
            '"rewrite_guidance":"actionable rewrite suggestion in English"}.\n'
            f"Original idea: {idea}\n"
            f"Script: {script.get('story', '')}\n"
            f"Narration: {script.get('narration', '')}\n"
            f"Visual bible: {'; '.join(f'{key}: {value}' for key, value in visual_bible.items())}\n"
            f"Storyboard: {'; '.join(f'{shot.number}. {shot.image_description} {shot.action}' for shot in storyboard)}",
        )
        risk_level = str(result.get("risk_level", "")).strip().lower()
        reasons = result.get("reasons", [])
        if not isinstance(reasons, list):
            reasons = [str(reasons)]
        reason_text = "; ".join(str(reason).strip() for reason in reasons if str(reason).strip())
        guidance = str(result.get("rewrite_guidance", "")).strip()
        if risk_level == "high":
            detail = reason_text or "High similarity risk to existing film/TV IP detected."
            raise ValueError(f"Copyright review failed: {detail} {guidance}".strip())
        if risk_level == "medium":
            return [f"Copyright review: Confusable similarity detected; rewrite recommended. {reason_text} {guidance}".strip()]
        if risk_level == "low":
            return ["Copyright review: No substantial similarity to existing film/TV IP found."]
        return ["Copyright review: Model did not return a valid risk level; rule-based check retained; manual review recommended."]
