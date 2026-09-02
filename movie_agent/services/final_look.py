"""Whole-film colour finishing plans for the Deliver / Screening Room stage.

Final Look is intentionally separate from shot generation.  A user can audition
the look in the browser, then explicitly apply it to the finished cut.  The
same small JSON contract is consumed by the UI and by the optional FFmpeg
finisher, so mock projects never need to pretend that a media file exists.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


FINAL_LOOK_PRESETS: dict[str, dict[str, Any]] = {
    "original": {
        "label": "原片",
        "english": "ORIGINAL",
        "description": "保留原始曝光、色彩与镜头质感。",
        "css": "original",
        "contrast": 0.0,
        "saturation": 0.0,
        "brightness": 0.0,
        "balance": (0.0, 0.0, 0.0),
    },
    "film_narrative": {
        "label": "胶片叙事",
        "english": "FILM NARRATIVE",
        "description": "暖肤色、柔和反差和轻微乳剂颗粒，适合人物叙事。",
        "css": "film",
        "contrast": 0.08,
        "saturation": -0.16,
        "brightness": 0.01,
        "balance": (0.08, 0.02, -0.05),
    },
    "cool_gray_future": {
        "label": "冷灰未来",
        "english": "COOL GRAY FUTURE",
        "description": "压低暖色、抬高蓝灰阴影，保持克制的未来感。",
        "css": "cool",
        "contrast": 0.11,
        "saturation": -0.28,
        "brightness": -0.015,
        "balance": (-0.04, 0.0, 0.09),
    },
    "dream_surreal": {
        "label": "梦境超现实",
        "english": "DREAM SURREAL",
        "description": "高光轻柔、色彩稍微漂浮，让现实边界变得不确定。",
        "css": "dream",
        "contrast": -0.05,
        "saturation": 0.2,
        "brightness": 0.035,
        "balance": (0.04, 0.04, 0.08),
    },
    "documentary_desaturated": {
        "label": "纪实去饱和",
        "english": "DOCUMENTARY DESAT",
        "description": "低饱和、高信息密度，保留现场观察感。",
        "css": "documentary",
        "contrast": 0.1,
        "saturation": -0.52,
        "brightness": -0.005,
        "balance": (0.0, 0.0, 0.0),
    },
    "cyber_night": {
        "label": "赛博夜色",
        "english": "CYBER NIGHT",
        "description": "深黑底色与冷蓝高光，强化夜景和电子空间。",
        "css": "cyber",
        "contrast": 0.18,
        "saturation": 0.24,
        "brightness": -0.055,
        "balance": (-0.04, 0.02, 0.12),
    },
}

FINAL_LOOK_SCOPES = {"whole_film", "current_scene", "current_shot"}
DEFAULT_FINAL_LOOK: dict[str, Any] = {
    "preset": "original",
    "intensity": 0.72,
    "grain": 0.0,
    "vignette": 0.0,
    "highlight_soften": 0.0,
    "scope": "whole_film",
    "applied": False,
    "status": "READY TO FINISH",
    "revision": 1,
    "base_media_path": None,
    "media_path": None,
}


def _clamp(value: Any, low: float, high: float, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = fallback
    return round(max(low, min(high, number)), 3)


def normalise_look_preset(value: Any) -> str:
    aliases = {
        "原片": "original",
        "original": "original",
        "胶片叙事": "film_narrative",
        "film": "film_narrative",
        "film narrative": "film_narrative",
        "冷灰未来": "cool_gray_future",
        "cool": "cool_gray_future",
        "冷灰": "cool_gray_future",
        "梦境超现实": "dream_surreal",
        "dream": "dream_surreal",
        "纪实去饱和": "documentary_desaturated",
        "documentary": "documentary_desaturated",
        "赛博夜色": "cyber_night",
        "cyber": "cyber_night",
    }
    key = str(value or "").strip().lower()
    key = aliases.get(key, key)
    return key if key in FINAL_LOOK_PRESETS else "original"


def normalise_look_scope(value: Any) -> str:
    key = str(value or "whole_film").strip().lower()
    aliases = {"全片": "whole_film", "scene": "current_scene", "shot": "current_shot"}
    key = aliases.get(key, key)
    return key if key in FINAL_LOOK_SCOPES else "whole_film"


def _scope_label(scope: str) -> str:
    return {
        "whole_film": "WHOLE FILM",
        "current_scene": "CURRENT SCENE",
        "current_shot": "CURRENT SHOT",
    }.get(scope, "WHOLE FILM")


def normalise_final_look(value: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a stable, backwards-compatible Final Look object."""

    raw = deepcopy(value or {})
    preset = normalise_look_preset(raw.get("preset"))
    scope = normalise_look_scope(raw.get("scope"))
    info = FINAL_LOOK_PRESETS[preset]
    result = {
        **raw,
        "preset": preset,
        "label": info["label"],
        "english": info["english"],
        "description": info["description"],
        "intensity": _clamp(raw.get("intensity", DEFAULT_FINAL_LOOK["intensity"]), 0, 1, 0.72),
        "grain": _clamp(raw.get("grain", 0), 0, 1, 0),
        "vignette": _clamp(raw.get("vignette", 0), 0, 1, 0),
        "highlight_soften": _clamp(raw.get("highlight_soften", 0), 0, 1, 0),
        "scope": scope,
        "applied": bool(raw.get("applied", False)),
        "revision": max(1, int(raw.get("revision", 1) or 1)),
        "base_media_path": raw.get("base_media_path"),
        "media_path": raw.get("media_path"),
    }
    if result["applied"]:
        result["status"] = (
            f"{info['english']} · {_scope_label(scope)}"
            if preset != "original" or any(result[key] > 0 for key in ("grain", "vignette", "highlight_soften"))
            else "ORIGINAL · APPLIED"
        )
    else:
        result["status"] = str(raw.get("status") or "READY TO FINISH")
    return result


