"""Place one continuous voice performance on the film timeline."""

from __future__ import annotations

import shutil
import subprocess
import wave
from collections import defaultdict
from pathlib import Path
from typing import Any


def _words(text: str) -> int:
    return max(1, len(str(text or "").split()))


def _shot_windows(project: Any) -> dict[int, tuple[float, float]]:
    cursor = 0.0
    windows: dict[int, tuple[float, float]] = {}
    for shot in getattr(project, "storyboard", []) or []:
        duration = max(0.0, float(getattr(shot, "duration_seconds", 0) or 0))
        number = int(getattr(shot, "number", len(windows) + 1) or 0)
        windows[number] = (cursor, cursor + duration)
        cursor += duration
    return windows


def _speech_entries(script: dict[str, Any]) -> list[dict[str, Any]]:
    policies = script.get("speech_policy_by_shot") or {}
    source = script.get("dialogue_book") or script.get("subtitle_track") or []
    result = []
    for item in source:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("dialogue") or "").strip()
        shot = int(item.get("shot") or item.get("shot_number") or 0)
        if not text or text == "(silence)" or str(policies.get(str(shot), policies.get(shot, "NARRATION"))).upper() in {"SILENT", "AMBIENCE_ONLY"}:
            continue
        result.append(dict(item, shot=shot, text=text))
    return result


def _timeline_cues(project: Any, script: dict[str, Any], raw_duration: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entries = _speech_entries(script)
    if not entries:
        return [], []
    total_words = sum(_words(entry["text"]) for entry in entries)
    local_cursor = 0.0
    local_spans: list[tuple[float, float]] = []
    for entry in entries:
        duration = raw_duration * _words(entry["text"]) / max(1, total_words)
        local_spans.append((local_cursor, min(raw_duration, local_cursor + duration)))
        local_cursor += duration
    windows = _shot_windows(project)
    grouped: dict[int, list[tuple[dict[str, Any], float]]] = defaultdict(list)
    for entry, (local_start, local_end) in zip(entries, local_spans):
        grouped[int(entry["shot"])].append((entry, max(0.01, local_end - local_start)))
    cues: list[dict[str, Any]] = []
    overflow: list[dict[str, Any]] = []
    for shot_number, group in grouped.items():
        if shot_number not in windows:
            continue
        window_start, window_end = windows[shot_number]
        available = max(0.0, window_end - window_start)
        gap = min(0.18, available / max(2.0, len(group) * 4.0))
        spoken_total = sum(duration for _, duration in group)
        usable = max(0.01, available - gap * (len(group) + 1))
        scale = min(1.0, usable / spoken_total) if spoken_total else 1.0
        cursor = window_start + gap
        for entry, local_duration in group:
            placed_duration = local_duration * scale
            start = cursor
            end = min(window_end, start + placed_duration)
            cue = dict(entry)
            cue.update(
                {
                    "timeline_start_seconds": round(start, 3),
                    "timeline_end_seconds": round(end, 3),
                    "start_seconds": round(start, 3),
                    "end_seconds": round(end, 3),
                    "alignment_domain": "FILM_TIMELINE",
                }
            )
            cues.append(cue)
            if local_duration > placed_duration + 0.01:
                overflow.append(
                    {
                        "shot": shot_number,
                        "line_id": entry.get("line_id"),
                        "available_seconds": round(max(0.0, window_end - start), 3),
                        "spoken_seconds": round(local_duration, 3),
                        "overflow_seconds": round(local_duration - placed_duration, 3),
                    }
                )
            cursor = end + gap
    cues.sort(key=lambda item: (float(item.get("timeline_start_seconds", 0)), int(item.get("shot", 0))))
    return cues, overflow


def _compose_wav(raw_path: Path, output_path: Path, duration: float, cues: list[dict[str, Any]], raw_duration: float) -> None:
    with wave.open(str(raw_path), "rb") as source:
        params = source.getparams()
        frames = source.readframes(source.getnframes())
    frame_width = params.nchannels * params.sampwidth
    source_frames = len(frames) // max(1, frame_width)
    output_frames = max(1, int(round(duration * params.framerate)))
    buffer = bytearray(output_frames * frame_width)
    entries = _speech_entries({"dialogue_book": cues})
    total_words = sum(_words(entry["text"]) for entry in entries) or 1
    raw_cursor = 0
    for cue in cues:
        raw_count = int(round(source_frames * _words(str(cue.get("text") or "")) / total_words))
        raw_count = max(1, min(source_frames - raw_cursor, raw_count)) if raw_cursor < source_frames else 0
        if raw_count <= 0:
            continue
        segment = frames[raw_cursor * frame_width:(raw_cursor + raw_count) * frame_width]
        raw_cursor += raw_count
        destination = max(0, int(round(float(cue.get("timeline_start_seconds", 0)) * params.framerate)))
        writable = min(len(segment), max(0, len(buffer) - destination * frame_width))
        buffer[destination * frame_width:destination * frame_width + writable] = segment[:writable]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as target:
        target.setparams(params._replace(nframes=output_frames))
        target.writeframes(bytes(buffer))


def compose_voice_timeline(
    project: Any,
    raw_path: Path,
    raw_duration: float,
    *,
    ffmpeg_bin: str = "ffmpeg",
) -> dict[str, Any]:
    """Return timeline cues and a full-length voice track with real silence gaps."""

    duration = sum(float(getattr(shot, "duration_seconds", 0) or 0) for shot in getattr(project, "storyboard", []) or [])
    duration = max(0.01, duration or float(getattr(project, "duration_seconds", 0) or 0) or raw_duration)
    script = getattr(project, "script", {}) or {}
    cues, overflow = _timeline_cues(project, script, raw_duration)
    output_path = raw_path.with_name("voice_timeline.wav")
    try:
        with wave.open(str(raw_path), "rb"):
            is_wav = True
    except (OSError, wave.Error):
        is_wav = False
    if is_wav:
        _compose_wav(raw_path, output_path, duration, cues, raw_duration)
    else:
        # Provider-neutral fallback for MP3/other media. The normal Spark
        # provider emits WAV, but this keeps the contract honest for plugins.
        command = [ffmpeg_bin, "-y", "-i", str(raw_path), "-af", f"apad=whole_dur={duration:.3f}", "-t", f"{duration:.3f}", "-ar", "48000", "-ac", "2", str(output_path)]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0 or not output_path.is_file():
            shutil.copy2(raw_path, output_path)
    return {
        "media_path": str(output_path),
        "raw_media_path": str(raw_path),
        "duration_seconds": round(duration, 3),
        "cues": cues,
        "overflow": overflow,
        "status": "SCRIPT_TIMING_REVIEW" if overflow else "TIMELINE_ALIGNED",
    }


__all__ = ["compose_voice_timeline"]
