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

from movie_agent.services.alignment import (
    PROPORTIONAL,
    SENTENCE_LEVEL,
    WORD_LEVEL,
    normalize_word_boundaries,
    sentence_level_cues,
    word_level_cues,
)


SUBTITLE_MODES = {"none", "soft", "burned"}
_DEFAULT_SPEAKER = "NARRATOR"


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
        return "; ".join(part for part in (_text(item) for item in value) if part)
    if isinstance(value, dict):
        return "; ".join(part for part in (_text(item) for item in value.values()) if part)
    return str(value).strip()


_MAX_LINE_CHARS = 42
_MAX_LINES_PER_CUE = 2

_PROTECTED_PREPOSITIONS = frozenset({
    "in", "on", "at", "to", "from", "with", "by", "for", "of",
    "about", "into", "through", "during", "before", "after",
    "above", "below", "between", "under", "over", "near",
})

_ARTICLES_AND_DETERMINERS = frozenset({
    "the", "a", "an", "this", "that", "these", "those",
    "my", "your", "his", "her", "its", "our", "their",
})

_AUXILIARIES = frozenset({
    "is", "are", "was", "were", "am", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "may", "might", "must", "can", "could",
})

_CLAUSE_CONJUNCTIONS = frozenset({
    "and", "but", "yet", "so", "or", "nor", "while", "although",
    "because", "since", "unless", "until", "though", "whereas",
})

_RELATIVE_PRONOUNS = frozenset({"who", "which", "that", "whom", "whose"})


def _split_for_shots(text: str, count: int) -> list[str]:
    """Split English prose into subtitle-friendly segments.

    Splits on sentence boundaries first, then at clause boundaries for long
    sentences, and finally merges or pads to hit the requested count.
    """

    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return []
    sentences = [part.strip() for part in re.split(r"(?<=[.!?;])\s+", clean) if part.strip()]
    segments: list[str] = []
    for sentence in sentences:
        if len(sentence) <= _MAX_LINE_CHARS * _MAX_LINES_PER_CUE:
            segments.append(sentence)
        else:
            segments.extend(_split_at_clauses(sentence))
    expanded: list[str] = []
    for segment in segments:
        expanded.extend(_split_long_text(segment))
    if len(expanded) >= count:
        return _merge_segments(expanded, count)
    return _pad_segments(expanded, count)


def _split_at_clauses(sentence: str) -> list[str]:
    """Break a long sentence at clause boundaries while keeping phrases intact."""

    parts = re.split(r"(?<=,)\s+|(?<=;)\s+", sentence)
    clauses: list[str] = []
    buffer = ""
    for part in parts:
        candidate = f"{buffer} {part}".strip() if buffer else part
        if len(candidate) > _MAX_LINE_CHARS * _MAX_LINES_PER_CUE and buffer:
            clauses.append(buffer.strip())
            buffer = part
        else:
            buffer = candidate
    if buffer.strip():
        remaining = buffer.strip()
        if len(remaining) > _MAX_LINE_CHARS * _MAX_LINES_PER_CUE:
            clauses.extend(_split_at_conjunctions(remaining))
        else:
            clauses.append(remaining)
    return [clause for clause in clauses if clause]


