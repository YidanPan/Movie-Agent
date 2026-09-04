"""Media quality tiers for fast previews and safe final delivery.

The editor keeps three intentionally different contracts:

* ``working_proxy`` is disposable and optimized for interaction.
* ``screening_preview`` is the viewer-facing copy (720p/1080p when the source
  can support it).
* ``final_master`` is the only source allowed into a delivery export.

All helpers are best-effort around ffprobe/ffmpeg so mock projects remain
fully usable without media binaries.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


TARGETS = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
}


def target_dimensions(resolution: str = "1080p") -> tuple[int, int]:
    return TARGETS.get(str(resolution).lower().strip(), TARGETS["1080p"])


def probe_media(path: Path, ffprobe_bin: str = "ffprobe") -> dict[str, Any]:
    """Return stable video metadata without making probing a hard dependency."""

    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "width": None,
        "height": None,
        "duration_seconds": None,
        "fps": None,
        "codec": None,
    }
    if not path.is_file():
        return result
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,codec_name:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        payload = json.loads(completed.stdout or "{}")
    except (OSError, ValueError, TypeError):
        return result
    streams = payload.get("streams") if isinstance(payload, dict) else None
    stream = streams[0] if isinstance(streams, list) and streams and isinstance(streams[0], dict) else {}
    for key in ("width", "height"):
        try:
            result[key] = int(stream[key]) if stream.get(key) is not None else None
        except (TypeError, ValueError):
            result[key] = None
    result["codec"] = str(stream.get("codec_name") or "").upper() or None
    rate = str(stream.get("r_frame_rate") or "")
    try:
        numerator, denominator = rate.split("/", 1)
        result["fps"] = round(float(numerator) / float(denominator), 3) if float(denominator) else None
    except (ValueError, TypeError, ZeroDivisionError):
        result["fps"] = None
    media_format = payload.get("format") if isinstance(payload, dict) else None
    try:
        result["duration_seconds"] = round(float(media_format.get("duration")), 3) if media_format and media_format.get("duration") else None
    except (TypeError, ValueError):
        result["duration_seconds"] = None
    return result


def quality_label(metadata: dict[str, Any], target_resolution: str = "1080p") -> str:
    """Map dimensions to a human-readable UI quality signal."""

    width, height = metadata.get("width"), metadata.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        return "QUALITY UNKNOWN"
    target_width, target_height = target_dimensions(target_resolution)
    if width >= target_width and height >= target_height:
        return target_resolution.upper()
    if width >= 1280 and height >= 720:
        return "720P"
    return "LOW RES SOURCE"


def asset_record(
    path: Path,
    *,
    tier: str,
    ffprobe_bin: str = "ffprobe",
    target_resolution: str = "1080p",
    source: str = "original",
    normalized: bool = False,
) -> dict[str, Any]:
    metadata = probe_media(path, ffprobe_bin)
    return {
        **metadata,
        "tier": tier,
        "source": source,
        "quality": quality_label(metadata, target_resolution),
        "normalized": bool(normalized),
        "is_low_res": quality_label(metadata, target_resolution) == "LOW RES SOURCE",
    }


def best_master_path(project: Any) -> Path | None:
    """Resolve only a master-derived path for export; never choose a proxy."""

    assets = getattr(project, "video_assets", {}) or {}
    master = assets.get("final_master") if isinstance(assets, dict) else None
    if isinstance(master, dict):
        path = Path(str(master.get("path") or ""))
        if path.is_file():
            return path
    fallback = Path(str(getattr(project, "final_output_placeholder", "") or ""))
    return fallback if fallback.is_file() else None


def best_screening_path(project: Any) -> Path | None:
    """Resolve a viewer copy, preferring a 720p/1080p screening asset."""

    assets = getattr(project, "video_assets", {}) or {}
    if isinstance(assets, dict):
        for key in ("screening_preview", "final_master"):
            record = assets.get(key)
            if isinstance(record, dict):
                path = Path(str(record.get("path") or ""))
                if path.is_file():
                    return path
    for candidate in (
        getattr(project, "rough_cut_placeholder", None),
        getattr(project, "final_output_placeholder", None),
    ):
        path = Path(str(candidate or ""))
        if path.is_file():
            return path
    return None


def quality_snapshot(project: Any, ffprobe_bin: str = "ffprobe") -> dict[str, Any]:
    """Build a JSON-safe quality summary for API responses and the UI."""

    target = str(getattr(project, "target_resolution", "1080p") or "1080p").lower()
    assets = dict(getattr(project, "video_assets", {}) or {})
    shots = getattr(project, "storyboard", []) or []
    low_res_source = False
    for shot in shots:
        records = getattr(shot, "media_assets", {}) or {}
        record = records.get("final_master") if isinstance(records, dict) else None
        if isinstance(record, dict) and record.get("is_low_res"):
            low_res_source = True
    snapshot: dict[str, Any] = {
        "target_resolution": target,
        "target_fps": int(getattr(project, "target_fps", 24) or 24),
        "working_proxy": assets.get("working_proxy"),
        "screening_preview": assets.get("screening_preview"),
        "final_master": assets.get("final_master"),
        "source_low_res": low_res_source,
        "upscale_available": low_res_source,
    }
    # Older project files have no manifest. Infer a source record without
    # changing the persisted JSON until the next edit/save.
    if snapshot["final_master"] is None:
        fallback = Path(str(getattr(project, "final_output_placeholder", "") or ""))
        if fallback.is_file():
            snapshot["final_master"] = asset_record(
                fallback,
                tier="final_master",
                ffprobe_bin=ffprobe_bin,
                target_resolution=target,
                source="legacy_project",
            )
    if snapshot["screening_preview"] is None:
        fallback = best_screening_path(project)
        if fallback:
            snapshot["screening_preview"] = asset_record(
                fallback,
                tier="screening_preview",
                ffprobe_bin=ffprobe_bin,
                target_resolution=target,
                source="legacy_project",
            )
    for key in ("working_proxy", "screening_preview", "final_master"):
        record = snapshot.get(key)
        if isinstance(record, dict) and record.get("is_low_res"):
            snapshot["source_low_res"] = True
            snapshot["upscale_available"] = True
    return snapshot
