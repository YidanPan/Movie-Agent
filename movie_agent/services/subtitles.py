"""Dialogue and subtitle assets shared by writing, editing, and delivery.

The writer owns the canonical dialogue book.  The subtitle track is a timed
projection of that book and is intentionally kept as plain JSON so it can be
reviewed, edited, locked, and exported without requiring a media tool.
"""

from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any, Iterable


SUBTITLE_MODES = {"none", "soft", "burned"}
_DEFAULT_SPEAKER = "旁白"


def shot_count_for_duration(duration_seconds: int) -> int:
    """Return the 6–10 shot count used by the storyboard planner."""

    return max(6, min(10, math.ceil(max(30, int(duration_seconds)) / 8)))


def allocate_durations(duration_seconds: int, shot_count: int) -> list[int]:
    """Distribute a target duration across 4–8 second subtitle slots."""

    count = max(1, int(shot_count))
    target = max(4 * count, min(8 * count, int(duration_seconds)))
    base, remainder = divmod(target, count)
    durations = [base + (1 if index < remainder else 0) for index in range(count)]
    # The supported project range and shot count make this a defensive guard,
    # but retaining the bounds keeps this helper safe for API callers too.
    for index, duration in enumerate(durations):
        durations[index] = max(4, min(8, duration))
    drift = int(duration_seconds) - sum(durations)
    index = 0
    while drift and durations:
        slot = index % len(durations)
        if drift > 0 and durations[slot] < 8:
            durations[slot] += 1
            drift -= 1
        elif drift < 0 and durations[slot] > 4:
            durations[slot] -= 1
            drift += 1
        index += 1
        if index > len(durations) * 20:
            break
    return durations


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return "；".join(part for part in (_text(item) for item in value) if part)
    if isinstance(value, dict):
        return "；".join(part for part in (_text(item) for item in value.values()) if part)
    return str(value).strip()


def _split_for_shots(text: str, count: int) -> list[str]:
    """Split Chinese prose into short readable lines without losing content."""

    clean = re.sub(r"\s+", "", text or "")
    if not clean:
        return []
    sentences = [part.strip() for part in re.split(r"(?<=[。！？；])", clean) if part.strip()]
    if len(sentences) >= count:
        return sentences[:count]
    # Evenly slice longer prose when the model gives one long narration line.
    width = max(1, math.ceil(len(clean) / count))
    chunks = [clean[index : index + width] for index in range(0, len(clean), width)]
    if len(chunks) >= count:
        return chunks[:count]
    return sentences or [clean]


def _entry_text(entry: Any) -> str:
    if isinstance(entry, dict):
        return _text(entry.get("text") or entry.get("dialogue") or entry.get("line") or entry.get("content"))
    return _text(entry)


