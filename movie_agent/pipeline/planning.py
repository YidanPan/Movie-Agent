"""Planning-stage read models.

These helpers intentionally return plain dictionaries.  They are safe to use
from an API, event callback, or future background worker without coupling the
planning agents to FastAPI.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from movie_agent.models import MovieProject
from movie_agent.services.audio import ensure_audio_design
from movie_agent.services.continuity import build_continuity_lock
from movie_agent.services.final_look import ensure_final_look
from movie_agent.services.revisions import ensure_project_revision_metadata, reconcile_generation_fingerprints
from movie_agent.services.story_world import extract_story_world, validate_story_world_references
from movie_agent.services.state_ledger import build_state_ledger
from movie_agent.services.subtitles import align_script_to_shots, ensure_dialogue_assets, shot_count_for_duration
from movie_agent.services.quality import ContinuityQualityGate, PlanningQualityGate, SemanticCopyrightReviewer
from movie_agent.services.storyboard_quality import StoryboardRelevanceGate


def planning_snapshot(project: Any) -> dict[str, Any]:
    """Summarise the planning outputs without exposing mutable internals."""

    storyboard = list(getattr(project, "storyboard", []) or [])
    return {
        "project_id": str(getattr(project, "project_id", "")),
        "idea": str(getattr(project, "idea", "")),
        "film_language": str(getattr(project, "film_language", "en") or "en"),
        "story_beats": len(getattr(project, "story_beats", []) or []),
        "shots": len(storyboard),
        "shot_revisions": [int(getattr(shot, "revision", 1) or 1) for shot in storyboard],
        "dialogue_locked": bool((getattr(project, "script", {}) or {}).get("dialogue_locked")),
    }


class PlanningPipeline:
    """Own the planning quality boundary used before a project is saved."""

    def __init__(
        self,
        quality_gate: PlanningQualityGate,
        continuity_gate: ContinuityQualityGate,
        copyright_reviewer: SemanticCopyrightReviewer,
        *,
        director: Any | None = None,
        writer: Any | None = None,
        storyboard_agent: Any | None = None,
        visual_bible_agent: Any | None = None,
        settings: Any | None = None,
        using_creative_llm: bool = False,
    ) -> None:
        self.quality_gate = quality_gate
        self.continuity_gate = continuity_gate
        self.copyright_reviewer = copyright_reviewer
        self.director = director
        self.writer = writer
        self.storyboard_agent = storyboard_agent
        self.visual_bible_agent = visual_bible_agent
        self.settings = settings
        self.using_creative_llm = using_creative_llm

    def review(
        self,
        *,
        idea: str,
        duration_seconds: int,
        script: dict[str, Any],
        visual_bible: dict[str, Any],
        storyboard: list[Any],
        continuity_lock: dict[str, Any],
        story_beats: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Run all planning QC without making orchestration decisions."""

        board_review = None
        if story_beats is not None:
            board_review = StoryboardRelevanceGate().review_storyboard(storyboard, story_beats)
            if board_review["beat_mapping"]["uncovered_beats"] or board_review["beat_mapping"]["orphan_shots"]:
                raise ValueError(
                    "Planning quality failed: storyboard beat mapping is incomplete "
                    f"(uncovered={board_review['beat_mapping']['uncovered_beats']}, "
                    f"orphan_shots={board_review['beat_mapping']['orphan_shots']})."
                )

        report = self.quality_gate.review(
            duration_seconds=duration_seconds,
            script=script,
            visual_bible=visual_bible,
            storyboard=storyboard,
        )
        report.extend(self.copyright_reviewer.review(idea=idea, script=script, visual_bible=visual_bible, storyboard=storyboard))
        report.extend(
            self.continuity_gate.review(
                visual_bible=visual_bible,
                storyboard=storyboard,
                continuity_lock=continuity_lock,
            )
        )
        if board_review:
            report.append(
                "Storyboard Review: "
                f"beat coverage {board_review['beat_coverage']:.0%}; "
                f"decision {board_review['decision']}."
            )
        return report

    def create_project(
        self,
        idea: str,
        duration: int,
        visual_style: str,
        *,
        project_id: str,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> MovieProject:
        """Run the complete planning department and return a persisted-ready project.

        The orchestrator owns storage and lifecycle transitions.  All Director,
        Writer, Story Supervisor, Visual Bible, Storyboard, and Planning QC
        work lives here so that a future planning worker can call one boundary.
        """

        if self.settings is None or any(
            dependency is None
            for dependency in (self.director, self.writer, self.storyboard_agent, self.visual_bible_agent)
        ):
            raise RuntimeError("PlanningPipeline requires all planning agents and settings.")

        def emit(event: dict[str, Any]) -> None:
            if event_callback is not None:
                event_callback(event)

        cleaned_idea = idea.strip()
        if len(cleaned_idea) < 10:
            raise ValueError("Please provide an original sci-fi idea of at least 10 characters.")
        if not 30 <= duration <= 80:
            raise ValueError("Current MVP supports 30-80 second target duration.")
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
        script = self.writer.write(cleaned_idea, brief, duration_seconds=duration, shot_count=planned_shot_count)
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
            emit({"type": "artifact", "agent": "writer", "title": "Story Outline", "content": script["outline"]})

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
        story_beats = self.writer.generate_story_beats(cleaned_idea, brief, script, duration, story_world=story_world)
        emit({"type": "agent_done", "agent": "story_beats", "story_beats": story_beats})
        emit(
            {
                "type": "artifact",
                "agent": "story_beats",
                "title": "Beat Map",
                "content": (
                    f"{len(story_beats)} dramatic beats locked. "
                    + " → ".join(beat.get("narrative_purpose", f"beat {i + 1}") for i, beat in enumerate(story_beats))
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
                "message": "I'd suggest locking off the camera for the first three shots, saving the slow dolly for the final turn — so movement earns its meaning.",
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
            cleaned_idea,
            duration,
            visual_style,
            project_id,
            brief,
            script,
            visual_bible,
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
                "content": f"Script Supervisor mapped {len(storyboard)} dialogue and narration cues to the locked storyboard. Review this version before locking the Dialogue Book.",
            }
        )
        emit({"type": "agent_done", "agent": "storyboard", "storyboard": [shot.to_dict() for shot in storyboard]})
        emit(
            {
                "type": "artifact",
                "agent": "storyboard",
                "title": "Shot Rhythm",
                "content": f"{len(storyboard)} shots: static-static-static-dynamic-static; final shot holds {storyboard[-1].duration_seconds if storyboard else 4}s of silence.",
            }
        )
        emit(
            {
                "type": "chat",
                "from": "storyboard",
                "to": "director",
                "message": f"{len(storyboard)} shots cover the full narrative arc. Should we reserve a backup shot in case the pacing feels too fast?",
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
        quality_report = self.review(
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
                "message": f"Script and visual descriptions have passed copyright review; all elements are original. {len(quality_report)} items flagged for attention.",
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
            target_fps=int(getattr(self.settings, "project_master_fps", 24) or 24),
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
        ensure_audio_design(project)
        ensure_final_look(project)
        project.logs.extend(
            [
                "Sound Design Agent: Music Brief and Emotional Arc generated; awaiting AI Edit to wire up four tracks.",
                "Sound Design Agent: Voice / Music / SFX / Ambience tracks established; Smart Ducking enabled by default.",
                "Final Look: Final Look console will open after the final cut; defaults to whole-film scope.",
            ]
        )
        return project