def _split_at_conjunctions(text: str) -> list[str]:
    """Split at coordinating conjunctions and relative pronouns as a last resort."""

    pattern = r"\s+(?=" + "|".join(
        sorted(_CLAUSE_CONJUNCTIONS | _RELATIVE_PRONOUNS, key=len, reverse=True)
    ) + r"\b)"
    parts = re.split(pattern, text, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def _merge_segments(segments: list[str], target: int) -> list[str]:
    """Merge excess segments into groups to hit the target count.

    Merges adjacent segments while keeping each group under the subtitle
    line-length budget.  If a merge would exceed the budget the segments
    stay separate and the target is treated as a soft guide.
    """

    if target <= 0:
        return segments
    count = max(1, target)
    if len(segments) <= count:
        return segments
    max_group_chars = _MAX_LINE_CHARS * _MAX_LINES_PER_CUE
    merged: list[str] = []
    buffer = ""
    for segment in segments:
        candidate = f"{buffer} {segment}".strip() if buffer else segment
        if buffer and len(candidate) > max_group_chars:
            merged.append(buffer.strip())
            buffer = segment
        else:
            buffer = candidate
    if buffer.strip():
        merged.append(buffer.strip())
    if len(merged) > count and len(merged) < len(segments):
        return _merge_segments(merged, count)
    return merged


def _pad_segments(segments: list[str], target: int) -> list[str]:
    """Pad a short segment list to the target count by splitting the longest entries."""

    result = list(segments)
    while len(result) < target:
        longest_index = max(range(len(result)), key=lambda i: len(result[i]))
        entry = result[longest_index]
        words = entry.split()
        if len(words) < 2:
            break
        mid = len(words) // 2
        split_at = _find_best_break(words, mid)
        if split_at <= 0 or split_at >= len(words):
            break
        result[longest_index] = " ".join(words[:split_at])
        result.insert(longest_index + 1, " ".join(words[split_at:]))
    return result[:target]


def _wrap_cue_text(text: str) -> str:
    """Wrap a subtitle cue into at most 2 lines of ~42 chars each.

    Never splits an article+noun, preposition+object, or auxiliary+verb pair.
    Returns the text unchanged if it already fits on one line.
    """

    clean = text.strip()
    if not clean or len(clean) <= _MAX_LINE_CHARS:
        return clean
    words = clean.split()
    if len(words) <= 1:
        return clean
    mid = len(words) // 2
    best_break = _find_best_break(words, mid)
    line1 = " ".join(words[:best_break])
    line2 = " ".join(words[best_break:])
    # A cue is never allowed to grow a third line.  Long text is split into
    # multiple timed cues by ``_render_entries`` before this wrapper is called;
    # this function therefore has one responsibility: format one cue as one
    # or two lines while preserving all of its words.
    return f"{line1}\n{line2}"


def _find_best_break(words: list[str], target: int, lo: int = 1) -> int:
    """Find the best word index to break at, near *target*, respecting protected pairs."""

    best = max(lo, min(target, len(words) - 1))
    for offset in range(len(words)):
        for candidate in (target + offset, target - offset):
            if candidate <= lo or candidate >= len(words):
                continue
            word = words[candidate].lower().rstrip(".,;:!?")
            prev_word = words[candidate - 1].lower().rstrip(".,;:!?")
            if prev_word in _ARTICLES_AND_DETERMINERS:
                continue
            if prev_word in _PROTECTED_PREPOSITIONS:
                continue
            if prev_word in _AUXILIARIES:
                continue
            return candidate
    return best


def _split_long_text(text: str, max_chars: int = _MAX_LINE_CHARS * _MAX_LINES_PER_CUE) -> list[str]:
    """Split an overlong subtitle into natural, two-line-sized cue chunks.

    The old implementation attempted to keep every word in one cue and
    produced a third line as a last resort.  Subtitle renderers cannot express
    that reliably across players, so we create additional cues and let their
    timestamps be proportionally distributed by ``_render_entries``.
    """

    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean or len(clean) <= max_chars:
        return [clean] if clean else []
    words = clean.split()
    chunks: list[str] = []
    while words:
        remaining = " ".join(words)
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        # Find the largest word prefix within the two-line budget, then move
        # the boundary toward a protected-phrase-safe word break.
        max_cut = 1
        for index in range(2, len(words) + 1):
            if len(" ".join(words[:index])) > max_chars:
                break
            max_cut = index
        split_at = _find_best_break(words, max_cut, lo=1)
        split_at = min(max_cut, max(1, split_at))
        # ``_find_best_break`` may choose a nearby candidate that still pushes
        # the prefix over the character budget; walk back until it fits.
        while split_at > 1 and (
            len(" ".join(words[:split_at])) > max_chars or _protected_break(words, split_at)
        ):
            split_at -= 1
        chunks.append(" ".join(words[:split_at]))
        words = words[split_at:]
    return chunks


def _protected_break(words: list[str], index: int) -> bool:
    """Whether a cue boundary would strand a protected English phrase."""

    if index <= 0 or index >= len(words):
        return False
    previous = words[index - 1].lower().rstrip(".,;:!?")
    return previous in (_ARTICLES_AND_DETERMINERS | _PROTECTED_PREPOSITIONS | _AUXILIARIES)


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
            text = "(silence)"
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
    aliases = {"burn": "burned", "burn-in": "burned", "soft": "soft", "none": "none", "烧录": "burned", "软字幕": "soft", "无字幕": "none"}
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

    shots = list(storyboard)
    if not shots:
        return ensure_dialogue_assets(script)
    target_duration = sum(
        float(shot.get("duration_seconds", 4)) if isinstance(shot, dict) else float(getattr(shot, "duration_seconds", 4))
        for shot in shots
    )
    # Pass the real shot count through.  Calling the legacy default here would
    # normalise every project to six cues and silently replace shots 7–10 with
    # silence in longer films.
    result = ensure_dialogue_assets(
        script,
        duration_seconds=max(1, int(round(target_duration))),
        shot_count=len(shots),
    )
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
                entries.append({"line_id": f"L{index + 1:02d}", "speaker": _DEFAULT_SPEAKER, "kind": "narration", "text": "(silence)"})
            entry = entries[index]
            entry["shot"] = number
            entry["start_seconds"] = round(cursor, 3)
            entry["end_seconds"] = round(cursor + duration, 3)
            entry.setdefault("line_id", f"L{index + 1:02d}")
            entry.setdefault("speaker", _DEFAULT_SPEAKER)
            entry.setdefault("kind", "narration")
            entry["text"] = _entry_text(entry) or "(silence)"
        cursor += duration
    result["dialogue_book"] = dialogue[: len(shots)]
    result["subtitle_track"] = subtitle[: len(shots)]
    return result


def align_script_to_audio(
    script: dict[str, Any],
    audio_duration_seconds: float,
    *,
    minimum_cue_seconds: float = 0.18,
    word_boundaries: Iterable[Any] | None = None,
    forced_alignment: Iterable[Any] | None = None,
    sentence_boundaries: dict[str, Any] | None = None,
    shot_transitions: Iterable[float] | None = None,
) -> dict[str, Any]:
    """Re-time locked dialogue and subtitles to measured voice media.

    Without word-level timestamps, the most reliable deterministic fallback is
    a proportional sentence/cue allocation weighted by spoken word count.  It
    keeps the two editable tracks in lockstep, guarantees monotonic timings,
    and records the method so a provider with word timestamps can replace it
    later without changing the project contract.
    """

    duration = max(0.1, float(audio_duration_seconds or 0))
    # The priority is deliberate: provider-native events beat forced
    # alignment, which beats measured sentence boundaries, which beats the
    # proportional fallback below.
    native_events = list(word_boundaries or [])
    forced_events = list(forced_alignment or [])
    if native_events or forced_events:
        boundaries = normalize_word_boundaries(native_events or forced_events, duration)
        if boundaries:
            result = ensure_dialogue_assets(script, duration_seconds=max(1, int(round(duration))))
            cues = word_level_cues(result, boundaries, shot_transitions=shot_transitions)
            if cues:
                result["dialogue_book"] = deepcopy(cues)
                result["subtitle_track"] = deepcopy(cues)
                result["voice_alignment"] = {
                    "status": "MEASURED",
                    "media_duration_seconds": round(duration, 3),
                    "method": WORD_LEVEL,
                    "word_level_timestamps": True,
                    "source": "tts_native" if native_events else "forced_alignment",
                    "words": [item.to_dict() for item in boundaries],
                }
                return result
    if sentence_boundaries:
        measured_script = ensure_dialogue_assets(script, duration_seconds=max(1, int(round(duration))))
        if isinstance(sentence_boundaries.get("dialogue_book"), list):
            measured_script["dialogue_book"] = sentence_boundaries["dialogue_book"]
        if isinstance(sentence_boundaries.get("subtitle_track"), list):
            measured_script["subtitle_track"] = sentence_boundaries["subtitle_track"]
        cues = sentence_level_cues(measured_script, duration)
        if cues:
            measured_script["dialogue_book"] = deepcopy(cues)
            measured_script["subtitle_track"] = deepcopy(cues)
            measured_script["voice_alignment"] = {
                "status": "MEASURED",
                "media_duration_seconds": round(duration, 3),
                "method": SENTENCE_LEVEL,
                "word_level_timestamps": False,
                "source": "measured_sentence_boundaries",
            }
            return measured_script
    source_entries = _raw_entries((script or {}).get("dialogue_book") or (script or {}).get("subtitle_track"))
    cue_count = max(1, len(source_entries))
    result = ensure_dialogue_assets(
        script,
        duration_seconds=max(1, int(round(duration))),
        shot_count=cue_count,
    )

    def retime(entries: Any) -> list[dict[str, Any]]:
        items = [deepcopy(entry) for entry in _raw_entries(entries) if isinstance(entry, dict)]
        if not items:
            return []
        weights = []
        for entry in items:
            text = _entry_text(entry)
            weights.append(max(1.0, float(len(re.findall(r"\b[\w’'-]+\b", text))) if text else 0.35))
        total_weight = sum(weights) or float(len(items))
        # Keep a tiny positive cue duration even for many short lines, then
        # normalize the final cue so the media edge is covered exactly.
        minimum = min(max(0.0, minimum_cue_seconds), duration / max(1, len(items)))
        raw_durations = [max(minimum, duration * weight / total_weight) for weight in weights]
        scale = duration / (sum(raw_durations) or duration)
        cursor = 0.0
        retimed: list[dict[str, Any]] = []
        for index, entry in enumerate(items):
            if index == len(items) - 1:
                end = duration
            else:
                end = min(duration, cursor + raw_durations[index] * scale)
            entry["start_seconds"] = round(cursor, 3)
            entry["end_seconds"] = round(max(cursor, end), 3)
            entry["text"] = _entry_text(entry) or "(silence)"
            entry.setdefault("line_id", f"L{index + 1:02d}")
            entry.setdefault("speaker", _DEFAULT_SPEAKER)
            entry.setdefault("kind", "narration")
            retimed.append(entry)
            cursor = end
        return retimed

    dialogue = retime(result.get("dialogue_book"))
    subtitle = retime(result.get("subtitle_track"))
    if not subtitle:
        subtitle = deepcopy(dialogue)
    result["dialogue_book"] = dialogue
    result["subtitle_track"] = subtitle
    result["voice_alignment"] = {
        "status": "MEASURED",
        "media_duration_seconds": round(duration, 3),
        "method": PROPORTIONAL,
        "word_level_timestamps": False,
        "source": "word_count_weighted_fallback",
    }
    return result


def _render_entries(entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return export cues with guaranteed one- or two-line text blocks."""

    rendered: list[dict[str, Any]] = []
    for entry in entries:
        source = deepcopy(entry)
        text = _entry_text(source) or "(silence)"
        chunks = _split_long_text(text) or ["(silence)"]
        try:
            start = max(0.0, float(source.get("start_seconds", 0) or 0))
            end = max(start, float(source.get("end_seconds", start) or start))
        except (TypeError, ValueError):
            start, end = 0.0, 0.0
        if len(chunks) == 1:
            source["text"] = _wrap_cue_text(chunks[0])
            rendered.append(source)
            continue
        weights = [max(1, len(chunk)) for chunk in chunks]
        total_weight = float(sum(weights))
        duration = max(0.0, end - start)
        cursor = start
        for index, chunk in enumerate(chunks):
            next_cursor = end if index == len(chunks) - 1 else cursor + duration * weights[index] / total_weight
            part = deepcopy(source)
            line_id = str(source.get("line_id") or "CUE")
            part["line_id"] = f"{line_id}-{index + 1}"
            part["start_seconds"] = round(cursor, 3)
            part["end_seconds"] = round(max(cursor, next_cursor), 3)
            part["text"] = _wrap_cue_text(chunk)
            rendered.append(part)
            cursor = next_cursor
    return rendered


def _timestamp(seconds: Any, separator: str) -> str:
    total_ms = max(0, int(round(float(seconds or 0) * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def render_srt(entries: Iterable[dict[str, Any]]) -> str:
    rows = []
    for index, entry in enumerate(_render_entries(entries), start=1):
        text = str(entry.get("text") or "(silence)")
        rows.append(
            f"{index}\n{_timestamp(entry.get('start_seconds'), ',')} --> {_timestamp(entry.get('end_seconds'), ',')}\n{text}\n"
        )
    return "\n".join(rows).rstrip() + ("\n" if rows else "")


def render_vtt(entries: Iterable[dict[str, Any]]) -> str:
    rows = ["WEBVTT", ""]
    for index, entry in enumerate(_render_entries(entries), start=1):
        text = str(entry.get("text") or "(silence)")
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