def _raw_entries(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return list(value.values())
    if value:
        return [value]
    return []


def _seconds(value: Any, default: float) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


def _normalise_entries(value: Any, count: int, durations: list[int], fallback_text: str) -> list[dict[str, Any]]:
    raw = _raw_entries(value)
    fallback = _split_for_shots(fallback_text, count)
    entries: list[dict[str, Any]] = []
    cursor = 0.0
    for index in range(count):
        item = raw[index] if index < len(raw) else {}
        if isinstance(item, str):
            item = {"text": item}
        if not isinstance(item, dict):
            item = {}
        text = _entry_text(item) or (fallback[index] if index < len(fallback) else "")
        if not text:
            text = "（留白）"
        start = _seconds(item.get("start_seconds", item.get("start")), cursor)
        end_default = cursor + durations[index]
        end = _seconds(item.get("end_seconds", item.get("end")), end_default)
        if end <= start:
            end = end_default
        entries.append(
            {
                "line_id": str(item.get("line_id") or f"L{index + 1:02d}"),
                "shot": int(item.get("shot") or item.get("shot_number") or index + 1),
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "speaker": _text(item.get("speaker")) or _DEFAULT_SPEAKER,
                "kind": _text(item.get("kind")) or "narration",
                "text": text,
            }
        )
        cursor = end_default
    return entries


def normalise_subtitle_mode(value: Any) -> str:
    aliases = {"burn": "burned", "burn-in": "burned", "烧录": "burned", "软字幕": "soft", "无字幕": "none"}
    mode = aliases.get(str(value or "").strip().lower(), str(value or "").strip().lower())
    return mode if mode in SUBTITLE_MODES else "burned"


def build_dialogue_assets(
    narration: str,
    story: str = "",
    *,
    duration_seconds: int = 48,
    shot_count: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Create one editable dialogue line and one subtitle cue per planned shot."""

    count = shot_count or shot_count_for_duration(duration_seconds)
    durations = allocate_durations(duration_seconds, count)
    source = _text(narration) or _text(story)
    dialogue = _normalise_entries(None, count, durations, source)
    subtitle = deepcopy(dialogue)
    return dialogue, subtitle


def ensure_dialogue_assets(
    script: dict[str, Any] | None,
    *,
    duration_seconds: int = 48,
    shot_count: int | None = None,
) -> dict[str, Any]:
    """Return a backwards-compatible script containing canonical timed assets."""

    result: dict[str, Any] = deepcopy(script or {})
    count = shot_count or shot_count_for_duration(duration_seconds)
    durations = allocate_durations(duration_seconds, count)
    dialogue_source = _text(result.get("narration")) or _text(result.get("story"))
    dialogue = _normalise_entries(result.get("dialogue_book"), count, durations, dialogue_source)
    subtitle = _normalise_entries(result.get("subtitle_track"), count, durations, dialogue_source)
    # Subtitle cues should follow the editable dialogue text by default.  A
    # separately edited track is still preserved when it contains different
    # text or timing.
    if not result.get("subtitle_track"):
        subtitle = deepcopy(dialogue)
    result["dialogue_book"] = dialogue
    result["subtitle_track"] = subtitle
    result["dialogue_locked"] = bool(result.get("dialogue_locked", False))
    result["subtitle_mode"] = normalise_subtitle_mode(result.get("subtitle_mode", "burned"))
    result["dialogue_revision"] = int(result.get("dialogue_revision", 1) or 1)
    return result


def align_script_to_shots(script: dict[str, Any], storyboard: Iterable[Any]) -> dict[str, Any]:
    """Align cue timing to the actual storyboard durations after planning."""

    result = ensure_dialogue_assets(script)
    shots = list(storyboard)
    if not shots:
        return result
    dialogue = list(result.get("dialogue_book") or [])
    subtitle = list(result.get("subtitle_track") or [])
    cursor = 0.0
    for index, shot in enumerate(shots):
        if isinstance(shot, dict):
            number = int(shot.get("number", index + 1))
            duration = float(shot.get("duration_seconds", 4))
        else:
            number = int(getattr(shot, "number", index + 1))
            duration = float(getattr(shot, "duration_seconds", 4))
        for entries in (dialogue, subtitle):
            if index >= len(entries):
                entries.append({"line_id": f"L{index + 1:02d}", "speaker": _DEFAULT_SPEAKER, "kind": "narration", "text": "（留白）"})
            entry = entries[index]
            entry["shot"] = number
            entry["start_seconds"] = round(cursor, 3)
            entry["end_seconds"] = round(cursor + duration, 3)
            entry.setdefault("line_id", f"L{index + 1:02d}")
            entry.setdefault("speaker", _DEFAULT_SPEAKER)
            entry.setdefault("kind", "narration")
            entry["text"] = _entry_text(entry) or "（留白）"
        cursor += duration
    result["dialogue_book"] = dialogue[: len(shots)]
    result["subtitle_track"] = subtitle[: len(shots)]
    return result


def _timestamp(seconds: Any, separator: str) -> str:
    total_ms = max(0, int(round(float(seconds or 0) * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def render_srt(entries: Iterable[dict[str, Any]]) -> str:
    rows = []
    for index, entry in enumerate(entries, start=1):
        text = _entry_text(entry) or "（留白）"
        rows.append(
            f"{index}\n{_timestamp(entry.get('start_seconds'), ',')} --> {_timestamp(entry.get('end_seconds'), ',')}\n{text}\n"
        )
    return "\n".join(rows).rstrip() + ("\n" if rows else "")


def render_vtt(entries: Iterable[dict[str, Any]]) -> str:
    rows = ["WEBVTT", ""]
    for index, entry in enumerate(entries, start=1):
        text = _entry_text(entry) or "（留白）"
        rows.extend(
            [
                str(index),
                f"{_timestamp(entry.get('start_seconds'), '.')} --> {_timestamp(entry.get('end_seconds'), '.')}",
                text,
                "",
            ]
        )
    return "\n".join(rows)


def script_subtitle_track(script: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list((script or {}).get("subtitle_track") or (script or {}).get("dialogue_book") or [])
