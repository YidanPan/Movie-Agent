"""Small edit-stage read helpers.

The media renderer remains ``EditorAgent`` for backwards compatibility.  The
helpers here keep status/readiness decisions out of HTTP handlers and provide a
safe seam for a future background edit worker.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from movie_agent.services.audio import apply_audio_track_params, ensure_audio_design
from movie_agent.services.audio import EDIT_AUDIO_STAGES, mark_audio_media_status, mark_audio_stage
from movie_agent.services.errors import clear_failure
from movie_agent.services.final_look import normalise_final_look, reset_final_look
from movie_agent.services.readiness import ensure_action_ready
from movie_agent.services.subtitles import normalise_subtitle_mode
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
        using_creative_llm: bool = False,
    ) -> None:
        self.editor = editor
        self.voice_service = voice_service
        self.settings = settings
        self.persist = persist
        self.using_creative_llm = using_creative_llm

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
        mark_audio_media_status(project, "voice", "MEDIA_READY" if voice_result.media_path else "DEFERRED")
        for track_key in ("music", "sfx", "ambience"):
            track = (project.audio_tracks or {}).get(track_key) or {}
            mark_audio_media_status(
                project,
                track_key,
                "MEDIA_READY" if Path(str(track.get("media_path") or "")).is_file() else "PLANNED",
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

    def approve_edit(self, project: Any, subtitle_mode: str | None = None) -> Any:
        """Approve the current edit revision without rendering a master."""

        if self.settings is None:
            raise RuntimeError("EditPipeline requires settings for Final Cut approval.")
        ensure_action_ready(project, self.settings, "APPROVE_FINAL_CUT")
        require_dialogue_locked(project)
        if project.status not in {"rough_cut_ready", "editing_rough_cut"}:
            raise ValueError("Please complete the Rough Cut before approving the final cut.")
        if not shots_ready(project):
            raise ValueError("All current shot revisions must be approved before the final cut can be approved.")
        if subtitle_mode:
            project.subtitle_mode = normalise_subtitle_mode(subtitle_mode)
        project.status = "final_cut_approved"
        ensure_audio_design(project)
        reset_final_look(project)
        project.edit_plan = {
            **(project.edit_plan or {}),
            "status": "final_cut_approved",
            "approved": True,
            "approved_subtitle_mode": project.subtitle_mode,
        }
        project.mix_state["active_stage"] = None
        project.mix_state["status"] = "FINAL CUT APPROVED · MASTER PENDING"
        project.logs.append(f"Editor Agent: Final Cut approved; ready to generate a Final Master with {project.subtitle_mode} subtitles.")
        self._save(project)
        return project

    def generate_final_master(self, project: Any) -> Any:
        """Generate or recover the Final Master from an approved edit."""

        if self.settings is None:
            raise RuntimeError("EditPipeline requires settings for Final Master generation.")
        ensure_action_ready(project, self.settings, "GENERATE_FINAL_MASTER")
        require_dialogue_locked(project)
        approved = bool((project.edit_plan or {}).get("approved"))
        if not approved and project.status != "final_cut_approved" and not str(project.status).startswith("completed"):
            raise ValueError("Approve the current Final Cut before generating the Final Master.")
        if not shots_ready(project):
            raise ValueError("All current shot revisions must be approved before generating the Final Master.")
        project.status = "editing_final"
        project.mix_state["active_stage"] = "final_encode"
        project.mix_state["status"] = "FINAL MASTER GENERATION"
        self._save(project)
        try:
            if self.settings.video_generation_mode != "mock":
                project.logs.append(self.editor.assemble(project, project.subtitle_mode))
                project.status = "completed"
            else:
                project.logs.append(self.editor.assemble_mock(project))
                # Public Demo exposes one stable mock-delivery state while
                # the API still reports the real planning provider separately
                # as ``text_mode=modelscope``.  Keep the more specific legacy
                # status for private/non-demo callers.
                project.status = (
                    "completed_mock"
                    if bool(getattr(self.settings, "public_demo_mode", False)) or not self.using_creative_llm
                    else "completed_text_ai_video_mock"
                )
            project.logs.append(f"Project complete: Final Master generated from approved cut ({project.subtitle_mode}).")
            project.mix_state["status"] = "FINAL MASTER READY"
            project.mix_state["active_stage"] = None
            self._save(project)
        except Exception:
            project.status = "final_cut_approved"
            project.mix_state["status"] = "FINAL MASTER GENERATION FAILED"
            project.mix_state["active_stage"] = None
            self._save(project)
            raise
        return project

    def set_final_look(
        self,
        project: Any,
        *,
        preset: str = "original",
        intensity: float = 0.72,
        grain: float = 0.0,
        vignette: float = 0.0,
        highlight_soften: float = 0.0,
        scope: str = "whole_film",
        apply: bool = True,
    ) -> Any:
        """Save a Final Look and optionally render it onto the current cut."""

        if not str(project.status).startswith("completed"):
            raise ValueError("Please complete the final cut before entering Final Look finishing.")
        previous = normalise_final_look(project.final_look or {})
        requested = normalise_final_look(
            {
                **previous,
                "preset": preset,
                "intensity": intensity,
                "grain": grain,
                "vignette": vignette,
                "highlight_soften": highlight_soften,
                "scope": scope,
                "applied": bool(apply),
            }
        )
        changed = any(
            previous.get(key) != requested.get(key)
            for key in ("preset", "intensity", "grain", "vignette", "highlight_soften", "scope", "applied")
        )
        if changed:
            requested["revision"] = int(previous.get("revision", 1) or 1) + 1
        project.final_look = normalise_final_look(requested)
        if not apply:
            project.final_look["status"] = "PREVIEW ONLY · NOT APPLIED"

        if apply:
            current_path = Path(project.final_output_placeholder or "")
            base_path = Path(str(project.final_look.get("base_media_path") or ""))
            if not base_path.is_file() and current_path.is_file():
                base_path = current_path
                project.final_look["base_media_path"] = str(base_path)
            rendered = self.editor.apply_final_look(project, project.final_look, base_path)
            if rendered is not None and rendered.is_file():
                project.final_output_placeholder = str(rendered)
                project.final_look["media_path"] = str(rendered)
                project.final_look["status"] = normalise_final_look(project.final_look)["status"]
            elif not current_path.is_file():
                project.final_look["status"] = f"{project.final_look['english']} · EXPORT FILTER READY"
            project.logs.append(
                f"Final Look: Applied {project.final_look['english']} (intensity {project.final_look['intensity']}, scope {project.final_look['scope']})."
            )
        else:
            project.logs.append("Final Look: Browser preview draft updated; not yet applied to delivery file.")
        self._save(project)
        return project

