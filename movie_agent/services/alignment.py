"""Speech alignment primitives shared by voice synthesis and subtitles."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable


WORD_LEVEL = "WORD-LEVEL"
SENTENCE_LEVEL = "SENTENCE-LEVEL"
PROPORTIONAL = "PROPORTIONAL"


@dataclass(frozen=True)
class WordBoundary:
    word: str
    start_time: float
    end_time: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _event_time(event: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _number(event.get(key))
        if value is not None:
            return value
    return None


def normalize_word_boundaries(events: Iterable[Any] | None, duration_seconds: float) -> list[WordBoundary]:
    """Normalize native TTS or forced-alignment events to one stable schema."""

    duration = max(0.1, float(duration_seconds or 0))
    parsed: list[tuple[str, float, float | None]] = []
    for raw in events or []:
        if isinstance(raw, WordBoundary):
            parsed.append((raw.word.strip(), raw.start_time, raw.end_time))
            continue
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            word = str(raw[0] or "").strip()
            start = _number(raw[1])
            end = _number(raw[2]) if len(raw) > 2 else None
        elif isinstance(raw, dict):
            word = str(raw.get("word") or raw.get("text") or raw.get("token") or "").strip()
            start = _event_time(raw, "start_time", "start_seconds", "start", "offset")
            end = _event_time(raw, "end_time", "end_seconds", "end")
            if start is not None and start > duration * 20:
                start /= 1000.0
            if end is not None and end > duration * 20:
                end /= 1000.0
        else:
            continue
        if word and start is not None:
            parsed.append((word, start, end))
    parsed.sort(key=lambda item: item[1])
    boundaries: list[WordBoundary] = []
    for index, (word, start, raw_end) in enumerate(parsed):
        next_start = parsed[index + 1][1] if index + 1 < len(parsed) else duration
        start = min(duration, max(0.0, start))
        end = raw_end if raw_end is not None else next_start
        end = min(duration, max(start + 0.01, end))
        if boundaries:
            start = max(start, boundaries[-1].end_time)
            end = max(start + 0.01, end)
        boundaries.append(WordBoundary(word, round(start, 3), round(min(duration, end), 3)))
    return boundaries


def _words(text: str) -> list[str]:
    return re.findall(r"\b[\w’'-]+(?:[.!?,;:]*)", text or "")


def _source_entries(script: dict[str, Any]) -> list[dict[str, Any]]:
    entries = script.get("dialogue_book") or script.get("subtitle_track") or []
    return [dict(item) for item in entries if isinstance(item, dict) and str(item.get("text") or item.get("dialogue") or "").strip()]


def _cue_groups(words: list[WordBoundary], *, pause_threshold: float = 0.45, max_words: int = 9) -> list[list[WordBoundary]]:
    groups: list[list[WordBoundary]] = []
    current: list[WordBoundary] = []
    for index, boundary in enumerate(words):
        current.append(boundary)
        following = words[index + 1] if index + 1 < len(words) else None
        punctuation_break = boundary.word.rstrip().endswith((".", "!", "?", ";", ":"))
        pause_break = following is not None and following.start_time - boundary.end_time >= pause_threshold
        if punctuation_break or pause_break or len(current) >= max_words:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def word_level_cues(
    script: dict[str, Any],
    boundaries: Iterable[WordBoundary],
    *,
    shot_transitions: Iterable[float] | None = None,
) -> list[dict[str, Any]]:
    """Build cues from punctuation, pauses, semantic-sized phrases and cuts."""

    all_words = list(boundaries)
    if not all_words:
        return []
    transitions = sorted(float(value) for value in (shot_transitions or []) if _number(value) is not None)
    source = _source_entries(script)
    counts = [len(_words(str(entry.get("text") or entry.get("dialogue") or ""))) for entry in source]
    assignments: list[tuple[dict[str, Any] | None, list[WordBoundary]]] = []
    cursor = 0
    if source and sum(counts) > 0:
        for entry, count in zip(source, counts):
            chunk = all_words[cursor:cursor + max(1, count)]
            cursor += len(chunk)
            if chunk:
                assignments.append((entry, chunk))
        if cursor < len(all_words):
            assignments.append((source[-1], all_words[cursor:]))
    else:
        assignments = [(None, all_words)]

    cues: list[dict[str, Any]] = []
    for entry, assigned in assignments:
        for group in _cue_groups(assigned):
            subgroups: list[list[WordBoundary]] = [[]]
            for boundary in group:
                subgroups[-1].append(boundary)
                if any(boundary.start_time < cut <= boundary.end_time for cut in transitions):
                    subgroups.append([])
            for subgroup in [part for part in subgroups if part]:
                first, last = subgroup[0], subgroup[-1]
                cue = dict(entry or {})
                cue.update(
                    {
                        "text": " ".join(item.word for item in subgroup).strip(),
                        "start_seconds": first.start_time,
                        "end_seconds": last.end_time,
                        "alignment_method": WORD_LEVEL,
                        "word_start_index": all_words.index(first),
                        "word_end_index": all_words.index(last) + 1,
                    }
                )
                cues.append(cue)
    for index, cue in enumerate(cues, start=1):
        cue.setdefault("line_id", f"L{index:02d}")
        cue.setdefault("shot", index)
        cue.setdefault("speaker", "NARRATOR")
        cue.setdefault("kind", "narration")
    return cues


def sentence_level_cues(script: dict[str, Any], duration_seconds: float) -> list[dict[str, Any]]:
    """Use measured sentence timings already supplied by a provider."""

    duration = max(0.1, float(duration_seconds or 0))
    cues: list[dict[str, Any]] = []
    for index, entry in enumerate(_source_entries(script), start=1):
        start = _number(entry.get("start_seconds", entry.get("start")))
        end = _number(entry.get("end_seconds", entry.get("end")))
        if start is None or end is None or end <= start:
            return []
        cue = dict(entry)
        cue.update({"start_seconds": round(min(duration, start), 3), "end_seconds": round(min(duration, end), 3), "alignment_method": SENTENCE_LEVEL})
        cue.setdefault("line_id", f"L{index:02d}")
        cues.append(cue)
    return cues


__all__ = ["PROPORTIONAL", "SENTENCE_LEVEL", "WORD_LEVEL", "WordBoundary", "normalize_word_boundaries", "sentence_level_cues", "word_level_cues"]
