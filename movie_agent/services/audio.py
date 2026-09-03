"""Deterministic sound-design planning shared by AI Edit and Deliver.

The first implementation deliberately produces a reviewable, portable audio
plan rather than pretending that a mock project contains finished music files.
The plan is the contract a future music/SFX renderer can consume: one Music
Brief, an emotional arc, four named tracks, and Smart Ducking voice cues.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from movie_agent.services.subtitles import script_subtitle_track


MUSIC_MODES = {"ai", "library", "upload"}
TRACK_ORDER = ("voice", "music", "sfx", "ambience")
EDIT_AUDIO_STAGES = ("picture_cut", "voice", "music", "sfx", "subtitles", "mix", "final_encode")
DEFAULT_MUSIC_INTENSITY = 0.6


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
    theme = _compact((getattr(project, "brief", {}) or {}).get("主题"), "a quiet human choice")
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
        "instruments": ["低音合成器", "颗粒钢琴", "弓弦纹理", "低频打击"],
        "entry_seconds": 0,
        "peak_seconds": peak,
        "fade_out_seconds": max(0, runtime - 4),
        "runtime_seconds": runtime,
        "emotional_arc": arc,
        "intensity_curve": [item["intensity"] for item in arc],
        "direction": f"围绕“{theme}”建立由克制到释放的声音弧线；{story[:80]}",
        "rhythm_sync": "按 Shot duration 对齐重拍与转场，避免连续铺满。",
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
    shots = list(getattr(project, "storyboard", []) or [])
    music_source, music_status = _mode_source(resolved_mode, asset_name)
    cue_count = len(script_subtitle_track(getattr(project, "script", {}) or {}))
    sfx_count = sum(1 for shot in shots if _compact(getattr(shot, "sound_design", "")))
    return {
        "voice": {
            "key": "voice",
            "label": "VOICE",
            "name": "旁白 / Dialogue",
            "status": "READY" if locked else "LOCK REQUIRED",
            "source": f"LOCKED DIALOGUE BOOK · {cue_count} CUES" if locked else "DIALOGUE BOOK / REVIEW",
            "enabled": True,
            "volume_db": -2,
            "preview_url": None,
            "can_regenerate": False,
        },
        "music": {
            "key": "music",
            "label": "MUSIC",
            "name": "AI 配乐 / Score",
            "status": music_status,
            "source": music_source,
            "enabled": True,
            "volume_db": round(-20 + (resolved_intensity * 10), 1),
            "preview_url": None,
            "can_regenerate": True,
        },
        "sfx": {
            "key": "sfx",
            "label": "SFX",
            "name": "动作音效 / Effects",
            "status": "CUE MAP READY" if sfx_count else "CUE MAP EMPTY",
            "source": f"SHOT SOUND DESIGN · {sfx_count} CUES",
            "enabled": True,
            "volume_db": -10,
            "preview_url": None,
            "can_regenerate": True,
        },
        "ambience": {
            "key": "ambience",
            "label": "AMBIENCE",
            "name": "环境声 / Atmos",
            "status": "ROOM TONE READY" if shots else "WAITING FOR SHOTS",
            "source": "VISUAL BIBLE · CONTINUOUS BED",
            "enabled": True,
            "volume_db": -22,
            "preview_url": None,
            "can_regenerate": True,
        },
    }


def build_smart_ducking(project: Any, *, enabled: bool = True) -> dict[str, Any]:
    locked = bool((getattr(project, "script", {}) or {}).get("dialogue_locked"))
    cues = []
    for entry in script_subtitle_track(getattr(project, "script", {}) or {}):
        if not isinstance(entry, dict):
            continue
        text = _compact(entry.get("text"), "")
        if text and text != "（留白）":
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
        "description": "对白 / 旁白出现时，Music 自动降低并在语音结束后平滑恢复。",
    }


def ensure_audio_design(
    project: Any,
    *,
    music_mode: str | None = None,
    smart_ducking: bool | None = None,
    music_asset_name: str | None = None,
    music_intensity: float | None = None,
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
        if previous.get("preview_url") and not (key == "music" and mode != "upload"):
            track["preview_url"] = previous["preview_url"]
        if previous.get("media_path") and not (key == "music" and mode != "upload"):
            track["media_path"] = previous["media_path"]
        if previous.get("revision"):
            track["revision"] = previous["revision"]
    project.smart_ducking = build_smart_ducking(project, enabled=enabled)
    previous_mix = deepcopy(getattr(project, "mix_state", {}) or {})
    previous_stage_status = previous_mix.get("stage_status") or {}
    project.mix_state = {
        "status": previous_mix.get("status", "DESIGN READY"),
        "pipeline": list(previous_mix.get("pipeline") or EDIT_AUDIO_STAGES),
        "active_stage": previous_mix.get("active_stage"),
        "loudness_lufs": previous_mix.get("loudness_lufs", -14),
        "true_peak_db": previous_mix.get("true_peak_db", -1),
        "ducking": "ON" if enabled else "OFF",
        "media_mixed": bool(previous_mix.get("media_mixed", False)),
        "stage_status": {stage: str(previous_stage_status.get(stage, "queued")) for stage in EDIT_AUDIO_STAGES},
    }
    return project


def mark_audio_stage(project: Any, stage: str, status: str) -> Any:
    """Persist a small stage state map for UI recovery and API consumers."""

    if stage not in EDIT_AUDIO_STAGES:
        raise ValueError(f"未知的声音制作阶段：{stage}")
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
        raise ValueError("音轨仅支持 Voice、Music、SFX 或 Ambience。")
    ensure_audio_design(project)
    track = project.audio_tracks[key]
    track["revision"] = int(track.get("revision", 1) or 1) + 1
    track["status"] = "REGENERATED · READY" if key != "voice" else track["status"]
    if key == "music":
        project.music_brief["version"] = int(project.music_brief.get("version", 1) or 1) + 1
    project.mix_state["media_mixed"] = False
    project.mix_state["status"] = "DESIGN UPDATED"
    return project
