"""Sound-design planning and deterministic FFmpeg mix contracts.

The planner stays portable when a project has no generated audio, while the
editor consumes the same four-track contract to perform real Smart Ducking,
crossfade/dropout handling, loudness normalization, and limiting whenever
media paths are available.
"""

from __future__ import annotations

import re
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from movie_agent.services.subtitles import script_subtitle_track
from movie_agent.services.music import MusicProvider, render_music_asset


MUSIC_MODES = {"ai", "library", "upload"}
TRACK_ORDER = ("voice", "music", "sfx", "ambience")
EDIT_AUDIO_STAGES = ("picture_cut", "voice", "music", "sfx", "subtitles", "mix", "final_encode")
DEFAULT_MUSIC_INTENSITY = 0.6
TARGET_LOUDNESS_LUFS = -14.0
TARGET_TRUE_PEAK_DBTP = -1.0
DEFAULT_CROSSFADE_MS = 180


def loudness_filter() -> str:
    """Return the delivery loudness chain used by every real audio mix."""

    # -1 dBTP expressed as a linear limiter ceiling.  Keeping this in one
    # helper makes the target auditable in project.json and easy to replace
    # with a two-pass loudnorm implementation later.
    return (
        f"loudnorm=I={TARGET_LOUDNESS_LUFS}:TP={TARGET_TRUE_PEAK_DBTP}:LRA=7:linear=true:print_format=summary,"
        "alimiter=limit=0.89125:level_in=1"
    )


def crossfade_filter(input_labels: list[str], output_label: str, duration_ms: int = DEFAULT_CROSSFADE_MS) -> str | None:
    """Build an FFmpeg ``acrossfade`` chain for segmented audio media.

    The function returns ``None`` for a single clip because no crossfade is
    needed.  Track renderers can use the same helper for scene chunks while
    the default one-file Music/Ambience beds remain continuous via looping.
    """

    labels = [str(label).strip("[]") for label in input_labels if str(label).strip("[]")]
    if len(labels) < 2:
        return None
    duration = max(0.1, min(0.3, float(duration_ms) / 1000.0))
    current = labels[0]
    for index, label in enumerate(labels[1:], start=1):
        next_label = output_label if index == len(labels) - 1 else f"{output_label}_{index}"
        # c1/c2 triangular fades are deterministic, short, and avoid a hard
        # click at provider chunk boundaries.
        yield_filter = f"[{current}][{label}]acrossfade=d={duration:.3f}:c1=tri:c2=tri[{next_label}]"
        if index == 1:
            chain = yield_filter
        else:
            chain += ";" + yield_filter
        current = next_label
    return chain


