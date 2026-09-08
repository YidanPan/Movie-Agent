"""Small edit-stage read helpers.

The media renderer remains ``EditorAgent`` for backwards compatibility.  The
helpers here keep status/readiness decisions out of HTTP handlers and provide a
safe seam for a future background edit worker.
"""

from __future__ import annotations

from typing import Any

from movie_agent.services.audio import apply_audio_track_params, ensure_audio_design
from movie_agent.services.audio import EDIT_AUDIO_STAGES, mark_audio_stage
from movie_agent.services.errors import clear_failure
from movie_agent.services.readiness import ensure_action_ready
from movie_agent.pipeline.rendering import invalidate_edit_outputs, require_dialogue_locked, shots_ready


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

    def __init__(
        self,
        editor: Any,
        voice_service: Any,
        *,
        settings: Any | None = None,
        persist: Any | None = None,
    ) -> None:
        self.editor = editor
        self.voice_service = voice_service
        self.settings = settings
        self.persist = persist

    def _save(self, project: Any) -> None:
        if self.persist is not None:
            self.persist(project)

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

    def create_rough_cut(
        self,
        project: Any,
        progress_callback: Any | None = None,
        *,
        music_mode: str | None = None,
        smart_ducking: bool | None = None,
        music_asset_name: str | None = None,
        music_intensity: float | None = None,
        track_enabled: dict[str, bool] | None = None,
        track_params: dict[str, dict[str, Any]] | None = None,
    ) -> Any:
        """Run the complete edit handoff through a resumable Rough Cut."""

        if self.settings is None:
            raise RuntimeError("EditPipeline requires settings for Rough Cut creation.")
        ensure_action_ready(project, self.settings, "START_AI_EDIT")
        clear_failure(project)
        require_dialogue_locked(project)
        if not shots_ready(project):
            raise ValueError("All shots must pass QC before AI Edit can start.")
        if str(project.status).startswith("completed"):
            invalidate_edit_outputs(project, reason="recut_requested", source="rough_cut")
        media_status, voice_result = self.prepare_media_and_audio(
            project,
            music_mode=music_mode,
            smart_ducking=smart_ducking,
            music_asset_name=music_asset_name,
            music_intensity=music_intensity,
            track_enabled=track_enabled,
            track_params=track_params,
        )
        project.logs.append(f"Media Pipeline: {media_status}.")
        project.mix_state["media_mixed"] = False
        project.mix_state["stage_status"] = {stage: "queued" for stage in EDIT_AUDIO_STAGES}
        project.mix_state["active_stage"] = "picture_cut"
        project.status = "editing_rough_cut"
        project.logs.append(
            f"Editor Agent: Starting AI Edit with locked dialogue book and subtitle track; sound mode is {project.music_mode.upper()}."
        )
        self._save(project)
        mark_audio_stage(project, "picture_cut", "working")
        self._save(project)
        if progress_callback:
            progress_callback("Picture Cut: Ordering shots and computing Trim / transitions.")
        mark_audio_stage(project, "picture_cut", "done")
        mark_audio_stage(project, "voice", "working")
        self._save(project)
        project.logs.append("Editor Agent: Shot order, Trim, and transitions complete.")
        if progress_callback:
            progress_callback("Voice: Wiring locked narration and Dialogue Book.")
        if voice_result.media_path:
            project.logs.append(
                f"Voice Agent: Continuous English voice ready ({voice_result.duration_seconds:.2f}s measured; subtitle timing aligned)."
            )
        else:
            project.logs.append(
                f"Voice Agent: Continuous English voice pending provider ({voice_result.error or 'no media renderer configured'})."
            )
        self._save(project)
        mark_audio_stage(project, "voice", "done")
        mark_audio_stage(project, "music", "working")
        self._save(project)
        project.logs.append("Sound Design Agent: Voice track wired to locked dialogue book.")
        if progress_callback:
            progress_callback("Music: Generating Music Brief and Emotional Arc.")
        mark_audio_stage(project, "music", "done")
        mark_audio_stage(project, "sfx", "working")
        self._save(project)
        project.logs.append(
            f"Sound Design Agent: Music Brief ready ({project.music_brief.get('bpm', 0)} BPM, peak {project.music_brief.get('peak_seconds', 0)}s)."
        )
        if progress_callback:
            progress_callback("SFX: Placing action sound effects and ambience.")
        mark_audio_stage(project, "sfx", "done")
        mark_audio_stage(project, "subtitles", "working")
        self._save(project)
        project.logs.append("Sound Design Agent: SFX and Ambience tracks built from shot sound design cues.")
        if progress_callback:
            progress_callback("Subtitles: Wiring locked Subtitle Track.")
        mark_audio_stage(project, "subtitles", "done")
        mark_audio_stage(project, "mix", "working")
        self._save(project)
        project.logs.append(
            "Editor Agent: Subtitle Track wired to the locked English Dialogue Book; awaiting final output mode."
        )
        if progress_callback:
            progress_callback("Mix: Smart Ducking and four-track mixing in progress.")
        mark_audio_stage(project, "mix", "done")
        mark_audio_stage(project, "final_encode", "working")
        project.mix_state["active_stage"] = "final_encode"
        project.mix_state["status"] = "MIX COMPLETE · ROUGH CUT ENCODING"
        project.logs.append(
            f"Mix Agent: Smart Ducking {'ON' if project.smart_ducking.get('enabled') else 'OFF'}, Music duck {project.smart_ducking.get('amount_db', -8)} dB."
        )
        self._save(project)
        project.logs.append(self.editor.create_rough_cut(project))
        mark_audio_stage(project, "final_encode", "done")
        project.mix_state["active_stage"] = "final_encode"
        project.mix_state["status"] = "ROUGH CUT READY"
        project.status = "rough_cut_ready"
        project.logs.append("Editor Agent: Rough Cut complete. Preview sound design, re-edit, or approve final cut.")
        self._save(project)
        return project

