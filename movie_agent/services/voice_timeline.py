"""Place one continuous voice performance on the film timeline."""

from __future__ import annotations

import shutil
import subprocess
import wave
from collections import defaultdict
from pathlib import Path
from typing import Any

from movie_agent.services.alignment import PROPORTIONAL, SENTENCE_LEVEL, WORD_LEVEL, normalize_word_boundaries, word_level_cues


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


def _raw_voice_cues(script: dict[str, Any], raw_duration: float, word_boundaries: list[Any] | None = None) -> list[dict[str, Any]]:
    if word_boundaries:
        boundaries = normalize_word_boundaries(word_boundaries, raw_duration)
        cues = word_level_cues(script, boundaries)
        if cues:
            return [
                {
                    **cue,
                    "raw_start_seconds": float(cue.get("start_seconds", 0) or 0),
                    "raw_end_seconds": float(cue.get("end_seconds", 0) or 0),
                    "alignment_method": WORD_LEVEL,
                }
                for cue in cues
            ]
    entries = _speech_entries(script)
    if not entries:
        return []
    measured = str((script.get("voice_alignment") or {}).get("method") or "")
    if measured == SENTENCE_LEVEL and all(entry.get("start_seconds") is not None and entry.get("end_seconds") is not None for entry in entries):
        return [
            {
                **entry,
                "raw_start_seconds": float(entry.get("start_seconds") or 0),
                "raw_end_seconds": float(entry.get("end_seconds") or 0),
                "alignment_method": SENTENCE_LEVEL,
            }
            for entry in entries
        ]
    total_words = sum(_words(entry["text"]) for entry in entries)
    cursor = 0.0
    result: list[dict[str, Any]] = []
    for entry in entries:
        span = raw_duration * _words(entry["text"]) / max(1, total_words)
        result.append({
            **entry,
            "raw_start_seconds": round(cursor, 3),
            "raw_end_seconds": round(min(raw_duration, cursor + span), 3),
            "alignment_method": PROPORTIONAL,
        })
        cursor += span
    return result


def _timeline_cues(
    project: Any,
    script: dict[str, Any],
    raw_duration: float,
    word_boundaries: list[Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entries = _speech_entries(script)
    if not entries:
        return [], []
    raw_cues = _raw_voice_cues(script, raw_duration, word_boundaries)
    windows = _shot_windows(project)
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for entry in raw_cues:
        grouped[int(entry["shot"])].append(entry)
    cues: list[dict[str, Any]] = []
    overflow: list[dict[str, Any]] = []
    for shot_number, group in grouped.items():
        if shot_number not in windows:
            continue
        window_start, window_end = windows[shot_number]
        available = max(0.0, window_end - window_start)
        gap = min(0.18, available / max(2.0, len(group) * 4.0))
        spoken_total = sum(max(0.01, float(entry.get("raw_end_seconds", 0)) - float(entry.get("raw_start_seconds", 0))) for entry in group)
        cursor = window_start + gap
        for entry in group:
            local_duration = max(0.01, float(entry.get("raw_end_seconds", 0)) - float(entry.get("raw_start_seconds", 0)))
            placed_duration = local_duration
            start = cursor
            end = start + placed_duration
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
            cursor = end + gap
        if spoken_total > max(0.01, available) * 1.08:
            overflow.append(
                {
                    "shot": shot_number,
                    "line_id": group[0].get("line_id"),
                    "available_seconds": round(available, 3),
                    "spoken_seconds": round(spoken_total, 3),
                    "overflow_seconds": round(spoken_total - available, 3),
                }
            )
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
    for cue in cues:
        raw_start = max(0.0, float(cue.get("raw_start_seconds", 0) or 0))
        raw_end = max(raw_start, float(cue.get("raw_end_seconds", raw_start) or raw_start))
        frame_start = min(source_frames, int(round(raw_start * params.framerate)))
        frame_end = min(source_frames, max(frame_start + 1, int(round(raw_end * params.framerate))))
        if frame_start >= source_frames or frame_end <= frame_start:
            continue
        segment = frames[frame_start * frame_width:frame_end * frame_width]
        destination = max(0, int(round(float(cue.get("timeline_start_seconds", 0)) * params.framerate)))
        writable = min(len(segment), max(0, len(buffer) - destination * frame_width))
        buffer[destination * frame_width:destination * frame_width + writable] = segment[:writable]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as target:
        target.setparams(params._replace(nframes=output_frames))
        target.writeframes(bytes(buffer))


def _compose_media_with_ffmpeg(raw_path: Path, output_path: Path, duration: float, cues: list[dict[str, Any]], ffmpeg_bin: str) -> None:
    if not cues:
        filters = f"apad=whole_dur={duration:.3f},atrim=duration={duration:.3f}"
        command = [ffmpeg_bin, "-y", "-i", str(raw_path), "-af", filters, "-t", f"{duration:.3f}", str(output_path)]
    else:
        labels: list[str] = []
        filters: list[str] = []
        for index, cue in enumerate(cues):
            label = f"voice_{index}"
            start = max(0.0, float(cue.get("raw_start_seconds", 0) or 0))
            end = max(start + 0.01, float(cue.get("raw_end_seconds", start + 0.01) or start + 0.01))
            delay = max(0, int(round(float(cue.get("timeline_start_seconds", 0) or 0) * 1000)))
            filters.append(f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS,adelay={delay}|{delay}[{label}]")
            labels.append(f"[{label}]")
        filters.append("".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0,apad,atrim=duration={duration:.3f}[out]")
        command = [ffmpeg_bin, "-y", "-i", str(raw_path), "-filter_complex", ";".join(filters), "-map", "[out]", "-t", f"{duration:.3f}", str(output_path)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0 or not output_path.is_file():
        shutil.copy2(raw_path, output_path)


def compose_voice_timeline(
    project: Any,
    raw_path: Path,
    raw_duration: float,
    *,
    ffmpeg_bin: str = "ffmpeg",
    word_boundaries: list[Any] | None = None,
) -> dict[str, Any]:
    """Return timeline cues and a full-length voice track with real silence gaps."""

    duration = sum(float(getattr(shot, "duration_seconds", 0) or 0) for shot in getattr(project, "storyboard", []) or [])
    duration = max(0.01, duration or float(getattr(project, "duration_seconds", 0) or 0) or raw_duration)
    script = getattr(project, "script", {}) or {}
    cues, overflow = _timeline_cues(project, script, raw_duration, word_boundaries)
    output_path = raw_path.with_name("voice_timeline.wav")
    try:
        with wave.open(str(raw_path), "rb"):
            is_wav = True
    except (OSError, wave.Error):
        is_wav = False
    if is_wav:
        _compose_wav(raw_path, output_path, duration, cues, raw_duration)
    else:
        _compose_media_with_ffmpeg(raw_path, output_path, duration, cues, ffmpeg_bin)
    return {
        "media_path": str(output_path),
        "raw_media_path": str(raw_path),
        "duration_seconds": round(duration, 3),
        "cues": cues,
        "overflow": overflow,
        "alignment_method": next((cue.get("alignment_method") for cue in cues if cue.get("alignment_method")), PROPORTIONAL),
        "status": "SCRIPT_TIMING_REVIEW" if overflow else "TIMELINE_ALIGNED",
    }


__all__ = ["compose_voice_timeline"]
