"""Explainable storyboard quality checks used before visual generation."""

from __future__ import annotations

import re
from typing import Any, Iterable

from movie_agent.services.narrative import validate_beat_shot_mapping


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into", "is", "of", "on", "or",
    "the", "to", "with", "this", "that", "same", "shot", "previous", "next",
}

PLANNING_RELEVANCE_FLAGS = {
    "LOW_RELEVANCE_SHOT",
    "REDUNDANT_SHOT",
    "REPEATED_INFORMATION",
    "SHOT_TOO_COMPLEX",
    "NARRATIVE_STATE_DRIFT",
    "BEAT_MAPPING_REVIEW",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _tokens(value: Any) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]+", _text(value))
        if token.lower() not in _STOPWORDS and len(token) > 1
    }


def previous_ending_connects_to_next_starting_state(previous: Any, current: Any) -> bool:
    """Return whether the next shot acknowledges the prior ending state."""

    previous_text = _text(getattr(previous, "ending_state", "") or getattr(previous, "continuity_to", ""))
    current_text = _text(getattr(current, "starting_state", "") or getattr(current, "continuity_from", ""))
    if not previous_text or not current_text:
        return True
    previous_tokens = _tokens(previous_text)
    current_tokens = _tokens(current_text)
    if not previous_tokens or not current_tokens:
        return True
    if previous_tokens & current_tokens:
        return True
    stems = {token[: max(3, len(token) - 2)] for token in previous_tokens}
    return any(token[: max(3, len(token) - 2)] in stems for token in current_tokens)


