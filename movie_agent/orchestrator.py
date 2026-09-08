"""Coordinates the MVP planning stages and stores their output."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
from datetime import datetime, timezone
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
from movie_agent.services.story_world import extract_story_world, validate_story_world_references
from movie_agent.services.audio import (
    EDIT_AUDIO_STAGES,
    apply_audio_track_params,
    ensure_audio_design,
    replan_track,
)
from movie_agent.services.music import FileMusicProvider
from movie_agent.services.media_quality import best_master_path, probe_media, export_dimensions
from movie_agent.services.voice import ContinuousVoiceService, mark_voice_alignment_stale
from movie_agent.services.state_ledger import rebuild_state_ledger_from_shot, build_state_ledger, validate_state_delta_or_raise
from movie_agent.services.change_impact import RENDERER_INPUT_FIELDS, SHOT_EDITABLE_FIELDS, TIMING_FIELDS, resolve_change_impact
from movie_agent.services.final_look import ensure_final_look, normalise_final_look, reset_final_look
from movie_agent.services.errors import clear_failure
from movie_agent.services.revisions import (
    ensure_project_revision_metadata,
    ensure_shot_metadata,
    hash_shot_prompt,
    reconcile_generation_fingerprints,
    mark_shot_stale,
)
from movie_agent.services.subtitles import (
    align_script_to_shots,
    ensure_dialogue_assets,
    normalise_subtitle_mode,
    shot_count_for_duration,
)
from movie_agent.services.readiness import ensure_action_ready
from movie_agent.pipeline.planning import PlanningPipeline
from movie_agent.pipeline.rendering import (
    RenderPipeline,
    invalidate_edit_outputs as render_invalidate_edit_outputs,
    require_dialogue_locked as render_require_dialogue_locked,
    shots_ready as render_shots_ready,
)
from movie_agent.pipeline.editing import EditPipeline
from movie_agent.pipeline.editing import edit_output_exists


def _render_ready_status(settings: Settings) -> str:
    """Persist one provider-neutral state for every real render provider."""

    return "render_ready"


def _rendering_status(settings: Settings) -> str:
    return "rendering"


class MovieOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = ProjectStore(settings.projects_dir)
        creative_llm = build_creative_llm(settings)
        self.using_creative_llm = creative_llm is not None
        self.director = DirectorAgent(creative_llm)
        self.writer = WriterAgent(creative_llm)
        # V0.2 keeps video generation mocked and the current renderer
        # manifest is T2V-only.  Do not let a text model select I2V/R2V before
        # those providers and their renderer contracts are actually enabled.
        supported_modes = {"T2V"}
        self.storyboard_agent = StoryboardAgent(creative_llm, supported_modes)
        self.visual_bible_agent = VisualBibleAgent(creative_llm)
        self.generation_agent = GenerationAgent(settings)
        self.reviewer = ReviewerAgent(settings)
        self.editor = EditorAgent(settings)
        self.voice_service = ContinuousVoiceService(settings)
        self.quality_gate = PlanningQualityGate()
        self.continuity_gate = ContinuityQualityGate()
        self.semantic_copyright_reviewer = SemanticCopyrightReviewer(creative_llm)
        self.planning_pipeline = PlanningPipeline(
            self.quality_gate,
            self.continuity_gate,
            self.semantic_copyright_reviewer,
        )
        self.render_pipeline = RenderPipeline(
            self.generation_agent,
            self.reviewer,
            settings=self.settings,
            continuity_gate=self.continuity_gate,
            persist=self.store.save,
        )
        self.edit_pipeline = EditPipeline(
            self.editor,
            self.voice_service,
            settings=self.settings,
            persist=self.store.save,
        )

    def create_project(
        self,
        idea: str,
        duration: int,
        visual_style: str,
        event_callback: Callable[[dict], None] | None = None,
        project_id: str | None = None,
    ) -> MovieProject:
        def emit(event: dict) -> None:
            if event_callback is not None:
                event_callback(event)

        cleaned_idea = idea.strip()
        if len(cleaned_idea) < 10:
            raise ValueError("Please provide an original sci-fi idea of at least 10 characters.")
        if not 30 <= duration <= 80:
            raise ValueError("Current MVP supports 30-80 second target duration.")

        project_id = str(project_id or f"film-{uuid4().hex[:8]}")
        if not project_id.startswith("film-"):
            raise ValueError("Project ID must start with film-.")
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
            "Project saved: Project JSON persisted; ready for review, AI Edit, or export.",
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
                "content": "Extracting dramatic beats independently from the shot count for cross-shot continuity.",
            }
        )
        emit({"type": "agent_start", "agent": "story_world"})
        story_world = extract_story_world(cleaned_idea, brief, script, self.writer.llm)
        emit({"type": "agent_done", "agent": "story_world", "story_world": story_world})
        story_beats = self.writer.generate_story_beats(
            cleaned_idea,
            brief,
            script,
            duration,
            story_world=story_world,
        )
        emit({"type": "agent_done", "agent": "story_beats", "story_beats": story_beats})
        emit(
            {
                "type": "artifact",
                "agent": "story_beats",
                "title": "Beat Map",
                "content": (
                    f"{len(story_beats)} dramatic beats locked. "
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
                    "Translate the writer's emotional turn into a repeatable visual language. "
                    f"Keep the palette and camera choices subordinate to the brief: {str(brief.get('theme') or brief.get('主题') or 'the central conflict')[:120]}."
                ),
            }
        )
        emit({"type": "agent_start", "agent": "visual_bible"})
        emit(
            {
                "type": "artifact",
                "agent": "visual_bible",
                "title": "Material Samples",
                "content": (
                    "Visual candidates extracted from the locked bible: "
                    f"{visual_style} / {str(brief.get('theme') or brief.get('主题') or 'the central conflict')[:120]}. "
                    "Awaiting script confirmation of emotional direction."
                ),
            }
        )
        visual_bible = self.visual_bible_agent.create(visual_style, brief, script, story_world=story_world)
        continuity_lock = build_continuity_lock(visual_bible, self.settings.film_language)
        emit({"type": "agent_done", "agent": "visual_bible", "visual_bible": visual_bible})
        emit(
            {
                "type": "artifact",
                "agent": "visual_bible",
                "title": "Mood Board",
                "content": (
                    f"{visual_style}-led. Palette: {str(visual_bible.get('palette') or visual_bible.get('style_card') or 'locked style')[:120]}; "
                    f"lighting: {str(visual_bible.get('lighting') or visual_bible.get('cinematography_lock') or 'locked cinematography')[:120]}."
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
            story_world=story_world,
        )
        storyboard_review = self.storyboard_agent.review_storyboard(storyboard, story_beats)
        emit({"type": "storyboard_review", "review": storyboard_review})
        if storyboard_review["decision"] == "REVIEW":
            storyboard = self.storyboard_agent.repair_shots(
                storyboard,
                story_beats,
                visual_bible=visual_bible,
                story_world=story_world,
                max_passes=1,
            )
            storyboard_review = self.storyboard_agent.review_storyboard(storyboard, story_beats)
            emit({"type": "storyboard_repair", "review": storyboard_review})
        previs_review_required = storyboard_review.get("decision") != "PASS"
        if story_world:
            world_errors = validate_story_world_references([shot.to_dict() for shot in storyboard], story_world)
            if any(world_errors.values()):
                raise ValueError(f"STORY_WORLD_REVIEW_REQUIRED: {world_errors}")
        # The first Writer pass creates the broad screenplay.  Once the
        # storyboard is locked, run the Script Supervisor pass so narration,
        # dialogue, and subtitle cues are grounded in the actual shot events.
        if not previs_review_required:
            script = self.writer.supervise_storyboard(
                cleaned_idea,
                brief,
                script,
                storyboard,
                duration_seconds=duration,
            )
            script["film_language"] = self.settings.film_language
            script = align_script_to_shots(script, storyboard, allow_silent=True)
        else:
            script = ensure_dialogue_assets(script, duration_seconds=duration, shot_count=len(storyboard) or None)
            script["film_language"] = self.settings.film_language
        emit(
            {
                "type": "artifact",
                "agent": "writer",
                "title": "Shot-aware Dialogue Lock Draft",
                "content": (
                    f"Script Supervisor mapped {len(storyboard)} dialogue and narration cues to the locked storyboard. "
                    "Review this version before locking the Dialogue Book."
                ),
            }
        )
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
        quality_report = self.planning_pipeline.review(
            idea=cleaned_idea,
            duration_seconds=duration,
            script=script,
            visual_bible=visual_bible,
            storyboard=storyboard,
            continuity_lock=continuity_lock,
            story_beats=story_beats,
        )
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
            status="previs_review_required" if previs_review_required else ("planned_text_ai" if self.using_creative_llm else "planned_mock"),
            brief=brief,
            script=script,
            visual_bible=visual_bible,
            storyboard=storyboard,
            quality_report=quality_report,
            logs=logs + quality_report,
            story_beats=story_beats,
            story_world=story_world,
            storyboard_review=storyboard_review,
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
        build_state_ledger(project)
        ensure_project_revision_metadata(
            project,
            provider="modelscope" if self.using_creative_llm else "mock",
            model=self.settings.modelscope_model if self.using_creative_llm else "mock-rule-engine",
        )
        reconcile_generation_fingerprints(
            project,
            workflow_identity=self.settings.comfy_workflow_template or "verified-comfyui-workflow",
            workflow_path=self.settings.workflows_dir / self.settings.comfy_workflow_template,
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
        # Persisting a project is not the same as archiving it.  Keep this as a
        # neutral lifecycle event so the UI cannot render a false ARCHIVED
        # state while the project is still in active production.
        emit({"type": "project_saved", "project_id": project_id})
        if previs_review_required:
            project.logs.append(
                "Planning QC: Storyboard remains under review after one repair pass; explicit PREVIS approval is required before Script Supervisor or Render."
            )
            self.store.save(project)
            return project
        if self.settings.video_generation_mode != "mock":
            project.status = _render_ready_status(self.settings)
            project.logs.append(
                "Generation Agent: Project is ready. Submit per-shot tasks through the selected video provider."
            )
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
        if project.status == "previs_review_required":
            raise ValueError("PREVIS_REVIEW_REQUIRED: approve the storyboard before mock production can advance.")
        clear_failure(project)
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
        project = self.store.load(project_id)
        return self.render_pipeline.render_project(project, progress_callback=progress_callback)

    def render_shot(self, project_id: str, shot_number: int) -> MovieProject:
        """Regenerate one shot from the Inspector without assembling the full film."""
        project = self.store.load(project_id)
        return self.render_pipeline.render_single_shot(project, shot_number)

    def approve_previs(self, project_id: str) -> MovieProject:
        """Explicitly approve a repaired storyboard and resume planning."""

        project = self.store.load(project_id)
        ensure_action_ready(project, self.settings, "APPROVE_PREVIS")
        review = self.storyboard_agent.review_storyboard(project.storyboard, project.story_beats)
        if review.get("decision") != "PASS":
            raise ValueError("PREVIS_REVIEW_REQUIRED: storyboard still contains unresolved review items.")
        project.storyboard_review = review
        project.script = self.writer.supervise_storyboard(
            project.idea,
            project.brief,
            project.script,
            project.storyboard,
            duration_seconds=project.duration_seconds,
        )
        project.script["film_language"] = project.film_language
        project.script = align_script_to_shots(project.script, project.storyboard, allow_silent=True)
        project.quality_report = self.planning_pipeline.review(
            idea=project.idea,
            duration_seconds=project.duration_seconds,
            script=project.script,
            visual_bible=project.visual_bible,
            storyboard=project.storyboard,
            continuity_lock=project.continuity_lock,
            story_beats=project.story_beats,
        )
        project.status = "planned_text_ai" if self.using_creative_llm else "planned_mock"
        project.logs.append("Planning QC: PREVIS explicitly approved; Script Supervisor resumed.")
        self.store.save(project)
        if self.settings.video_generation_mode != "mock":
            project.status = _render_ready_status(self.settings)
            self.store.save(project)
        return project

    def approve_shot(self, project_id: str, shot_number: int) -> MovieProject:
        """Record an explicit human visual approval for one generated shot."""

        project = self.store.load(project_id)
        if not 1 <= shot_number <= len(project.storyboard):
            raise ValueError(f"Shot number must be between 1 and {len(project.storyboard)}.")
        ensure_action_ready(project, self.settings, "APPROVE_SHOT", shot_number=shot_number)
        shot = project.storyboard[shot_number - 1]
        project.logs.append(self.reviewer.approve_manual(shot, project_id=project.project_id))
        if self._shots_ready(project):
            project.status = "ready_for_ai_edit"
            project.logs.append("QC Agent: All current shot revisions are explicitly approved; SHOTS READY.")
        else:
            project.status = "awaiting_visual_review"
        self.store.save(project)
        return project

    @staticmethod
    def _require_dialogue_locked(project: MovieProject) -> None:
        render_require_dialogue_locked(project)

    @staticmethod
    def _shots_ready(project: MovieProject) -> bool:
        """Return true only for currently approved, non-stale shot revisions."""

        return render_shots_ready(project)

    @staticmethod
    def _invalidate_edit_outputs(
        project: MovieProject,
        *,
        reason: str = "upstream_changed",
        source: str = "pipeline",
        shot: Any | None = None,
    ) -> dict[str, Any]:
        """Mark downstream derivatives stale without deleting prior media."""

        return render_invalidate_edit_outputs(project, reason=reason, source=source, shot=shot)

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
        mark_voice_alignment_stale(project, "dialogue_revision_changed")
        self._invalidate_edit_outputs(project, reason="dialogue_revision_changed", source="dialogue")
        ensure_audio_design(project)
        project.logs.append("Script Supervisor: Saved dialogue book and subtitle track draft; not yet locked.")
        self.store.save(project)
        return project

    def lock_dialogue(self, project_id: str) -> MovieProject:
        project = self.store.load(project_id)
        policies = (project.script or {}).get("speech_policy_by_shot") or {}
        all_silent = bool(policies) and all(
            str(value).upper() in {"SILENT", "AMBIENCE_ONLY"} for value in policies.values()
        )
        # Do not silently lock a brand-new empty payload that the normaliser
        # would otherwise turn into placeholder lines.
        if not all_silent and (not (project.script or {}).get("dialogue_book") or not (project.script or {}).get("subtitle_track")):
            raise ValueError("Dialogue book or subtitle track is empty; cannot lock.")
        project.script = ensure_dialogue_assets(
            project.script,
            duration_seconds=project.duration_seconds,
            shot_count=len(project.storyboard) or None,
        )
        if not all_silent and (not project.script.get("dialogue_book") or not project.script.get("subtitle_track")):
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
        self._invalidate_edit_outputs(project, reason="dialogue_unlocked", source="dialogue")
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
        mark_voice_alignment_stale(project, "shot_timeline_changed")
        ensure_audio_design(project)
        self._invalidate_edit_outputs(project, reason="shot_timeline_changed", source="shot_timing")
        project.status = "ready_for_ai_edit" if self._shots_ready(project) else _render_ready_status(self.settings)
        project.logs.append(
            f"Editor Agent: Shot {shot_number} timing updated to {shot.duration_seconds}s ({mode.upper()}); downstream cut invalidated."
        )
        self.store.save(project)
        return project

    def update_shot(self, project_id: str, shot_number: int, updates: dict[str, Any]) -> MovieProject:
        """Apply Inspector edits through one domain boundary.

        The HTTP layer must not mutate ``Shot`` fields directly: visual edits
        create a new shot revision and invalidate dependent media, while a
        timeline-only edit preserves the original source render.
        """

        incoming = {str(key): value for key, value in (updates or {}).items() if value is not None}
        unknown = sorted(set(incoming) - SHOT_EDITABLE_FIELDS)
        if unknown:
            raise ValueError(f"Unsupported shot fields: {', '.join(unknown)}.")
        timing_updates = {key: incoming[key] for key in TIMING_FIELDS if key in incoming}
        incoming = {key: value for key, value in incoming.items() if key not in TIMING_FIELDS}
        project = self.store.load(project_id)
        if not 1 <= shot_number <= len(project.storyboard):
            raise ValueError(f"Shot number must be between 1 and {len(project.storyboard)}.")
        if timing_updates:
            # Reuse the public timing validator and reload its atomic result;
            # visual edits below are then applied against the newest snapshot.
            project = self.update_shot_timing(
                project_id,
                shot_number,
                desired_duration=timing_updates.get(
                    "desired_duration", timing_updates.get("duration_seconds")
                ),
                timing_mode=timing_updates.get("timing_mode"),
            )
        if not incoming:
            return project
        project = self.store.load(project_id)
        if not 1 <= shot_number <= len(project.storyboard):
            raise ValueError(f"Shot number must be between 1 and {len(project.storyboard)}.")
        shot = project.storyboard[shot_number - 1]
        if "beat_id" in incoming and str(incoming["beat_id"]) != str(shot.beat_id):
            raise ValueError("Beat reassignment is a separate operation; use Reassign Beat.")
        candidate = shot.to_dict()
        candidate.update(incoming)
        if isinstance(candidate.get("character_ids"), str):
            candidate["character_ids"] = [item.strip() for item in candidate["character_ids"].split(",") if item.strip()]
        if isinstance(candidate.get("prop_ids"), str):
            candidate["prop_ids"] = [item.strip() for item in candidate["prop_ids"].split(",") if item.strip()]
        if "state_delta" in candidate:
            candidate["state_delta"] = validate_state_delta_or_raise(candidate["state_delta"], project.story_world)
        if project.story_world:
            world_errors = validate_story_world_references([candidate], project.story_world)
            if any(world_errors.values()):
                raise ValueError(f"STORY_WORLD_REVIEW_REQUIRED: {world_errors}")
        impact = resolve_change_impact(set(incoming))
        changed = False
        for key, value in incoming.items():
            if key in {"character_ids", "prop_ids"}:
                value = candidate[key]
            elif isinstance(value, str):
                value = value.strip()
            if getattr(shot, key) != value:
                setattr(shot, key, value)
                changed = True
        if not changed:
            return project
        if impact["timing"]:
            requested = incoming.get("desired_duration", incoming.get("duration_seconds", shot.duration_seconds))
            try:
                requested = float(requested)
            except (TypeError, ValueError) as error:
                raise ValueError("Desired shot duration must be numeric.") from error
            if not 1 <= requested <= 80:
                raise ValueError("Desired shot duration must be between 1 and 80 seconds.")
            shot.duration_seconds = max(1, int(round(requested)))
            shot.desired_duration = float(shot.duration_seconds)
            shot.timing_mode = str(incoming.get("timing_mode", shot.timing_mode or "native"))
            project.duration_seconds = sum(int(item.duration_seconds) for item in project.storyboard)
            project.brief["target_duration"] = f"{project.duration_seconds} seconds"
            project.script = align_script_to_shots(project.script, project.storyboard, allow_silent=True)
            mark_voice_alignment_stale(project, "shot_timeline_changed")
        renderer_input_changed = bool(set(impact["fields"]) & RENDERER_INPUT_FIELDS)
        visual_or_narrative = renderer_input_changed
        if renderer_input_changed:
            mark_shot_stale(shot, "shot_fields_changed")
        if "state_delta" in incoming or impact["narrative"]:
            rebuild_state_ledger_from_shot(project, shot_number)
        edit_event = self._invalidate_edit_outputs(
            project,
            reason="shot_fields_changed",
            source="shot" if visual_or_narrative else "shot_timing",
            shot=shot if visual_or_narrative else None,
        )
        edit_event["impact"] = impact
        # The compiled renderer prompt includes continuity state and sound
        # design, so every renderer-facing field must invalidate current
        # media even when it is not classified as a purely visual edit.
        if renderer_input_changed:
            reconcile_generation_fingerprints(
                project,
                workflow_identity=self.settings.comfy_workflow_template or "verified-comfyui-workflow",
                workflow_path=self.settings.workflows_dir / self.settings.comfy_workflow_template,
            )
        project.status = "ready_for_ai_edit" if self._shots_ready(project) else _render_ready_status(self.settings)
        project.logs.append(
            f"Script Supervisor: Applied atomic Shot {shot_number} update ({', '.join(impact['fields'])}); downstream production marked stale."
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
        return self.edit_pipeline.create_rough_cut(
            project,
            progress_callback,
            music_mode=music_mode,
            smart_ducking=smart_ducking,
            music_asset_name=music_asset_name,
            music_intensity=music_intensity,
            track_enabled=track_enabled,
            track_params=track_params,
        )

    def normalize_resolution(self, project_id: str, resolution: str = "1080p") -> MovieProject:
        """Opt-in source normalization before AI Edit / Final Cut."""

        project = self.store.load(project_id)
        if not self._shots_ready(project):
            raise ValueError("All shots must pass QC before Resolution Normalize can run.")
        self.editor.normalize_resolution(project, resolution)
        if project.status not in {"ready_for_ai_edit", "ready_for_comfyui_render", "render_ready"}:
            project.status = "ready_for_ai_edit"
        self.store.save(project)
        return project

    def generate_voice_track(self, project_id: str) -> MovieProject:
        """Render the locked English voice track without starting a full edit."""

        project = self.store.load(project_id)
        self._require_dialogue_locked(project)
        result = self.voice_service.synthesize(project)
        project.logs.append(
            f"Voice Agent: Continuous track {result.status.lower()}"
            + (f" · {result.duration_seconds:.2f}s measured" if result.duration_seconds else "")
            + "."
        )
        project.mix_state.setdefault("voice", {})["status"] = result.status
        project.mix_state["voice_duration_seconds"] = result.duration_seconds
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
            edit_output_exists(project)
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
            self._invalidate_edit_outputs(project, reason="audio_design_changed", source="audio")
            project.mix_state["stage_status"] = {stage: "queued" for stage in EDIT_AUDIO_STAGES}
            project.mix_state["active_stage"] = None
            project.mix_state["status"] = "DESIGN UPDATED · RE-CUT REQUIRED"
        project.logs.append(
            f"Sound Design Agent: Configuration updated (Music={project.music_mode.upper()} · Smart Ducking={'ON' if project.smart_ducking.get('enabled') else 'OFF'})."
        )
        self.store.save(project)
        return project

    def replan_audio_track(self, project_id: str, track_key: str) -> MovieProject:
        """Re-plan one sound track without claiming that media was rendered."""

        project = self.store.load(project_id)
        ensure_action_ready(project, self.settings, "REPLAN_AUDIO_TRACK", track_key=track_key)
        had_edit_output = bool(
            edit_output_exists(project)
            or project.status in {"editing_rough_cut", "rough_cut_ready", "editing_final"}
            or str(project.status).startswith("completed")
        )
        replan_track(project, track_key)
        if had_edit_output:
            self._invalidate_edit_outputs(project, reason=f"{track_key}_track_replanned", source="audio")
            project.mix_state["stage_status"] = {stage: "queued" for stage in EDIT_AUDIO_STAGES}
            project.mix_state["active_stage"] = None
            project.mix_state["status"] = "DESIGN UPDATED · RE-CUT REQUIRED"
        project.logs.append(f"Sound Design Agent: {track_key.upper()} track plan re-planned.")
        self.store.save(project)
        return project

    def regenerate_audio_track(self, project_id: str, track_key: str) -> MovieProject:
        """Compatibility wrapper for the legacy regenerate endpoint."""

        return self.replan_audio_track(project_id, track_key)

    def render_audio_track(self, project_id: str, track_key: str) -> MovieProject:
        """Render one real provider-backed audio track, never just its plan."""

        project = self.store.load(project_id)
        key = str(track_key or "").strip().lower()
        ensure_action_ready(project, self.settings, "RENDER_AUDIO_TRACK", track_key=key)
        if key == "voice":
            return self.generate_voice_track(project_id)
        if key != "music":
            raise RuntimeError(f"No real provider is configured for the {key.upper()} track yet.")

        track = (project.audio_tracks or {}).get("music") or {}
        source = Path(str(track.get("media_path") or ""))
        if not source.is_file() and str(project.music_mode or "").lower() == "upload":
            source = self.settings.outputs_dir / project.project_id / "audio" / str(project.music_asset_name or "")
        if not source.is_file():
            raise RuntimeError("MUSIC_PROVIDER_REQUIRED: choose a library or uploaded score before rendering Music.")
        provider = FileMusicProvider(source, ffmpeg_bin=self.settings.ffmpeg_bin)
        ensure_audio_design(
            project,
            music_provider=provider,
            music_output_dir=self.settings.outputs_dir / project.project_id / "audio",
        )
        project.mix_state["media_mixed"] = False
        project.logs.append("Music Provider: Real score rendered from the current Music Brief.")
        self.store.save(project)
        return project

    def approve_edit(self, project_id: str, subtitle_mode: str | None = None) -> MovieProject:
        """Approve the current edit revision without rendering a master."""

        project = self.store.load(project_id)
        ensure_action_ready(project, self.settings, "APPROVE_FINAL_CUT")
        self._require_dialogue_locked(project)
        if project.status not in {"rough_cut_ready", "editing_rough_cut"}:
            raise ValueError("Please complete the Rough Cut before approving the final cut.")
        if not self._shots_ready(project):
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
        self.store.save(project)
        return project

    def generate_final_master(self, project_id: str) -> MovieProject:
        """Generate or recover the Final Master from an approved edit."""

        project = self.store.load(project_id)
        ensure_action_ready(project, self.settings, "GENERATE_FINAL_MASTER")
        self._require_dialogue_locked(project)
        approved = bool((project.edit_plan or {}).get("approved"))
        if not approved and project.status != "final_cut_approved" and not str(project.status).startswith("completed"):
            raise ValueError("Approve the current Final Cut before generating the Final Master.")
        if not self._shots_ready(project):
            raise ValueError("All current shot revisions must be approved before generating the Final Master.")
        project.status = "editing_final"
        project.mix_state["active_stage"] = "final_encode"
        project.mix_state["status"] = "FINAL MASTER GENERATION"
        self.store.save(project)
        try:
            if self.settings.video_generation_mode != "mock":
                project.logs.append(self.editor.assemble(project, project.subtitle_mode))
                project.status = "completed"
            else:
                project.logs.append(self.editor.assemble_mock(project))
                project.status = "completed_text_ai_video_mock" if self.using_creative_llm else "completed_mock"
            project.logs.append(f"Project complete: Final Master generated from approved cut ({project.subtitle_mode}).")
            project.mix_state["status"] = "FINAL MASTER READY"
            project.mix_state["active_stage"] = None
            self.store.save(project)
        except Exception:
            project.status = "final_cut_approved"
            project.mix_state["status"] = "FINAL MASTER GENERATION FAILED"
            project.mix_state["active_stage"] = None
            self.store.save(project)
            raise
        return project

    def verify_final_master(self, project_id: str) -> MovieProject:
        """Verify the actual current master asset and persist the result."""

        project = self.store.load(project_id)
        record = (project.video_assets or {}).get("final_master")
        path = best_master_path(project)
        metadata = probe_media(path, self.settings.ffprobe_bin) if path else {}
        target_width, target_height = export_dimensions(project.target_resolution, "16:9")
        width, height = metadata.get("width"), metadata.get("height")
        duration = metadata.get("duration_seconds")
        expected_duration = float(project.duration_seconds or 0)
        checks = {
            "asset_record": isinstance(record, dict),
            "file_exists": bool(path and path.is_file()),
            "not_stale": isinstance(record, dict) and record.get("stale") is not True,
            "ffprobe": bool(metadata.get("exists")) and bool(metadata.get("codec")),
            "resolution": isinstance(width, int) and isinstance(height, int) and width >= target_width and height >= target_height,
            "duration": isinstance(duration, (int, float)) and (not expected_duration or abs(float(duration) - expected_duration) <= 1.5),
        }
        verification = {
            "status": "VERIFIED" if all(checks.values()) else "FAILED",
            "valid": all(checks.values()),
            "checks": checks,
            "resolution": f"{width}x{height}" if width and height else None,
            "duration_seconds": duration,
            "verified_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        project.delivery_verification = verification
        if isinstance(record, dict):
            record["verification_status"] = verification["status"]
            record["verification_checks"] = dict(checks)
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
        ensure_action_ready(project, self.settings, "REPLAN_SHOT", shot_number=shot_number)
        index = shot_number - 1
        previous_shot = project.storyboard[index - 1] if index > 0 else None
        current_shot = project.storyboard[index]
        mark_shot_stale(current_shot, f"shot_{shot_number}_replanned")
        revised_shot = self.storyboard_agent.revise(
            current_shot, project.visual_bible, previous_shot=previous_shot
        )
        # ``revise`` creates a new dataclass instance, so explicitly retain the
        # revision ledger and stale media pointers from the prior instance.
        revised_shot.revision = current_shot.revision
        revised_shot.prompt_hash = hash_shot_prompt(revised_shot)
        revised_shot.stale = True
        revised_shot.qc_status = "STALE"
        revised_shot.asset_history = list(current_shot.asset_history)
        revised_shot.media_assets = current_shot.media_assets
        project.storyboard[index] = revised_shot
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
        self._invalidate_edit_outputs(
            project,
            reason=f"shot_{shot_number}_replanned",
            source="shot",
            shot=revised_shot,
        )
        project.status = "ready_for_ai_edit" if self._shots_ready(project) else _render_ready_status(self.settings)
        project.logs.append(f"Storyboard Agent: Shot {shot_number} re-planned; duration and narrative position preserved.")
        project.logs.extend(project.quality_report)
        self.store.save(project)
        return project