def measure_loudness(path: Path, ffmpeg_bin: str = "ffmpeg") -> dict[str, float | None]:
    """Read FFmpeg loudnorm measurements without making probing mandatory."""

    result: dict[str, float | None] = {
        "integrated_lufs": None,
        "true_peak_dbtp": None,
    }
    if not path.is_file():
        return result
    command = [
        ffmpeg_bin,
        "-hide_banner",
        "-i",
        str(path),
        "-af",
        f"loudnorm=I={TARGET_LOUDNESS_LUFS}:TP={TARGET_TRUE_PEAK_DBTP}:LRA=7:print_format=json",
        "-f",
        "null",
        "-",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError:
        return result
    output = completed.stderr or ""
    # FFmpeg prints a compact JSON object after the filter summary.  Parse the
    # object first; the regex fallback accommodates older FFmpeg builds.
    start = output.rfind("{\n")
    if start >= 0:
        try:
            payload = json.loads(output[start:])
            result["integrated_lufs"] = float(payload.get("output_i"))
            result["true_peak_dbtp"] = float(payload.get("output_tp"))
            return result
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    match = re.search(r"output_i\"\s*:\s*\"?(-?\d+(?:\.\d+)?)", output)
    if match:
        result["integrated_lufs"] = float(match.group(1))
    match = re.search(r"output_tp\"\s*:\s*\"?(-?\d+(?:\.\d+)?)", output)
    if match:
        result["true_peak_dbtp"] = float(match.group(1))
    return result


def normalise_music_mode(value: Any) -> str:
    """Normalise UI labels and old aliases to the API's stable mode names."""

    aliases = {
        "auto": "ai",
        "ai_music": "ai",
        "ai 自动配乐": "ai",
        "素材库音乐": "library",
        "library_music": "library",
        "用户上传音乐": "upload",
        "user_upload": "upload",
    }
    mode = aliases.get(str(value or "").strip().lower(), str(value or "").strip().lower())
    return mode if mode in MUSIC_MODES else "ai"


def normalise_music_intensity(value: Any) -> float:
    """Keep the score intensity in a predictable 0–1 range for UI and FFmpeg."""

    try:
        intensity = float(value)
    except (TypeError, ValueError):
        intensity = DEFAULT_MUSIC_INTENSITY
    return round(max(0.0, min(1.0, intensity)), 2)


def _compact(value: Any, fallback: str = "") -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or fallback


def _shot_text(shot: Any) -> str:
    return " ".join(
        _compact(getattr(shot, key, ""))
        for key in ("image_description", "action", "sound_design")
    ).lower()


def _emotion_for_shot(shot: Any, index: int, total: int) -> tuple[str, float]:
    """Infer a small, explainable emotional marker from shot metadata."""

    text = _shot_text(shot)
    keyword_scores = {
        "tension": ("危险", "追", "警报", "故障", "黑暗", "紧张", "危机", "alarm", "threat"),
        "wonder": ("星", "光", "发现", "远景", "宇宙", "海", "wonder", "glow"),
        "grief": ("离开", "失去", "告别", "孤独", "雨", "泪", "grief", "alone"),
        "release": ("希望", "黎明", "打开", "拥抱", "归来", "释放", "dawn", "release"),
    }
    label = "suspense" if index < max(1, total // 3) else "resolve"
    for candidate, words in keyword_scores.items():
        if any(word in text for word in words):
            label = candidate
            break
    progress = index / max(1, total - 1)
    base = 0.22 + progress * 0.46
    if label == "tension":
        base += 0.22
    elif label == "wonder":
        base += 0.08
    elif label == "grief":
        base += 0.03
    elif label == "release":
        base += 0.16
    return label, round(max(0.16, min(0.96, base)), 2)


def _mode_source(mode: str, asset_name: str = "") -> tuple[str, str]:
    if mode == "library":
        return "STUDIO LIBRARY / CURATED SCORE", "SOURCE SELECTED · AUDIO PENDING"
    if mode == "upload":
        return (
            f"USER UPLOAD / {_compact(asset_name, 'WAITING FOR AUDIO FILE')}",
            "FILE READY" if asset_name else "WAITING FOR FILE",
        )
    return "AI MUSIC / EMOTIONAL ARC", "BRIEF READY · AUDIO PENDING"


def build_music_brief(
    project: Any,
    *,
    mode: str | None = None,
    asset_name: str = "",
    intensity: float | None = None,
) -> dict[str, Any]:
    """Create a compact Music Brief from director, writer, art, and shot data."""

    resolved_mode = normalise_music_mode(mode or getattr(project, "music_mode", "ai"))
    resolved_intensity = normalise_music_intensity(
        getattr(project, "music_intensity", DEFAULT_MUSIC_INTENSITY) if intensity is None else intensity
    )
    shots = list(getattr(project, "storyboard", []) or [])
    runtime = max(1, int(getattr(project, "duration_seconds", 48) or 48))
    theme = _compact((getattr(project, "brief", {}) or {}).get("theme") or (getattr(project, "brief", {}) or {}).get("主题"), "a quiet human choice")
    story = _compact((getattr(project, "script", {}) or {}).get("story"), "")
    visual_style = _compact(getattr(project, "visual_style", ""), "cinematic")
    arc = []
    cursor = 0
    for index, shot in enumerate(shots):
        label, intensity = _emotion_for_shot(shot, index, len(shots))
        duration = max(1, int(getattr(shot, "duration_seconds", 4) or 4))
        arc.append(
            {
                "shot": int(getattr(shot, "number", index + 1)),
                "start_seconds": cursor,
                "end_seconds": cursor + duration,
                "emotion": label,
                "intensity": intensity,
                "sync": "cut-aware" if duration <= 5 else "phrase-aware",
            }
        )
        cursor += duration
    average_shot = runtime / max(1, len(shots))
    bpm = int(round(max(58, min(128, 92 - average_shot * 2 + len(shots) * 1.5))))
    peak = round(runtime * (0.68 if len(shots) <= 7 else 0.72), 2)
    source, mode_status = _mode_source(resolved_mode, asset_name)
    return {
        "mode": resolved_mode,
        "intensity": resolved_intensity,
        "intensity_percent": int(round(resolved_intensity * 100)),
        "mode_status": mode_status,
        "source": source,
        "style": f"{visual_style} · cinematic score",
        "bpm": bpm,
        "key": "D minor → F major",
        "instruments": ["bass synthesiser", "granular piano", "bowed strings", "low-frequency percussion"],
        "entry_seconds": 0,
        "peak_seconds": peak,
        "fade_out_seconds": max(0, runtime - 4),
        "runtime_seconds": runtime,
        "emotional_arc": arc,
        "intensity_curve": [item["intensity"] for item in arc],
        "direction": f"Build a restrained-to-released sonic arc around \"{theme}\"; {story[:80]}",
        "rhythm_sync": "Align downbeats and transitions to shot durations; avoid continuous wall-to-wall coverage.",
        "version": 1,
    }


def build_audio_tracks(
    project: Any,
    *,
    mode: str | None = None,
    asset_name: str = "",
    music_intensity: float | None = None,
) -> dict[str, dict[str, Any]]:
    resolved_mode = normalise_music_mode(mode or getattr(project, "music_mode", "ai"))
    resolved_intensity = normalise_music_intensity(
        getattr(project, "music_intensity", DEFAULT_MUSIC_INTENSITY) if music_intensity is None else music_intensity
    )
    locked = bool((getattr(project, "script", {}) or {}).get("dialogue_locked"))
    voice_profile = getattr(project, "voice_profile", {}) or {}
    shots = list(getattr(project, "storyboard", []) or [])
    music_source, music_status = _mode_source(resolved_mode, asset_name)
    existing_music = (getattr(project, "audio_tracks", {}) or {}).get("music", {})
    existing_media = Path(str(existing_music.get("media_path") or ""))
    if resolved_mode == "upload" and not existing_media.is_file():
        music_status = "BRIEF READY · AUDIO PENDING"
    cue_count = len(script_subtitle_track(getattr(project, "script", {}) or {}))
    sfx_count = sum(1 for shot in shots if _compact(getattr(shot, "sound_design", "")))
    return {
        "voice": {
            "key": "voice",
            "label": "VOICE",
            "name": "Narration / Dialogue",
            "status": "READY" if locked else "LOCK REQUIRED",
            "source": f"LOCKED DIALOGUE BOOK · {cue_count} CUES" if locked else "DIALOGUE BOOK / REVIEW",
            "generation_strategy": "continuous_voice_track",
            "voice_id": voice_profile.get("voice_id", "en-US-GuyNeural"),
            "accent": voice_profile.get("accent", "en-US"),
            "speaking_rate": voice_profile.get("speaking_rate", 1.0),
            "voice_style": voice_profile.get("voice_style", "restrained cinematic narration"),
            "enabled": True,
            "volume_db": -2,
            "preview_url": None,
            "can_regenerate": False,
            "pan": 0,
            "ducking": False,
            "crossfade_ms": DEFAULT_CROSSFADE_MS,
        },
        "music": {
            "key": "music",
            "label": "MUSIC",
            "name": "AI Score / Music",
            "status": music_status,
            "source": music_source,
            "provider": "pending" if music_status.endswith("PENDING") else "file_upload",
            "brief_status": "BRIEF READY" if music_status.endswith("PENDING") else "AUDIO READY",
            "enabled": True,
            "volume_db": round(-20 + (resolved_intensity * 10), 1),
            "preview_url": None,
            "can_regenerate": True,
            "pan": 0,
            "ducking": True,
            "crossfade_ms": DEFAULT_CROSSFADE_MS,
        },
        "sfx": {
            "key": "sfx",
            "label": "SFX",
            "name": "Sound Effects / SFX",
            "status": "CUE MAP READY" if sfx_count else "CUE MAP EMPTY",
            "source": f"SHOT SOUND DESIGN · {sfx_count} CUES",
            "enabled": True,
            "volume_db": -10,
            "preview_url": None,
            "can_regenerate": True,
            "pan": 0,
            "ducking": False,
            "crossfade_ms": DEFAULT_CROSSFADE_MS,
        },
        "ambience": {
            "key": "ambience",
            "label": "AMBIENCE",
            "name": "Ambience / Atmos",
            "status": "ROOM TONE READY" if shots else "WAITING FOR SHOTS",
            "source": "VISUAL BIBLE · CONTINUOUS BED",
            "enabled": True,
            "volume_db": -22,
            "preview_url": None,
            "can_regenerate": True,
            "pan": 0,
            "ducking": False,
            "crossfade_ms": DEFAULT_CROSSFADE_MS,
        },
    }


def build_smart_ducking(project: Any, *, enabled: bool = True) -> dict[str, Any]:
    locked = bool((getattr(project, "script", {}) or {}).get("dialogue_locked"))
    cues = []
    for entry in script_subtitle_track(getattr(project, "script", {}) or {}):
        if not isinstance(entry, dict):
            continue
        text = _compact(entry.get("text"), "")
        if text and text != "(silence)":
            cues.append(
                {
                    "shot": int(entry.get("shot", 0) or 0),
                    "start_seconds": float(entry.get("start_seconds", 0) or 0),
                    "end_seconds": float(entry.get("end_seconds", 0) or 0),
                    "text": text,
                }
            )
    return {
        "enabled": bool(enabled),
        "status": "ACTIVE" if enabled and locked and cues else ("LOCK REQUIRED" if enabled and cues else "OFF"),
        "amount_db": -8,
        "attack_ms": 120,
        "release_ms": 420,
        "voice_cues": cues,
        "description": "Music automatically ducks when dialogue or narration is present and smoothly recovers after speech ends.",
        "signal_source": "continuous_voice_track",
    }


def ensure_audio_design(
    project: Any,
    *,
    music_mode: str | None = None,
    smart_ducking: bool | None = None,
    music_asset_name: str | None = None,
    music_intensity: float | None = None,
    music_provider: MusicProvider | None = None,
    music_output_dir: Path | None = None,
) -> Any:
    """Mutate a project with the current sound department's reviewable plan."""

    previous_mode = normalise_music_mode(getattr(project, "music_mode", "ai"))
    previous_asset_name = _compact(getattr(project, "music_asset_name", ""), "")
    mode = normalise_music_mode(music_mode or previous_mode)
    previous_intensity = normalise_music_intensity(
        getattr(project, "music_intensity", DEFAULT_MUSIC_INTENSITY)
    )
    resolved_intensity = previous_intensity if music_intensity is None else normalise_music_intensity(music_intensity)
    asset_source = previous_asset_name if music_asset_name is None else music_asset_name
    # A stored upload is not an active source after switching to AI or the
    # curated library. Keep the file on disk for recovery, but do not expose
    # its preview/path as the current MUSIC track.
    asset_name = _compact(asset_source, "") if mode == "upload" else ""
    enabled = bool(
        getattr(project, "smart_ducking", {})
        .get("enabled", True)
        if smart_ducking is None
        else smart_ducking
    )
    old_tracks = deepcopy(getattr(project, "audio_tracks", {}) or {})
    project.music_mode = mode
    project.music_asset_name = asset_name
    project.music_intensity = resolved_intensity
    project.music_brief = build_music_brief(project, mode=mode, asset_name=asset_name, intensity=resolved_intensity)
    project.audio_tracks = build_audio_tracks(
        project,
        mode=mode,
        asset_name=asset_name,
        music_intensity=resolved_intensity,
    )
    for key, track in project.audio_tracks.items():
        previous = old_tracks.get(key) or {}
        if "enabled" in previous:
            track["enabled"] = bool(previous["enabled"])
        if "volume_db" in previous and not (key == "music" and music_intensity is not None):
            track["volume_db"] = previous["volume_db"]
        for setting in ("pan", "ducking"):
            if setting in previous:
                track[setting] = previous[setting]
        for setting in ("alignment", "duration_seconds", "duration_source", "provider_error"):
            if setting in previous:
                track[setting] = deepcopy(previous[setting])
        if key == "voice" and str(previous.get("status") or "").startswith("STALE"):
            track["status"] = previous["status"]
        if previous.get("preview_url") and not (key == "music" and mode != "upload"):
            track["preview_url"] = previous["preview_url"]
        if previous.get("media_path") and not (key == "music" and mode != "upload"):
            track["media_path"] = previous["media_path"]
        if previous.get("revision"):
            track["revision"] = previous["revision"]
    if music_provider is not None:
        try:
            rendered_music = render_music_asset(
                project,
                music_provider,
                music_output_dir or Path("outputs") / project.project_id / "audio",
            )
            project.audio_tracks["music"].update(rendered_music)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            project.audio_tracks["music"].update(
                {
                    "status": "BRIEF READY · AUDIO PENDING",
                    "brief_status": "BRIEF READY",
                    "provider": getattr(music_provider, "name", music_provider.__class__.__name__),
                    "provider_error": str(exc),
                }
            )
    project.smart_ducking = build_smart_ducking(project, enabled=enabled)
    previous_mix = deepcopy(getattr(project, "mix_state", {}) or {})
    previous_stage_status = previous_mix.get("stage_status") or {}
    project.mix_state = {
        "status": previous_mix.get("status", "DESIGN READY"),
        "pipeline": list(previous_mix.get("pipeline") or EDIT_AUDIO_STAGES),
        "active_stage": previous_mix.get("active_stage"),
        # Keep targets separate from measured output.  The previous API used
        # ``loudness_lufs`` / ``true_peak_db`` as if the target were a meter
        # reading; the explicit fields prevent the UI from claiming a mix is
        # normalized before a real audio file has passed FFmpeg.
        "loudness_lufs": previous_mix.get("loudness_lufs", TARGET_LOUDNESS_LUFS),
        "true_peak_db": previous_mix.get("true_peak_db", TARGET_TRUE_PEAK_DBTP),
        "loudness_target_lufs": previous_mix.get("loudness_target_lufs", TARGET_LOUDNESS_LUFS),
        "true_peak_target_dbtp": previous_mix.get("true_peak_target_dbtp", TARGET_TRUE_PEAK_DBTP),
        "loudness_measured_lufs": previous_mix.get("loudness_measured_lufs"),
        "true_peak_measured_dbtp": previous_mix.get("true_peak_measured_dbtp"),
        "loudness_status": previous_mix.get("loudness_status", "PENDING MEDIA"),
        "limiter": previous_mix.get("limiter", "PENDING MEDIA"),
        "crossfade_ms": int(previous_mix.get("crossfade_ms", DEFAULT_CROSSFADE_MS) or DEFAULT_CROSSFADE_MS),
        "crossfade_status": previous_mix.get("crossfade_status", "PENDING MEDIA"),
        "ducking_status": previous_mix.get("ducking_status", "PENDING MEDIA"),
        "filter_chain": previous_mix.get("filter_chain", loudness_filter()),
        "ducking": "ON" if enabled else "OFF",
        "media_mixed": bool(previous_mix.get("media_mixed", False)),
        "stage_status": {stage: str(previous_stage_status.get(stage, "queued")) for stage in EDIT_AUDIO_STAGES},
    }
    return project


def apply_audio_track_params(project: Any, track_params: dict[str, dict[str, Any]] | None = None) -> Any:
    """Apply bounded per-track mix controls from the sound console Inspector."""

    for key, params in (track_params or {}).items():
        if key not in ("voice", "music", "sfx", "ambience") or not isinstance(params, dict):
            continue
        track = (project.audio_tracks or {}).setdefault(key, {})
        if params.get("volume_db") is not None:
            try:
                track["volume_db"] = round(max(-60.0, min(6.0, float(params["volume_db"]))), 1)
            except (TypeError, ValueError):
                pass
        if params.get("pan") is not None:
            try:
                track["pan"] = round(max(-1.0, min(1.0, float(params["pan"]))), 2)
            except (TypeError, ValueError):
                pass
        if params.get("ducking") is not None:
            track["ducking"] = bool(params["ducking"])
    return project


def mark_audio_stage(project: Any, stage: str, status: str) -> Any:
    """Persist a small stage state map for UI recovery and API consumers."""

    if stage not in EDIT_AUDIO_STAGES:
        raise ValueError(f"Unknown audio production stage: {stage}")
    statuses = dict((project.mix_state or {}).get("stage_status") or {})
    statuses.setdefault(stage, "queued")
    statuses[stage] = status
    project.mix_state["stage_status"] = statuses
    project.mix_state["active_stage"] = stage if status == "working" else project.mix_state.get("active_stage")
    return project


def regenerate_track(project: Any, track_key: str) -> Any:
    """Bump a track revision while keeping user toggles and mix settings."""

    key = str(track_key or "").strip().lower()
    if key not in TRACK_ORDER:
        raise ValueError("Track must be one of Voice, Music, SFX, or Ambience.")
    ensure_audio_design(project)
    track = project.audio_tracks[key]
    track["revision"] = int(track.get("revision", 1) or 1) + 1
    track["status"] = "REGENERATED · READY" if key != "voice" else track["status"]
    if key == "music":
        project.music_brief["version"] = int(project.music_brief.get("version", 1) or 1) + 1
    project.mix_state["media_mixed"] = False
    project.mix_state["status"] = "DESIGN UPDATED"
    return project
