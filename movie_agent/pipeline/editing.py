"""Small edit-stage read helpers.

The media renderer remains ``EditorAgent`` for backwards compatibility.  The
helpers here keep status/readiness decisions out of HTTP handlers and provide a
safe seam for a future background edit worker.
"""

from __future__ import annotations

from typing import Any


def edit_output_exists(project: Any) -> bool:
    """Whether a rough/final edit pointer currently resolves to a value."""

    return bool(
        getattr(project, "final_output_placeholder", None)
        or getattr(project, "rough_cut_placeholder", None)
        or (getattr(project, "edit_plan", {}) or {}).get("approved")
    )


def editing_snapshot(project: Any) -> dict[str, Any]:
    """Return truthful edit readiness and stale derivative counts."""

    assets = getattr(project, "video_assets", {}) or {}
    stale_assets = sum(1 for item in assets.values() if isinstance(item, dict) and item.get("stale"))
    shots = list(getattr(project, "storyboard", []) or [])
    return {
        "status": str(getattr(project, "status", "")),
        "has_output": edit_output_exists(project),
        "stale_asset_count": stale_assets,
        "shots_ready": bool(shots) and all(
            str(getattr(shot, "status", "")).startswith("approved") and not getattr(shot, "stale", False)
            for shot in shots
        ),
    }

