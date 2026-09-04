"""Coordinates the MVP planning stages and stores their output."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from movie_agent.agents.director import DirectorAgent
from movie_agent.agents.editor import EditorAgent
from movie_agent.agents.generation import GenerationAgent
from movie_agent.agents.reviewer import ReviewerAgent
from movie_agent.agents.storyboard import StoryboardAgent
from movie_agent.agents.visual_bible import VisualBibleAgent
from movie_agent.agents.writer import WriterAgent
from movie_agent.config import Settings
from movie_agent.models import MovieProject
from movie_agent.storage.project_store import ProjectStore
from movie_agent.services.llm import build_creative_llm
from movie_agent.services.quality import ContinuityQualityGate, PlanningQualityGate, SemanticCopyrightReviewer
from movie_agent.services.continuity import build_continuity_lock, ensure_continuity_lock
from movie_agent.services.audio import (
    EDIT_AUDIO_STAGES,
    apply_audio_track_params,
    ensure_audio_design,
    mark_audio_stage,
    regenerate_track,
)
from movie_agent.services.final_look import ensure_final_look, normalise_final_look, reset_final_look
from movie_agent.services.subtitles import (
    align_script_to_shots,
    ensure_dialogue_assets,
    normalise_subtitle_mode,
    shot_count_for_duration,
)


class MovieOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = ProjectStore(settings.projects_dir)
        creative_llm = build_creative_llm(settings)
        self.using_creative_llm = creative_llm is not None
        self.director = DirectorAgent(creative_llm)
        self.writer = WriterAgent(creative_llm)
        supported_modes = {"T2V"} if settings.video_generation_mode == "comfyui" else None
        self.storyboard_agent = StoryboardAgent(creative_llm, supported_modes)
        self.visual_bible_agent = VisualBibleAgent(creative_llm)
        self.generation_agent = GenerationAgent(settings)
        self.reviewer = ReviewerAgent(settings)
        self.editor = EditorAgent(settings)
        self.quality_gate = PlanningQualityGate()
        self.continuity_gate = ContinuityQualityGate()
        self.semantic_copyright_reviewer = SemanticCopyrightReviewer(creative_llm)

    def create_project(
        self,
        idea: str,
        duration: int,
        visual_style: str,
        event_callback: Callable[[dict], None] | None = None,
    ) -> MovieProject:
        def emit(event: dict) -> None:
            if event_callback is not None:
                event_callback(event)

        cleaned_idea = idea.strip()
        if len(cleaned_idea) < 10:
            raise ValueError("Please provide an original sci-fi idea of at least 10 characters.")
        if not 30 <= duration <= 80:
            raise ValueError("Current MVP supports 30-80 second target duration.")

        project_id = f"film-{uuid4().hex[:8]}"
        emit(
            {
                "type": "project",
                "project_id": project_id,
                "text_mode": "modelscope" if self.using_creative_llm else "mock",
                "video_mode": self.settings.video_generation_mode,
            }
        )
        creative_source = "ModelScope text model" if self.using_creative_llm else "mock rule engine"
        logs = [
            f"Director Agent: Creative boundaries set via {creative_source}.",
            f"Writer Agent: Screenplay, narration, dialogue book and subtitle track generated via {creative_source}.",
            f"Storyboard Agent: Individual shots split and generation modes assigned via {creative_source}.",
            f"Visual Bible Agent: Character, scene and style specs locked via {creative_source}.",
            "Generation Agent: Per-shot generation queue ready.",
            "Dialogue Book: Dialogue Book and Subtitle Track generated; awaiting user lock.",
            "Project archived: Project JSON saved; ready for review, AI Edit, or export.",
        ]
        emit({"type": "agent_start", "agent": "director"})
        emit(
            {
                "type": "artifact",
                "agent": "director",
                "title": "Creative Breakdown",
                "content": "Extracting core imagery, conflict object, and the emotion the audience should feel in the last second.",
            }
        )
        emit(
            {
                "type": "chat",
                "from": "director",
                "to": "writer",
                "message": "I'll lock down an expressible conflict first; the writer will flesh out the character's choice once they receive the brief.",
            }
        )
        brief = self.director.plan(cleaned_idea, duration, visual_style)
        emit({"type": "agent_done", "agent": "director", "brief": brief})
        emit(
            {
                "type": "artifact",
                "agent": "director",
                "title": "Director's Note",
                "content": (
                    f"Core imagery: {brief.get('theme', 'solitude and automation')}."
                    "The audience should only realise in the last second what the protagonist's choice really means."
                ),
            }
        )
        emit(
            {
                "type": "chat",
                "from": "director",
                "to": "writer",
                "message": (
                    "The core conflict in this idea is clear. I'd suggest focusing on the protagonist's inner turn — "
                    "don't over-explain the world-building; let the audience feel it through the action."
                ),
            }
        )
        emit({"type": "agent_start", "agent": "writer"})
        emit(
            {
                "type": "artifact",
                "agent": "writer",
                "title": "Conflict Draft",
                "content": "Compressing the world into one character, one anomaly, and one irreversible choice.",
            }
        )
        planned_shot_count = shot_count_for_duration(duration)
        script = self.writer.write(
            cleaned_idea,
            brief,
            duration_seconds=duration,
            shot_count=planned_shot_count,
        )
        script["film_language"] = self.settings.film_language
        emit({"type": "agent_done", "agent": "writer", "script": script})
        emit(
            {
                "type": "artifact",
                "agent": "writer",
                "title": "Dialogue Book / Subtitle Draft",
                "content": (
                    f"Generated Dialogue Book and Subtitle Track for {planned_shot_count} shots. "
                    "Please review, edit, and lock in the production handbook."
                ),
            }
        )
        if script.get("outline"):
            emit(
                {
                    "type": "artifact",
                    "agent": "writer",
                    "title": "Story Outline",
                    "content": script["outline"],
                }
            )
        emit({"type": "agent_start", "agent": "story_beats"})
        emit(
            {
                "type": "artifact",
                "agent": "story_beats",
                "title": "Narrative Structure",
                "content": f"Breaking the screenplay into {planned_shot_count} narrative beats for cross-shot continuity.",
            }
        )
        story_beats = self.writer.generate_story_beats(cleaned_idea, brief, script, duration)
        emit({"type": "agent_done", "agent": "story_beats", "story_beats": story_beats})
        emit(
            {
                "type": "artifact",
                "agent": "story_beats",
                "title": "Beat Map",
                "content": (
                    f"{len(story_beats)} narrative beats locked. "
                    + " → ".join(beat.get("narrative_purpose", f"beat {i+1}") for i, beat in enumerate(story_beats))
                ),
            }
        )
        emit(
            {
                "type": "chat",
                "from": "writer",
                "to": "visual_bible",
                "message": (
                    "The story needs a restrained but warm visual tone. "
                    "The protagonist's space should contrast aged metal with warm tungsten light."
                ),
            }
        )
        emit({"type": "agent_start", "agent": "visual_bible"})
        emit(
            {
                "type": "artifact",
                "agent": "visual_bible",
                "title": "Material Samples",
                "content": "Aged metal, glass reflections, and a single warm light source enter the visual candidates; awaiting script confirmation of emotional direction.",
            }
        )
        visual_bible = self.visual_bible_agent.create(visual_style, brief, script)
        continuity_lock = build_continuity_lock(visual_bible, self.settings.film_language)
        emit({"type": "agent_done", "agent": "visual_bible", "visual_bible": visual_bible})
        emit(
            {
                "type": "artifact",
                "agent": "visual_bible",
                "title": "Mood Board",
                "content": (
                    f"{visual_style}-led. Aged metal, tungsten lamps, cool grey walls; "
                    "the only warm source is the device in the protagonist's hand."
                ),
            }
        )
        emit(
            {
                "type": "chat",
                "from": "visual_bible",
                "to": "storyboard",
                "message": (
                    "I'd suggest locking off the camera for the first three shots, "
                    "saving the slow dolly for the final turn — so movement earns its meaning."
                ),
            }
        )
        emit({"type": "agent_start", "agent": "storyboard"})
        emit(
            {
                "type": "artifact",
                "agent": "storyboard",
                "title": "Camera Sketches",
                "content": "Static shots establish order first; camera movement is reserved for the key turning point to avoid showing off in every frame.",
            }
        )
        storyboard = self.storyboard_agent.create(
            cleaned_idea, duration, visual_style, project_id, brief, script, visual_bible,
            story_beats=story_beats,
        )
        script = align_script_to_shots(script, storyboard)
        emit(
            {
                "type": "agent_done",
                "agent": "storyboard",
                "storyboard": [shot.to_dict() for shot in storyboard],
            }
        )
        emit(
            {
                "type": "artifact",
                "agent": "storyboard",
                "title": "Shot Rhythm",
                "content": (
                    f"{len(storyboard)} shots: static-static-static-dynamic-static; "
                    f"final shot holds {storyboard[-1].duration_seconds if storyboard else 4}s of silence."
                ),
            }
        )
        emit(
            {
                "type": "chat",
                "from": "storyboard",
                "to": "director",
                "message": (
                    f"{len(storyboard)} shots cover the full narrative arc. "
                    "Should we reserve a backup shot in case the pacing feels too fast?"
                ),
            }
        )
        emit({"type": "agent_start", "agent": "quality"})
        emit(
            {
                "type": "artifact",
                "agent": "quality",
                "title": "Pre-Flight Scan",
                "content": "Checking duration, shot count, prompt completeness, and potential copyright proximity in parallel.",
            }
        )
        quality_report = self.quality_gate.review(
            duration_seconds=duration,
            script=script,
            visual_bible=visual_bible,
            storyboard=storyboard,
        )
        quality_report.extend(
            self.semantic_copyright_reviewer.review(
                idea=cleaned_idea,
                script=script,
                visual_bible=visual_bible,
                storyboard=storyboard,
            )
        )
        continuity_report = self.continuity_gate.review(
            visual_bible=visual_bible,
            storyboard=storyboard,
            continuity_lock=continuity_lock,
        )
        quality_report.extend(continuity_report)
        emit({"type": "agent_done", "agent": "quality", "quality_report": quality_report})
        emit(
            {
                "type": "chat",
                "from": "quality",
                "to": "all",
                "message": (
                    "Script and visual descriptions have passed copyright review; all elements are original. "
                    f"{len(quality_report)} items flagged for attention."
                ),
            }
        )
        project = MovieProject(
            project_id=project_id,
            idea=cleaned_idea,
            duration_seconds=duration,
            visual_style=visual_style,
            status="planned_text_ai" if self.using_creative_llm else "planned_mock",
            brief=brief,
            script=script,
            visual_bible=visual_bible,
            storyboard=storyboard,
            quality_report=quality_report,
            logs=logs + quality_report,
            story_beats=story_beats,
            film_language=self.settings.film_language,
            continuity_lock=continuity_lock,
            voice_profile={
                "voice_id": self.settings.tts_voice,
                "accent": self.settings.tts_voice.rsplit("-", 1)[0] if "-" in self.settings.tts_voice else "en-US",
                "speaking_rate": 1.0,
                "voice_style": "restrained cinematic narration",
                "strategy": "continuous_voice_track",
            },
        )
        # Prepare the sound department as soon as the shot rhythm exists. The
        # brief is reviewable before AI Edit, while actual media remains a
        # later renderer concern.
        ensure_audio_design(project)
        ensure_final_look(project)
        project.logs.extend(
            [
                "Sound Design Agent: Music Brief and Emotional Arc generated; awaiting AI Edit to wire up four tracks.",
                "Sound Design Agent: Voice / Music / SFX / Ambience tracks established; Smart Ducking enabled by default.",
                "Final Look: Final Look console will open after the final cut; defaults to whole-film scope.",
            ]
        )
        self.store.save(project)
        emit({"type": "archived", "project_id": project_id})
        if self.settings.video_generation_mode == "comfyui":
            project.status = "ready_for_comfyui_render"
            project.logs.append("Generation Agent: Project is ready. Click 'Spark Real Generate' to submit per-shot tasks.")
            self.store.save(project)
            return project
        return self.run_mock_production(project_id, event_callback)

    def run_mock_production(
        self,
        project_id: str,
        event_callback: Callable[[dict], None] | None = None,
    ) -> MovieProject:
        """Simulate the state flow that will later call ComfyUI and FFmpeg."""

        def emit(event: dict) -> None:
            if event_callback is not None:
                event_callback(event)

        project = self.store.load(project_id)
        project.status = "generating_video_mock"
        project.logs.append("Generation Agent: Starting mock shot task queue submission.")
        emit({"type": "agent_start", "agent": "generation"})
        for shot in project.storyboard:
            project.logs.append(self.generation_agent.generate_mock(shot))
            emit({"type": "shot_update", "shot": shot.to_dict()})
            project.logs.append(self.reviewer.review_mock(shot))
            emit({"type": "shot_update", "shot": shot.to_dict()})
            # Keep the mock path resumable too: a refresh during the staged
            # reveal should not discard completed shot states.
            self.store.save(project)
        emit({"type": "agent_done", "agent": "generation"})

        project.status = "ready_for_ai_edit"
        project.logs.append(f"Generation Agent: {len(project.storyboard)}/{len(project.storyboard)} SHOTS READY; stage advanced to DELIVER.")
        project.logs.append("Editor Agent: Awaiting user dialogue lock before starting AI Edit Rough Cut.")
        self.store.save(project)
        return project

    def render_project(
        self,
        project_id: str,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> MovieProject:
        if self.settings.video_generation_mode != "comfyui":
            raise ValueError("Current mode is mock. Set VIDEO_GENERATION_MODE=comfyui in Spark's .env before rendering.")
        project = self.store.load(project_id)
        self._require_dialogue_locked(project)
        ensure_continuity_lock(project)
        self.continuity_gate.review(
            visual_bible=project.visual_bible,
            storyboard=project.storyboard,
            continuity_lock=project.continuity_lock,
        )
        unsupported_modes = sorted(
            {shot.generation_mode for shot in project.storyboard if shot.generation_mode != "T2V"}
        )
        if unsupported_modes:
            modes = ", ".join(unsupported_modes)
            raise ValueError(
                f"Spark's verified workflow only supports T2V; project still has {modes} shots. "
                "Please re-plan those shots before submitting for real generation."
            )
        project.status = "rendering_comfyui"
        project.final_output_placeholder = None
        project.rough_cut_placeholder = None
        project.video_assets = {}
        project.edit_plan = {}
        project.logs.append("Generation Agent: Submitting Spark ComfyUI per-shot tasks.")
        self.store.save(project)
        total_shots = len(project.storyboard)
        for index, shot in enumerate(project.storyboard, start=1):
            if shot.status == "approved_comfyui" and Path(shot.output_placeholder).is_file():
                project.logs.append(f"Generation Agent: Shot {shot.number} already complete; skipping on resume.")
                if progress_callback:
                    progress_callback(index, total_shots, f"Shot {shot.number} already complete; skipping")
                continue
            last_error: Exception | None = None
            previous_shot = project.storyboard[index - 2] if index > 1 else None
            for attempt in range(1, self.settings.comfy_max_retries + 1):
                try:
                    project.logs.append(self.generation_agent.generate(
                        project.project_id, shot,
                        visual_bible=project.visual_bible,
                        previous_shot=previous_shot,
                        target_resolution=project.target_resolution,
                    ))
                    project.logs.append(
                        self.reviewer.review_generated(
                            shot,
                            project_id=project.project_id,
                            visual_bible=project.visual_bible,
                        )
                    )
                    self.store.save(project)
                    if progress_callback:
                        progress_callback(index, total_shots, f"Shot {shot.number} generated and passed full QC")
                    last_error = None
                    break
                except Exception as error:
                    last_error = error
                    project.logs.append(
                        f"Generation Agent: Shot {shot.number} attempt {attempt}/{self.settings.comfy_max_retries} failed: {error}"
                    )
                    self.store.save(project)
            if last_error is not None:
                project.status = "render_failed"
                project.logs.append("Generation Agent: You can click the real generate button again to resume from incomplete shots.")
                self.store.save(project)
                raise RuntimeError(f"Shot {shot.number} failed after multiple attempts: {last_error}") from last_error

        project.status = "ready_for_ai_edit"
        project.logs.append(f"Generation Agent: {len(project.storyboard)}/{len(project.storyboard)} SHOTS READY; stage advanced to DELIVER.")
        project.logs.append("Editor Agent: Awaiting user to start AI Edit; Rough Cut first, then approve final cut.")
        self.store.save(project)
        if progress_callback:
            progress_callback(
                total_shots,
                total_shots,
                f"{total_shots}/{total_shots} SHOTS READY · Awaiting AI Edit",
            )
        return project

    def render_shot(self, project_id: str, shot_number: int) -> MovieProject:
        """Regenerate one shot from the Inspector without assembling the full film."""
        if self.settings.video_generation_mode != "comfyui":
            raise ValueError("Current mode is mock. Set VIDEO_GENERATION_MODE=comfyui in Spark's .env before generating shots.")
        project = self.store.load(project_id)
        if not 1 <= shot_number <= len(project.storyboard):
            raise ValueError(f"Shot number must be between 1 and {len(project.storyboard)}.")
        shot = project.storyboard[shot_number - 1]
        ensure_continuity_lock(project)
        if shot.generation_mode != "T2V":
            raise ValueError(
                f"Shot {shot.number} is marked as {shot.generation_mode}, but the current MiniMax-H3 workflow only supports T2V."
            )

        shot.status = "replanned"
        project.status = "rendering_comfyui"
        project.final_output_placeholder = None
        project.rough_cut_placeholder = None
        project.video_assets = {}
        project.edit_plan = {}
        project.logs.append(f"Generation Agent: Inspector submitted shot {shot_number} for single-shot regeneration.")
        self.store.save(project)
        previous_shot = project.storyboard[shot_number - 2] if shot_number > 1 else None
        try:
            project.logs.append(self.generation_agent.generate(
                project.project_id, shot,
                visual_bible=project.visual_bible,
                previous_shot=previous_shot,
                target_resolution=project.target_resolution,
            ))
            project.logs.append(
                self.reviewer.review_generated(
                    shot,
                    project_id=project.project_id,
                    visual_bible=project.visual_bible,
                )
            )
        except Exception as error:
            project.status = "render_failed"
            project.logs.append(f"Generation Agent: Shot {shot_number} single-shot generation failed: {error}")
            self.store.save(project)
            raise

        project.status = (
            "ready_for_ai_edit"
            if all(str(item.status).startswith("approved") for item in project.storyboard)
            else "ready_for_comfyui_render"
        )
        project.logs.append(f"QC Agent: Shot {shot_number} passed single-shot inspection; ready to continue assembling the full film.")
        self.store.save(project)
        return project

    @staticmethod
    def _require_dialogue_locked(project: MovieProject) -> None:
        if not bool((project.script or {}).get("dialogue_locked")):
            raise ValueError("Please review and lock the dialogue book / subtitle track in the writing stage first.")

    @staticmethod
    def _invalidate_edit_outputs(project: MovieProject) -> None:
        """Drop stale rough/final media whenever an upstream asset changes."""

        project.final_output_placeholder = None
        project.rough_cut_placeholder = None
        project.video_assets = {}
        project.edit_plan = {}
        reset_final_look(project)
        shots_ready = bool(project.storyboard) and all(
            str(shot.status).startswith("approved") for shot in project.storyboard
        )
        if shots_ready:
            project.status = "ready_for_ai_edit"
        elif str(project.status).startswith("completed"):
            project.status = "ready_for_comfyui_render"

    def update_dialogue(
        self,
        project_id: str,
        *,
        dialogue_book: list[dict],
        subtitle_track: list[dict] | None = None,
    ) -> MovieProject:
        project = self.store.load(project_id)
        if bool((project.script or {}).get("dialogue_locked")):
            raise ValueError("Dialogue book is locked. To make changes, unlock the current version first.")
        script = ensure_dialogue_assets(
            {
                **project.script,
                "dialogue_book": dialogue_book,
                "subtitle_track": subtitle_track if subtitle_track else dialogue_book,
            },
            duration_seconds=project.duration_seconds,
            shot_count=len(project.storyboard) or None,
        )
        script["dialogue_revision"] = int(script.get("dialogue_revision", 1)) + 1
        project.script = align_script_to_shots(script, project.storyboard)
        self._invalidate_edit_outputs(project)
        ensure_audio_design(project)
        project.logs.append("Script Supervisor: Saved dialogue book and subtitle track draft; not yet locked.")
        self.store.save(project)
        return project

    def lock_dialogue(self, project_id: str) -> MovieProject:
        project = self.store.load(project_id)
        # Do not silently lock a brand-new empty payload that the normaliser
        # would otherwise turn into placeholder lines.
        if not (project.script or {}).get("dialogue_book") or not (project.script or {}).get("subtitle_track"):
            raise ValueError("Dialogue book or subtitle track is empty; cannot lock.")
        project.script = ensure_dialogue_assets(
            project.script,
            duration_seconds=project.duration_seconds,
            shot_count=len(project.storyboard) or None,
        )
        if not project.script.get("dialogue_book") or not project.script.get("subtitle_track"):
            raise ValueError("Dialogue book or subtitle track is empty; cannot lock.")
        project.script["dialogue_locked"] = True
        ensure_audio_design(project)
        project.logs.append(
            f"Script Supervisor: Locked dialogue book / subtitle track revision {project.script.get('dialogue_revision', 1)}. All dubbing, subtitles, and editing will use this version."
        )
        self.store.save(project)
        return project

    def unlock_dialogue(self, project_id: str) -> MovieProject:
        """Allow an explicit revision pass and invalidate downstream edits."""

        project = self.store.load(project_id)
        if not bool((project.script or {}).get("dialogue_locked")):
            return project
        project.script["dialogue_locked"] = False
        self._invalidate_edit_outputs(project)
        ensure_audio_design(project)
        project.logs.append("Script Supervisor: Dialogue book unlocked; edits allowed, then re-review and re-lock.")
        self.store.save(project)
        return project

    def set_subtitle_mode(self, project_id: str, mode: str) -> MovieProject:
        project = self.store.load(project_id)
        project.subtitle_mode = normalise_subtitle_mode(mode)
        project.script["subtitle_mode"] = project.subtitle_mode
        self.store.save(project)
        return project

    def update_shot_timing(
        self,
        project_id: str,
        shot_number: int,
        *,
        desired_duration: float | None = None,
        timing_mode: str | None = None,
    ) -> MovieProject:
        """Edit the editorial timeline without changing native shot renders.

        ``source_duration_seconds`` remains the ComfyUI generation target;
        ``duration_seconds`` is the current cut length. The distinction makes
        trim/extend/hold/slow-motion reversible and keeps the continuity lock
        intact.
        """

        project = self.store.load(project_id)
        if not 1 <= shot_number <= len(project.storyboard):
            raise ValueError(f"Shot number must be between 1 and {len(project.storyboard)}.")
        shot = project.storyboard[shot_number - 1]
        mode = str(timing_mode or shot.timing_mode or "native").strip().lower()
        aliases = {"hold": "hold_last_frame", "slow": "slow_motion", "normal": "native"}
        mode = aliases.get(mode, mode)
        if mode not in {"native", "trim", "extend", "hold_last_frame", "slow_motion"}:
            raise ValueError("Timing mode must be native, trim, extend, hold_last_frame, or slow_motion.")
        requested = shot.duration_seconds if desired_duration is None else float(desired_duration)
        if not 1 <= requested <= 80:
            raise ValueError("Desired shot duration must be between 1 and 80 seconds.")
        # Keep a native render duration for ComfyUI while allowing editorial
        # changes to exceed the 4–8 second generation window.
        shot.duration_seconds = max(1, int(round(requested)))
        shot.desired_duration = float(shot.duration_seconds)
        shot.timing_mode = mode
        project.duration_seconds = sum(int(item.duration_seconds) for item in project.storyboard)
        project.brief["target_duration"] = f"{project.duration_seconds} seconds"
        project.script = align_script_to_shots(project.script, project.storyboard)
        ensure_audio_design(project)
        self._invalidate_edit_outputs(project)
        project.status = "ready_for_ai_edit" if all(
            str(item.status).startswith("approved") for item in project.storyboard
        ) else "ready_for_comfyui_render"
        project.logs.append(
            f"Editor Agent: Shot {shot_number} timing updated to {shot.duration_seconds}s ({mode.upper()}); downstream cut invalidated."
        )
        self.store.save(project)
        return project

    def create_rough_cut(
        self,
        project_id: str,
        progress_callback: Callable[[str], None] | None = None,
        *,
        music_mode: str | None = None,
        smart_ducking: bool | None = None,
        music_asset_name: str | None = None,
        music_intensity: float | None = None,
        track_enabled: dict[str, bool] | None = None,
        track_params: dict[str, dict[str, Any]] | None = None,
    ) -> MovieProject:
        project = self.store.load(project_id)
        self._require_dialogue_locked(project)
        if not project.storyboard or not all(str(shot.status).startswith("approved") for shot in project.storyboard):
            raise ValueError("All shots must pass QC before AI Edit can start.")
        # A completed cut can be sent back through AI Edit for a new rough cut
        # without touching the locked dialogue or regenerating shots.
        if str(project.status).startswith("completed"):
            project.final_output_placeholder = None
            project.video_assets = {}
            project.edit_plan = {}
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
        project.mix_state["media_mixed"] = False
        project.mix_state["stage_status"] = {stage: "queued" for stage in EDIT_AUDIO_STAGES}
        project.mix_state["active_stage"] = "picture_cut"
        project.status = "editing_rough_cut"
        project.logs.append(
            f"Editor Agent: Starting AI Edit with locked dialogue book and subtitle track; sound mode is {project.music_mode.upper()}."
        )
        self.store.save(project)
        mark_audio_stage(project, "picture_cut", "working")
        self.store.save(project)
        if progress_callback:
            progress_callback("Picture Cut: Ordering shots and computing Trim / transitions.")
        mark_audio_stage(project, "picture_cut", "done")
        mark_audio_stage(project, "voice", "working")
        self.store.save(project)
        project.logs.append("Editor Agent: Shot order, Trim, and transitions complete.")
        if progress_callback:
            progress_callback("Voice: Wiring locked narration and Dialogue Book.")
        mark_audio_stage(project, "voice", "done")
        mark_audio_stage(project, "music", "working")
        self.store.save(project)
        project.logs.append("Sound Design Agent: Voice track wired to locked dialogue book.")
        if progress_callback:
            progress_callback("Music: Generating Music Brief and Emotional Arc.")
        mark_audio_stage(project, "music", "done")
        mark_audio_stage(project, "sfx", "working")
        self.store.save(project)
        project.logs.append(
            f"Sound Design Agent: Music Brief ready ({project.music_brief.get('bpm', 0)} BPM, peak {project.music_brief.get('peak_seconds', 0)}s)."
        )
        if progress_callback:
            progress_callback("SFX: Placing action sound effects and ambience.")
        mark_audio_stage(project, "sfx", "done")
        mark_audio_stage(project, "subtitles", "working")
        self.store.save(project)
        project.logs.append("Sound Design Agent: SFX and Ambience tracks built from shot sound design cues.")
        if progress_callback:
            progress_callback("Subtitles: Wiring locked Subtitle Track.")
        mark_audio_stage(project, "subtitles", "done")
        mark_audio_stage(project, "mix", "working")
        self.store.save(project)
        project.logs.append("Editor Agent: Subtitle Track wired; awaiting final output mode.")
        if progress_callback:
            progress_callback("Mix: Smart Ducking and four-track mixing in progress.")
        mark_audio_stage(project, "mix", "done")
        mark_audio_stage(project, "final_encode", "working")
        project.mix_state["active_stage"] = "final_encode"
        project.mix_state["status"] = "MIX COMPLETE · ROUGH CUT ENCODING"
        project.logs.append(
            f"Mix Agent: Smart Ducking {'ON' if project.smart_ducking.get('enabled') else 'OFF'}, Music duck {project.smart_ducking.get('amount_db', -8)} dB."
        )
        self.store.save(project)
        project.logs.append(self.editor.create_rough_cut(project))
        mark_audio_stage(project, "final_encode", "done")
        project.mix_state["active_stage"] = "final_encode"
        project.mix_state["status"] = "ROUGH CUT READY"
        project.status = "rough_cut_ready"
        project.logs.append("Editor Agent: Rough Cut complete. Preview sound design, re-edit, or approve final cut.")
        self.store.save(project)
        return project

    def normalize_resolution(self, project_id: str, resolution: str = "1080p") -> MovieProject:
        """Opt-in source normalization before AI Edit / Final Cut."""

        project = self.store.load(project_id)
        if not project.storyboard or not all(str(shot.status).startswith("approved") for shot in project.storyboard):
            raise ValueError("All shots must pass QC before Resolution Normalize can run.")
        self.editor.normalize_resolution(project, resolution)
        if project.status not in {"ready_for_ai_edit", "ready_for_comfyui_render"}:
            project.status = "ready_for_ai_edit"
        self.store.save(project)
        return project

    def set_audio_design(
        self,
        project_id: str,
        *,
        music_mode: str | None = None,
        smart_ducking: bool | None = None,
        music_asset_name: str | None = None,
        music_intensity: float | None = None,
        track_enabled: dict[str, bool] | None = None,
        track_params: dict[str, dict[str, Any]] | None = None,
    ) -> MovieProject:
        """Persist sound-department choices without starting an edit render."""

        project = self.store.load(project_id)
        before_config = {
            "music_mode": project.music_mode,
            "music_intensity": project.music_intensity,
            "music_asset_name": project.music_asset_name,
            "smart_ducking": bool((project.smart_ducking or {}).get("enabled", True)),
        }
        before_config["track_enabled"] = {
            key: (project.audio_tracks or {}).get(key, {}).get("enabled", True)
            for key in ("voice", "music", "sfx", "ambience")
        }
        before_config["track_params"] = {
            key: {
                "volume_db": (project.audio_tracks or {}).get(key, {}).get("volume_db"),
                "pan": (project.audio_tracks or {}).get(key, {}).get("pan", 0),
                "ducking": (project.audio_tracks or {}).get(key, {}).get("ducking", key == "music"),
            }
            for key in ("voice", "music", "sfx", "ambience")
        }
        had_edit_output = bool(
            project.final_output_placeholder
            or project.rough_cut_placeholder
            or (project.edit_plan or {}).get("approved")
            or project.status in {"editing_rough_cut", "rough_cut_ready", "editing_final"}
            or str(project.status).startswith("completed")
        )
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
        after_config = {
            "music_mode": project.music_mode,
            "music_intensity": project.music_intensity,
            "music_asset_name": project.music_asset_name,
            "smart_ducking": bool((project.smart_ducking or {}).get("enabled", True)),
            "track_enabled": {
                key: (project.audio_tracks or {}).get(key, {}).get("enabled", True)
                for key in ("voice", "music", "sfx", "ambience")
            },
            "track_params": {
                key: {
                    "volume_db": (project.audio_tracks or {}).get(key, {}).get("volume_db"),
                    "pan": (project.audio_tracks or {}).get(key, {}).get("pan", 0),
                    "ducking": (project.audio_tracks or {}).get(key, {}).get("ducking", key == "music"),
                }
                for key in ("voice", "music", "sfx", "ambience")
            },
        }
        project.mix_state["media_mixed"] = False
        if had_edit_output and before_config != after_config:
            self._invalidate_edit_outputs(project)
            project.mix_state["stage_status"] = {stage: "queued" for stage in EDIT_AUDIO_STAGES}
            project.mix_state["active_stage"] = None
            project.mix_state["status"] = "DESIGN UPDATED · RE-CUT REQUIRED"
        project.logs.append(
            f"Sound Design Agent: Configuration updated (Music={project.music_mode.upper()} · Smart Ducking={'ON' if project.smart_ducking.get('enabled') else 'OFF'})."
        )
        self.store.save(project)
        return project

    def regenerate_audio_track(self, project_id: str, track_key: str) -> MovieProject:
        """Regenerate one sound track's plan while preserving user controls."""

        project = self.store.load(project_id)
        had_edit_output = bool(
            project.final_output_placeholder
            or project.rough_cut_placeholder
            or (project.edit_plan or {}).get("approved")
            or project.status in {"editing_rough_cut", "rough_cut_ready", "editing_final"}
            or str(project.status).startswith("completed")
        )
        regenerate_track(project, track_key)
        if had_edit_output:
            self._invalidate_edit_outputs(project)
            project.mix_state["stage_status"] = {stage: "queued" for stage in EDIT_AUDIO_STAGES}
            project.mix_state["active_stage"] = None
            project.mix_state["status"] = "DESIGN UPDATED · RE-CUT REQUIRED"
        project.logs.append(f"Sound Design Agent: {track_key.upper()} track re-planned.")
        self.store.save(project)
        return project

    def approve_edit(self, project_id: str, subtitle_mode: str | None = None) -> MovieProject:
        project = self.store.load(project_id)
        self._require_dialogue_locked(project)
        if project.status not in {"rough_cut_ready", "editing_rough_cut"}:
            raise ValueError("Please complete the Rough Cut before approving the final cut.")
        if subtitle_mode:
            project.subtitle_mode = normalise_subtitle_mode(subtitle_mode)
        project.status = "editing_final"
        ensure_audio_design(project)
        reset_final_look(project)
        project.mix_state["active_stage"] = "final_encode"
        project.mix_state["status"] = "FINAL ENCODE"
        project.logs.append(f"Editor Agent: Final approval received; exporting with {project.subtitle_mode} subtitle mode.")
        self.store.save(project)
        if self.settings.video_generation_mode == "comfyui":
            project.logs.append(self.editor.assemble(project, project.subtitle_mode))
            project.status = "completed_comfyui"
        else:
            project.logs.append(self.editor.assemble_mock(project))
            project.status = "completed_text_ai_video_mock" if self.using_creative_llm else "completed_mock"
        project.logs.append(f"Project complete: Final cut approved; delivery mode is {project.subtitle_mode}.")
        project.mix_state["status"] = "FINAL MIX READY"
        project.mix_state["active_stage"] = None
        self.store.save(project)
        return project

    def set_final_look(
        self,
        project_id: str,
        *,
        preset: str = "original",
        intensity: float = 0.72,
        grain: float = 0.0,
        vignette: float = 0.0,
        highlight_soften: float = 0.0,
        scope: str = "whole_film",
        apply: bool = True,
    ) -> MovieProject:
        """Save a Final Look and optionally render it onto the real Final Cut."""

        project = self.store.load(project_id)
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
        self.store.save(project)
        return project

    def regenerate_shot(self, project_id: str, shot_number: int) -> MovieProject:
        project = self.store.load(project_id)
        if not 1 <= shot_number <= len(project.storyboard):
            raise ValueError(f"Shot number must be between 1 and {len(project.storyboard)}.")
        index = shot_number - 1
        previous_shot = project.storyboard[index - 1] if index > 0 else None
        project.storyboard[index] = self.storyboard_agent.revise(
            project.storyboard[index], project.visual_bible, previous_shot=previous_shot
        )
        project.quality_report = self.quality_gate.review(
            duration_seconds=project.duration_seconds,
            script=project.script,
            visual_bible=project.visual_bible,
            storyboard=project.storyboard,
        )
        project.quality_report.extend(
            self.semantic_copyright_reviewer.review(
                idea=project.idea,
                script=project.script,
                visual_bible=project.visual_bible,
                storyboard=project.storyboard,
            )
        )
        project.quality_report.extend(
            self.continuity_gate.review(
                visual_bible=project.visual_bible,
                storyboard=project.storyboard,
                continuity_lock=project.continuity_lock,
            )
        )
        project.final_output_placeholder = None
        project.rough_cut_placeholder = None
        project.video_assets = {}
        project.edit_plan = {}
        reset_final_look(project)
        project.status = "ready_for_ai_edit" if all(
            str(shot.status).startswith("approved") for shot in project.storyboard
        ) else "ready_for_comfyui_render"
        project.logs.append(f"Storyboard Agent: Shot {shot_number} re-planned; duration and narrative position preserved.")
        project.logs.extend(project.quality_report)
        self.store.save(project)
        return project