def _similarity(left: Any, right: Any) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def _metric(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


class StoryboardRelevanceGate:
    """Score narrative contribution and annotate review flags.

    The gate is intentionally advisory: it marks shots for review but never
    silently removes editorial material.
    """

    def __init__(self, review_threshold: float = 0.45) -> None:
        self.review_threshold = review_threshold

    def evaluate(self, shot: Any, beat: dict[str, Any] | None = None, previous_shot: Any | None = None) -> dict[str, Any]:
        beat = beat or {}
        story_function = _text(
            getattr(shot, "story_function", "")
            or getattr(shot, "narrative_purpose", "")
            or beat.get("story_function")
            or beat.get("narrative_purpose")
        )
        action = _text(getattr(shot, "main_action", "") or getattr(shot, "action", ""))
        raw_gain = getattr(shot, "information_gain", None)
        if raw_gain is None:
            raw_gain = beat.get("information_gain")
        if raw_gain is None:
            raw_gain = 0.0
        try:
            information_score = _metric(float(raw_gain))
        except (TypeError, ValueError):
            information_score = 0.35
        metrics = {
            "narrative_contribution": _metric(0.8 if story_function and action else 0.2),
            "information_gain": information_score,
            "character_progression": _metric(0.75 if getattr(shot, "character_ids", None) or _text(getattr(shot, "character_reaction", "")) else 0.35),
            "emotional_progression": _metric(0.8 if (story_function or action) and (_text(getattr(shot, "emotional_shift", "")) or _text(getattr(shot, "character_reaction", ""))) else 0.3),
            "continuity_strength": _metric(1.0 if previous_shot is None or previous_ending_connects_to_next_starting_state(previous_shot, shot) else 0.15),
            "visual_necessity": _metric(0.8 if _text(getattr(shot, "visual_motif", "")) or _text(getattr(shot, "image_description", "")) else 0.25),
        }
        overall = _metric(sum(metrics.values()) / len(metrics))
        flags: list[str] = []
        necessary_atmosphere = story_function.upper() in {"ATMOSPHERE", "RHYTHM", "FORESHADOW"}
        if overall < self.review_threshold and not necessary_atmosphere:
            flags.append("LOW_RELEVANCE_SHOT")
        if previous_shot is not None:
            previous_content = " ".join(_text(getattr(previous_shot, key, "")) for key in ("image_description", "action", "main_action", "story_function"))
            current_content = " ".join(_text(getattr(shot, key, "")) for key in ("image_description", "action", "main_action", "story_function"))
            similarity = _similarity(previous_content, current_content)
            metrics["repetition_similarity"] = _metric(similarity)
            if similarity >= 0.72:
                flags.extend(["REDUNDANT_SHOT", "REPEATED_INFORMATION"])
        complexity = _text(getattr(shot, "shot_complexity", "")).upper()
        if complexity == "HIGH" or len(re.findall(r"[,;]|\band\b|\bthen\b", action, flags=re.IGNORECASE)) >= 4:
            flags.append("SHOT_TOO_COMPLEX")
        if previous_shot is not None and metrics["continuity_strength"] < 0.5:
            flags.append("NARRATIVE_STATE_DRIFT")
        return {
            "metrics": metrics,
            "overall": overall,
            "threshold": self.review_threshold,
            "flags": list(dict.fromkeys(flags)),
            "decision": "REVIEW" if flags else "PASS",
            "atmosphere_exception": necessary_atmosphere,
        }

    def annotate(self, shots: list[Any], beats: Iterable[dict[str, Any]] | None = None) -> list[Any]:
        beat_by_id: dict[str, dict[str, Any]] = {}
        for index, beat in enumerate(beats or []):
            beat_id = str(beat.get("beat_id") or beat.get("id") or beat.get("beat_number") or f"beat-{index + 1:02d}")
            beat_by_id[beat_id] = beat
        previous = None
        for shot in shots:
            result = self.evaluate(shot, beat_by_id.get(_text(getattr(shot, "beat_id", ""))), previous)
            details = dict(getattr(shot, "qc_details", {}) or {})
            planning = dict(details.get("planning") or {})
            planning["relevance"] = result
            mapping = planning.get("beat_mapping") or {}
            current_flags = list(result["flags"])
            if mapping and not mapping.get("valid", True):
                current_flags.append("BEAT_MAPPING_REVIEW")
            planning["flags"] = list(dict.fromkeys(current_flags))
            details["planning"] = planning
            # Keep the old top-level key for saved-project/API compatibility.
            details["relevance"] = result
            shot.qc_details = details
            external_flags = [
                str(flag) for flag in (shot.qc_flags or []) if str(flag) not in PLANNING_RELEVANCE_FLAGS
            ]
            for namespace in ("media", "visual", "manual_review"):
                namespace_value = details.get(namespace) or {}
                if isinstance(namespace_value, dict):
                    external_flags.extend(str(flag) for flag in (namespace_value.get("flags") or []))
            shot.qc_flags = list(dict.fromkeys([*external_flags, *current_flags]))
            previous = shot
        return shots

    def review_storyboard(self, shots: Iterable[Any], beats: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Review one complete board and return an explainable planning summary."""

        shot_list = list(shots)
        beat_list = list(beats or [])
        beat_mapping = validate_beat_shot_mapping(shot_list, beat_list)
        low_relevance: list[int] = []
        complex_shots: list[int] = []
        continuity_warnings: list[int] = []
        redundant_pairs: list[list[int]] = []
        repeated_information: list[list[int]] = []
        transition_scores: list[float] = []
        previous = None
        for shot in shot_list:
            result = self.evaluate(shot, None, previous)
            number = int(getattr(shot, "number", len(low_relevance) + 1))
            flags = set(result["flags"])
            if "LOW_RELEVANCE_SHOT" in flags:
                low_relevance.append(number)
            if "SHOT_TOO_COMPLEX" in flags:
                complex_shots.append(number)
            if "NARRATIVE_STATE_DRIFT" in flags:
                continuity_warnings.append(number)
            if previous is not None and "REDUNDANT_SHOT" in flags:
                pair = [int(getattr(previous, "number", number - 1)), number]
                redundant_pairs.append(pair)
            if previous is not None and "REPEATED_INFORMATION" in flags:
                repeated_information.append([int(getattr(previous, "number", number - 1)), number])
            transition_scores.append(float(result["metrics"].get("continuity_strength", 0.0)))
            previous = shot
        issues = bool(
            low_relevance or complex_shots or continuity_warnings or redundant_pairs
            or repeated_information or beat_mapping["uncovered_beats"] or beat_mapping["orphan_shots"]
        )
        return {
            "beat_coverage": beat_mapping["coverage_ratio"],
            "beat_mapping": beat_mapping,
            "low_relevance_shots": low_relevance,
            "redundant_pairs": redundant_pairs,
            "repeated_information": repeated_information,
            "complex_shots": complex_shots,
            "continuity_warnings": continuity_warnings,
            "transition_strength": round(sum(transition_scores) / max(1, len(transition_scores)), 3),
            "overall_storyboard_health": "REVIEW" if issues else "PASS",
            "decision": "REVIEW" if issues else "PASS",
        }


def review_storyboard(shots: Iterable[Any], beats: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    return StoryboardRelevanceGate().review_storyboard(shots, beats)


__all__ = ["PLANNING_RELEVANCE_FLAGS", "StoryboardRelevanceGate", "previous_ending_connects_to_next_starting_state", "review_storyboard"]