def ensure_final_look(project: Any, **changes: Any) -> Any:
    """Attach or update a project's Final Look without touching media."""

    current = normalise_final_look(getattr(project, "final_look", {}) or {})
    for key in ("preset", "intensity", "grain", "vignette", "highlight_soften", "scope", "applied"):
        if key in changes and changes[key] is not None:
            current[key] = changes[key]
    if changes.get("increment_revision"):
        current["revision"] = int(current.get("revision", 1) or 1) + 1
    project.final_look = normalise_final_look(current)
    return project


def reset_final_look(project: Any) -> Any:
    """Clear an applied media render when a new Final Cut is approved."""

    ensure_final_look(project, applied=False)
    project.final_look["status"] = "READY TO FINISH"
    project.final_look["base_media_path"] = None
    project.final_look["media_path"] = None
    return project


def final_look_filter(value: dict[str, Any] | None) -> str:
    """Build a conservative FFmpeg video filter chain for an applied look."""

    look = normalise_final_look(value)
    preset = FINAL_LOOK_PRESETS[look["preset"]]
    intensity = float(look["intensity"])
    filters: list[str] = []
    if look["preset"] != "original" and intensity > 0:
        contrast = 1 + float(preset["contrast"]) * intensity
        saturation = max(0.1, 1 + float(preset["saturation"]) * intensity)
        brightness = float(preset["brightness"]) * intensity
        filters.append(
            f"eq=contrast={contrast:.4f}:saturation={saturation:.4f}:brightness={brightness:.4f}"
        )
        red, green, blue = (float(part) * intensity for part in preset["balance"])
        if any(abs(part) > 0.0005 for part in (red, green, blue)):
            filters.append(f"colorbalance=rs={red:.4f}:gs={green:.4f}:bs={blue:.4f}")
    grain = float(look["grain"])
    if grain > 0:
        filters.append(f"noise=alls={max(1, round(18 * grain))}:allf=t+u")
    vignette = float(look["vignette"])
    if vignette > 0:
        filters.append("vignette=angle=PI/5")
    soften = float(look["highlight_soften"])
    if soften > 0:
        # A very small blur is used as a portable fallback for highlight
        # diffusion; the browser preview uses a softer local overlay.
        filters.append(f"gblur=sigma={0.18 + soften * 0.62:.3f}")
    return ",".join(filters) or "null"
