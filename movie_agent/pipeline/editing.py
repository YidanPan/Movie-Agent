"""Small edit-stage read helpers.

The media renderer remains ``EditorAgent`` for backwards compatibility.  The
helpers here keep status/readiness decisions out of HTTP handlers and provide a
safe seam for a future background edit worker.
"""

from __future__ import annotations

from typing import Any

from movie_agent.services.audio import apply_audio_track_params, ensure_audio_design


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


class EditPipeline:
    """Own the media-preparation and sound-design handoff into the editor."""

    def __init__(self, editor: Any, voice_service: Any) -> None:
        self.editor = editor
        self.voice_service = voice_service

    def prepare_media_and_audio(
        self,
        project: Any,
        *,
        music_mode: str | None = None,
        smart_ducking: bool | None = None,
        music_asset_name: str | None = None,
        music_intensity: float | None = None,
        track_enabled: dict[str, bool] | None = None,
        track_params: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[Any, Any]:
        """Prepare real media and return the media + voice results."""

        ensure_audio_design(
            project,
            music_mode=music_mode,
            smart_ducking=smart_ducking,
            music_asset_name=music_asset_name,
            music_intensity=music_intensity,
        )
        for key, enabled in (track_enabled or {}).items():
            if key in project.audio_tracks:
                project.audio_tracks[key]["enabled"] = bool(enabled)
        apply_audio_track_params(project, track_params)
        media_status = self.editor.prepare_media_for_edit(project)
        voice_result = self.voice_service.synthesize(project)
        return media_status, voice_result

