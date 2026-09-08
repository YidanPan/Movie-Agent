"""Rendering-stage seams shared by ComfyUI and mock workers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from movie_agent.services.continuity import ensure_continuity_lock
from movie_agent.services.errors import clear_failure, error_info, record_failure
from movie_agent.services.final_look import reset_final_look
from movie_agent.services.readiness import ensure_action_ready
from movie_agent.services.revisions import invalidate_downstream, mark_shot_stale, reconcile_generation_fingerprints
from movie_agent.services.shot_context import resolve_shot_context
from movie_agent.services.state_ledger import build_state_ledger, state_record_for_shot
from movie_agent.state import shot_ready


def failure_stage(error: BaseException) -> str:
    """Map a render exception to the production department that owns it."""

    text = str(error).lower()
    return "quality" if any(token in text for token in ("quality", "consistency", "copyright", "drift")) else "generation"


def require_dialogue_locked(project: Any) -> None:
    """Require the locked dialogue contract before rendering picture."""

    if not bool((getattr(project, "script", {}) or {}).get("dialogue_locked")):
        raise ValueError("Please review and lock the dialogue book / subtitle track in the writing stage first.")


def shots_ready(project: Any) -> bool:
    """Return true only for currently approved, non-stale shot revisions."""

    shots = list(getattr(project, "storyboard", []) or [])
    return bool(shots) and all(shot_ready(shot) for shot in shots)


def invalidate_edit_outputs(
    project: Any,
    *,
    reason: str = "upstream_changed",
    source: str = "pipeline",
    shot: Any | None = None,
) -> dict[str, Any]:
    """Mark downstream derivatives stale without deleting prior media."""

    event = invalidate_downstream(project, source, reason, shot=shot)
    reset_final_look(project)
    return event


class RenderPipeline:
    """Own real shot rendering, retry, and visual-QC state transitions."""

    def __init__(
        self,
        generation_agent: Any,
        reviewer: Any,
        *,
        settings: Any | None = None,
        continuity_gate: Any | None = None,
        persist: Callable[[Any], None] | None = None,
    ) -> None:
        self.generation_agent = generation_agent
        self.reviewer = reviewer
        self.settings = settings
        self.continuity_gate = continuity_gate
        self.persist = persist

    def _save(self, project: Any) -> None:
        if self.persist is not None:
            self.persist(project)

    def render_shot(self, project: Any, shot: Any, *, previous_shot: Any = None) -> str:
        build_state_ledger(project)
        record = state_record_for_shot(project, int(getattr(shot, "number", 0) or 0))
        context = resolve_shot_context(
            shot,
            project.visual_bible,
            getattr(project, "story_world", {}) or {},
            previous_shot,
            entity_state_before=record.get("before"),
            entity_state_delta=record.get("delta"),
            entity_state_after=record.get("after"),
        )
        message = self.generation_agent.generate(
            project.project_id,
            shot,
            visual_bible=project.visual_bible,
            previous_shot=previous_shot,
            target_resolution=project.target_resolution,
            film_language=project.film_language,
            story_world=getattr(project, "story_world", {}) or {},
            context=context,
            project=project,
        )
        review = self.reviewer.review_generated(
            shot,
            project_id=project.project_id,
            visual_bible=project.visual_bible,
            previous_shot=previous_shot,
            story_world=getattr(project, "story_world", {}) or {},
            context=context,
        )
        return f"{message}\n{review}"

    def render_project(
        self,
        project: Any,
        *,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> Any:
        """Render all incomplete shots and persist the resumable state."""

        if self.settings is None:
            raise RuntimeError("RenderPipeline requires settings for project rendering.")
        if self.settings.video_generation_mode == "mock":
            raise ValueError("Current mode is mock. Select an explicitly configured video provider before rendering.")
        if project.status == "previs_review_required":
            raise ValueError("PREVIS_REVIEW_REQUIRED: approve the storyboard before rendering.")

        clear_failure(project)
        require_dialogue_locked(project)
        ensure_continuity_lock(project)
        reconcile_generation_fingerprints(
            project,
            workflow_identity=self.settings.comfy_workflow_template or "verified-comfyui-workflow",
            workflow_path=self.settings.workflows_dir / self.settings.comfy_workflow_template,
        )
        ensure_action_ready(project, self.settings, "START_RENDER")
        if self.continuity_gate is None:
            raise RuntimeError("RenderPipeline requires a continuity gate for project rendering.")
        self.continuity_gate.review(
            visual_bible=project.visual_bible,
            storyboard=project.storyboard,
            continuity_lock=project.continuity_lock,
        )
        provider = getattr(self.generation_agent, "provider", None)
        supported_modes = {
            str(item).upper()
            for item in (getattr(provider, "supported_modes", frozenset({"T2V"})) or frozenset())
        }
        unsupported_modes = sorted(
            {
                str(shot.generation_mode or "").upper()
                for shot in project.storyboard
                if str(shot.generation_mode or "").upper() not in supported_modes
            }
        )
        if unsupported_modes:
            modes = ", ".join(unsupported_modes)
            raise ValueError(
                f"The selected video provider supports {', '.join(sorted(supported_modes)) or 'no generation modes'}; "
                f"project still has {modes} shots. "
                "Please re-plan those shots before submitting for real generation."
            )
        project.status = "rendering"
        invalidate_edit_outputs(project, reason="render_started", source="shot_media")
        project.logs.append(
            f"Generation Agent: Submitting per-shot tasks through the {self.settings.video_generation_mode} provider."
        )
        self._save(project)
        total_shots = len(project.storyboard)
        max_retries = max(
            1,
            int(
                getattr(
                    self.settings,
                    "video_generation_max_retries",
                    getattr(self.settings, "comfy_max_retries", 2),
                )
                or 1
            ),
        )
        for index, _shot in enumerate(project.storyboard, start=1):
            render_context = shot_render_context(project, index)
            shot = render_context["shot"]
            if shot_ready(shot) and Path(shot.output_placeholder).is_file():
                project.logs.append(f"Generation Agent: Shot {shot.number} already complete; skipping on resume.")
                if progress_callback:
                    progress_callback(index, total_shots, f"Shot {shot.number} already complete; skipping")
                continue
            last_error: Exception | None = None
            previous_shot = render_context["previous_shot"]
            for attempt in range(1, max_retries + 1):
                try:
                    project.logs.append(self.render_shot(project, shot, previous_shot=previous_shot))
                    self._save(project)
                    if progress_callback:
                        progress_callback(index, total_shots, f"Shot {shot.number} generated and passed full QC")
                    last_error = None
                    break
                except Exception as error:
                    last_error = error
                    stage = failure_stage(error)
                    record_failure(
                        shot,
                        error,
                        stage=stage,
                        recoverable=getattr(error, "recoverable", None),
                        increment_retry=not bool(getattr(shot, "error_code", "")),
                    )
                    record_failure(project, error, stage=stage, recoverable=getattr(error, "recoverable", None))
                    failure_message = error_info(error, stage=stage)["error_message"]
                    project.logs.append(
                        f"Generation Agent: Shot {shot.number} attempt {attempt}/{max_retries} failed: {failure_message}"
                    )
                    self._save(project)
                    # An ambiguous submit outcome is intentionally not
                    # retried: without a task id, another POST could charge
                    # twice.  In-flight task timeouts remain recoverable and
                    # the next attempt resumes the persisted task instead.
                    if getattr(error, "recoverable", None) is False:
                        break
            if last_error is not None:
                project.status = "render_failed"
                project.logs.append("Generation Agent: You can click the real generate button again to resume from incomplete shots.")
                self._save(project)
                safe_message = error_info(last_error, stage="generation")["error_message"]
                raise RuntimeError(f"Shot {shot.number} failed after multiple attempts: {safe_message}") from last_error
            clear_failure(project)

        if shots_ready(project):
            project.status = "ready_for_ai_edit"
            project.logs.append(f"Generation Agent: {len(project.storyboard)}/{len(project.storyboard)} SHOTS READY; stage advanced to DELIVER.")
            project.logs.append("Editor Agent: Awaiting user to start AI Edit; Rough Cut first, then approve final cut.")
        else:
            project.status = "awaiting_visual_review"
            project.logs.append("QC Agent: Media integrity passed, but one or more shots require explicit MANUAL VISUAL REVIEW before SHOTS READY.")
        self._save(project)
        if progress_callback:
            progress_callback(total_shots, total_shots, f"{total_shots}/{total_shots} SHOTS READY · Awaiting AI Edit")
        return project

    def render_single_shot(self, project: Any, shot_number: int) -> Any:
        """Regenerate one shot from the Inspector without assembling the film."""

        if self.settings is None:
            raise RuntimeError("RenderPipeline requires settings for single-shot rendering.")
        if self.settings.video_generation_mode == "mock":
            raise ValueError("Current mode is mock. Select an explicitly configured video provider before generating shots.")
        clear_failure(project)
        if not 1 <= shot_number <= len(project.storyboard):
            raise ValueError(f"Shot number must be between 1 and {len(project.storyboard)}.")
        reconcile_generation_fingerprints(
            project,
            workflow_identity=self.settings.comfy_workflow_template or "verified-comfyui-workflow",
            workflow_path=self.settings.workflows_dir / self.settings.comfy_workflow_template,
        )
        ensure_action_ready(project, self.settings, "RENDER_SHOT", shot_number=shot_number)
        render_context = shot_render_context(project, shot_number)
        shot = render_context["shot"]
        ensure_continuity_lock(project)
        provider = getattr(self.generation_agent, "provider", None)
        supported_modes = {
            str(item).upper()
            for item in (getattr(provider, "supported_modes", frozenset({"T2V"})) or frozenset())
        }
        if str(shot.generation_mode or "").upper() not in supported_modes:
            raise ValueError(
                f"Shot {shot.number} is marked as {shot.generation_mode}, but the selected video provider supports "
                f"{', '.join(sorted(supported_modes)) or 'no generation modes'}."
            )
        if not shot.stale:
            mark_shot_stale(shot, f"shot_{shot_number}_render_requested")
        shot.status = "replanned"
        project.status = "rendering"
        invalidate_edit_outputs(project, reason=f"shot_{shot_number}_render_started", source="shot_media")
        project.logs.append(f"Generation Agent: Inspector submitted shot {shot_number} for single-shot regeneration.")
        self._save(project)
        previous_shot = render_context["previous_shot"]
        try:
            project.logs.append(self.render_shot(project, shot, previous_shot=previous_shot))
        except Exception as error:
            stage = failure_stage(error)
            record_failure(
                shot,
                error,
                stage=stage,
                increment_retry=not bool(getattr(shot, "error_code", "")),
            )
            record_failure(project, error, stage=stage)
            project.status = "render_failed"
            safe_message = error_info(error, stage=stage)["error_message"]
            project.logs.append(f"Generation Agent: Shot {shot_number} single-shot generation failed: {safe_message}")
            self._save(project)
            raise

        project.status = "ready_for_ai_edit" if shots_ready(project) else "awaiting_visual_review"
        if project.status == "awaiting_visual_review":
            project.logs.append(f"QC Agent: Shot {shot_number} integrity passed; MANUAL VISUAL REVIEW is required before it can enter SHOTS READY.")
        else:
            project.logs.append(f"QC Agent: Shot {shot_number} passed single-shot inspection; ready to continue assembling the full film.")
        self._save(project)
        return project

    def run_mock_production(
        self,
        project: Any,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> Any:
        """Advance the mock renderer through the same resumable shot contract."""

        def emit(event: dict[str, Any]) -> None:
            if event_callback is not None:
                event_callback(event)

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
            self._save(project)
        emit({"type": "agent_done", "agent": "generation"})
        project.status = "ready_for_ai_edit"
        project.logs.append(f"Generation Agent: {len(project.storyboard)}/{len(project.storyboard)} SHOTS READY; stage advanced to DELIVER.")
        project.logs.append("Editor Agent: Awaiting user dialogue lock before starting AI Edit Rough Cut.")
        self._save(project)
        return project

    def approve_shot(self, project: Any, shot_number: int) -> Any:
        """Record explicit human approval for a generated shot revision."""

        if self.settings is None:
            raise RuntimeError("RenderPipeline requires settings for Shot approval.")
        if not 1 <= shot_number <= len(project.storyboard):
            raise ValueError(f"Shot number must be between 1 and {len(project.storyboard)}.")
        ensure_action_ready(project, self.settings, "APPROVE_SHOT", shot_number=shot_number)
        shot = project.storyboard[shot_number - 1]
        project.logs.append(self.reviewer.approve_manual(shot, project_id=project.project_id))
        project.status = "ready_for_ai_edit" if shots_ready(project) else "awaiting_visual_review"
        if project.status == "ready_for_ai_edit":
            project.logs.append("QC Agent: All current shot revisions are explicitly approved; SHOTS READY.")
        self._save(project)
        return project


def shot_render_context(project: Any, shot_number: int) -> dict[str, Any]:
    """Build the renderer context for one shot without doing any I/O."""

    shots = list(getattr(project, "storyboard", []) or [])
    if not 1 <= int(shot_number) <= len(shots):
        raise ValueError(f"Shot number must be between 1 and {len(shots)}.")
    index = int(shot_number) - 1
    ensure_continuity_lock(project)
    build_state_ledger(project)
    state_record = state_record_for_shot(project, int(shot_number))
    return {
        "project_id": str(getattr(project, "project_id", "")),
        "shot": shots[index],
        "previous_shot": shots[index - 1] if index else None,
        "visual_bible": getattr(project, "visual_bible", {}) or {},
        "continuity_lock": getattr(project, "continuity_lock", {}) or {},
        "target_resolution": str(getattr(project, "target_resolution", "1080p") or "1080p"),
        "film_language": str(getattr(project, "film_language", "en") or "en"),
        "state_record": state_record,
    }

