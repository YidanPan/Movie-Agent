"""Generate individual shots using a pre-verified ComfyUI API workflow."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from movie_agent.config import Settings
from movie_agent.models import Shot
from movie_agent.services.comfyui import ComfyUIClient, ComfyUIError, WorkflowOverrides, load_verified_workflow
from movie_agent.services.media_quality import asset_record
from movie_agent.services.continuity import derive_shot_seed
from movie_agent.services.errors import clear_failure, error_info, record_failure
from movie_agent.services.render_input import compile_renderer_input
from movie_agent.services.revisions import ensure_shot_metadata, hash_shot_prompt, utc_now
from movie_agent.services.shot_context import ResolvedShotContext, resolve_shot_context
from movie_agent.storage.reference_bank import ReferenceBankStore


def _field(value: object, fallback: str = "Not specified") -> str:
    text = str(value or "").strip()
    return text or fallback


def _state_text(value: dict[str, Any] | None) -> str:
    if not value:
        return "none"
    lines: list[str] = []
    for entity, changes in value.items():
        if isinstance(changes, dict):
            lines.append(f"{entity}: " + "; ".join(f"{key} = {item}" for key, item in changes.items()))
        else:
            lines.append(f"{entity}: {changes}")
    return "\n".join(lines) or "none"


def build_continuity_prompt(
    shot: Shot,
    visual_bible: dict[str, Any],
    previous_shot: Shot | None = None,
    *,
    project_id: str = "ad-hoc-project",
    film_language: str = "en",
    context: ResolvedShotContext | None = None,
    story_world: dict[str, Any] | None = None,
) -> str:
    """Compile the complete renderer prompt from global locks plus Shot Delta.

    ``Shot.prompt`` intentionally remains a concise editorial delta.  T2V
    cannot see a previous frame, so the generation layer must provide the
    previous ending state and all persistent locks explicitly.  Keeping this
    compilation here also makes the exact model input inspectable after a
    retry.
    """

    context = context or resolve_shot_context(shot, visual_bible, story_world, previous_shot=previous_shot)
    character_locks = context.character_locks
    scene_lock = context.scene_lock
    cinema = _field(context.cinematography_lock)
    reference_seed = _field(visual_bible.get("reference_seed"), "42")
    sections = [
        f"FILM LANGUAGE\n{_field(film_language).lower()} only. All dialogue, narration, subtitles, title cards, credits, on-screen text, and monitor text must be in English.",
        f"SHOT SCENE ID\n{_field(shot.scene_id, 'unassigned')}",
        f"ACTIVE CHARACTER IDS\n{', '.join(context.character_ids) or 'none'}",
        "ACTIVE CHARACTER LOCKS\n" + "\n".join(
            f"- {item.get('character_id') or item.get('name') or 'character'}: {item.get('lock', '')}" for item in character_locks
        ),
        f"CURRENT SCENE LOCK\n{scene_lock.get('scene_id')}\n{scene_lock.get('lock') or 'not provided'}",
        f"ACTIVE PROP IDS\n{', '.join(context.prop_ids) or 'none'}",
        "ACTIVE PROP LOCKS\n" + "\n".join(
            f"- {item.get('prop_id') or item.get('name') or 'prop'}: {item.get('lock', '')}" for item in context.prop_locks
        ) if context.prop_locks else "ACTIVE PROP LOCKS\nnone",
        f"STORY FUNCTION\n{_field(shot.story_function or shot.narrative_purpose)}",
        f"EMOTIONAL SHIFT\n{_field(shot.emotional_shift, 'not provided')}",
        f"VISUAL MOTIF\n{_field(shot.visual_motif, 'not provided')}",
        f"CINEMATOGRAPHY LOCK\n{cinema}",
        f"PROJECT REFERENCE SEED\n{reference_seed}",
        f"PREVIOUS CONTEXT MODE\n{context.previous_context_mode}",
        f"PREVIOUS VISUAL REFERENCE ROLE\n{context.previous_visual_reference_role}",
        f"CURRENT ENTITY STATE\n{_state_text(context.entity_state_before)}",
        f"SHOT STATE DELTA\n{_state_text(context.entity_state_delta)}",
        f"EXPECTED END STATE\n{_state_text(context.entity_state_after)}",
        f"CONTEXT FLAGS\n{', '.join(context.context_flags) or 'none'}",
        f"CURRENT SHOT STARTING STATE\n{_field(shot.starting_state)}",
        f"CURRENT SHOT MAIN ACTION\n{_field(shot.main_action or shot.action)}",
        f"SECONDARY ACTION\n{_field(shot.secondary_action, 'none')}",
        f"ENVIRONMENT REACTION\n{_field(shot.environment_reaction, 'none')}",
        f"CHARACTER REACTION\n{_field(shot.character_reaction)}",
        f"CURRENT VISUAL EVENT\n{_field(shot.image_description)}",
        f"SHOT DELTA\n{_field(shot.prompt)}",
        f"ENDING STATE\n{_field(shot.ending_state or shot.continuity_to)}",
        f"TRANSITION HOOK\n{_field(shot.transition_hook)}",
        f"TRANSITION TYPE\n{_field(shot.transition_type, 'CONTINUOUS')}",
        f"SOUND DESIGN\n{_field(shot.sound_design)}",
        "NEGATIVE CONSTRAINTS\nNo existing film or TV characters, titles, logos, brands, real-person likenesses, copyrighted designs, or language other than English in the generated film.",
    ]
    if context.inherit_previous_narrative_context:
        sections.insert(13, f"PREVIOUS NARRATIVE STATE\n{_field(context.previous_narrative_state or context.previous_ending_state)}")
        sections.insert(14, f"PREVIOUS NARRATIVE HOOK\n{_field(context.previous_narrative_hook or context.previous_transition_hook)}")
    if context.previous_context_mode in {"FULL_CONTINUITY", "ACTION_CONTINUITY"} and context.allow_previous_visual_reference:
        sections.insert(15, f"PREVIOUS SHOT ENDING STATE\n{_field(context.previous_ending_state)}")
        sections.insert(16, f"PREVIOUS SHOT TRANSITION HOOK\n{_field(context.previous_transition_hook)}")
        sections.insert(17, f"PREVIOUS SHOT VISUAL REFERENCE\n{context.previous_visual_reference_role}")
    elif context.previous_context_mode == "COMPOSITION_ONLY":
        framing = _field(getattr(previous_shot, "framing", ""), "not provided")
        sections.insert(15, f"PREVIOUS COMPOSITION CONTEXT\n{framing}; composition only; do not inherit previous scene identity")
    elif not context.allow_previous_visual_reference:
        sections.insert(15, "PREVIOUS VISUAL CONTEXT\nnone; establish from the current scene lock")
    # Include the derived seed in the compiled prompt so a human can audit a
    # retry and verify that the model input and ComfyUI override agree.
    shot_seed = derive_shot_seed(project_id, reference_seed, shot.number)
    sections.insert(5, f"SHOT DERIVED SEED\n{shot_seed}")
    return "\n\n".join(sections)


class GenerationAgent:
    def __init__(self, settings: Settings, client: ComfyUIClient | None = None) -> None:
        self.settings = settings
        self.client = client or ComfyUIClient(settings.comfy_base_url, settings.comfy_timeout_seconds)
        self.reference_bank = ReferenceBankStore(settings.outputs_dir)

    def generate_mock(self, shot: Shot) -> str:
        ensure_shot_metadata(shot, provider="mock", model="mock-rule-engine")
        if shot.status == "approved_mock" and not shot.stale:
            return f"Generation Agent: Shot {shot.number} already has an approved mock result; reusing current revision {shot.revision}."
        clear_failure(shot)
        shot.status = "generating_mock"
        shot.stale = False
        shot.qc_status = "PENDING"
        shot.attempts += 1
        return f"Generation Agent: Shot {shot.number} entered the mock generation queue."

    def generate(
        self,
        project_id: str,
        shot: Shot,
        *,
        visual_bible: dict[str, str] | None = None,
        previous_shot: Shot | None = None,
        target_resolution: str = "1080p",
        film_language: str = "en",
        story_world: dict[str, Any] | None = None,
        context: ResolvedShotContext | None = None,
    ) -> str:
        """Submit one planned shot and copy its MP4 into the project output folder."""
        if shot.generation_mode != "T2V":
            error = ComfyUIError(
                f"Shot {shot.number} is marked as {shot.generation_mode}, but the current MiniMax-H3 workflow only supports T2V."
            )
            record_failure(shot, error, stage="generation")
            shot.status = "generation_failed"
            shot.qc_status = "FAILED"
            raise error
        existing_output = Path(shot.output_placeholder)
        if shot.status == "approved_comfyui" and not shot.stale and existing_output.is_file():
            return f"Generation Agent: Shot {shot.number} already has an approved result; skipping duplicate generation."
        template_path = self.settings.workflows_dir / self.settings.comfy_workflow_template
        if not template_path.is_file():
            error = ComfyUIError(f"Verified workflow not found: {template_path}.")
            record_failure(shot, error, stage="generation")
            shot.status = "generation_failed"
            shot.qc_status = "FAILED"
            raise error
        if not self.client.is_available():
            error = ComfyUIError("ComfyUI service is unavailable; please check the local Spark service.")
            record_failure(shot, error, stage="generation")
            shot.status = "generation_failed"
            shot.qc_status = "FAILED"
            raise error

        visual_context = visual_bible or {}
        reference_seed = str(visual_context.get("reference_seed") or "42")
        context = context or resolve_shot_context(shot, visual_context, story_world, previous_shot)
        if any(context.missing_entities.values()):
            raise ValueError(f"STORY_WORLD_REVIEW_REQUIRED: missing entities {context.missing_entities}")
        if any(context.missing_locks.values()):
            raise ValueError(f"VISUAL_BIBLE_REVIEW_REQUIRED: missing locks {context.missing_locks}")
        clear_failure(shot)
        shot.status = "generating_comfyui"
        shot.stale = False
        shot.qc_status = "PENDING"
        shot.attempts += 1
        # Derive the seed before compiling the manifest.  The seed is a real
        # renderer input and must not appear only after the first fingerprint.
        seed = derive_shot_seed(project_id, reference_seed, shot.number)
        reference_inputs = self.reference_bank.generation_reference_paths(project_id, shot, previous_shot, context=context)
        reference_flags = list(reference_inputs.get("reference_flags") or [])
        shot.qc_details = {
            **(shot.qc_details or {}),
            "reference_inputs": {
                key: [str(path) for path in paths]
                for key, paths in reference_inputs.items()
                if key != "reference_flags"
            },
            "reference_flags": reference_flags,
            "reference_strategy": "TEXTUAL_LOCK_ONLY_T2V",
            "resolved_shot_context": context.to_dict(),
        }
        continuity_prompt = build_continuity_prompt(
            shot,
            visual_context,
            previous_shot,
            project_id=project_id,
            film_language=film_language,
            context=context,
            story_world=story_world,
        )
        shot.generation_seed = seed
        shot.seed = seed
        shot.compiled_generation_prompt = continuity_prompt
        workflow = load_verified_workflow(
            template_path,
            # Generate at the native duration. Editorial timing operations are
            # applied later in the AI Edit sequence and must not break the
            # shared visual continuity lock.
            WorkflowOverrides(
                prompt=continuity_prompt,
                seed=seed,
                duration_seconds=shot.source_duration_seconds or shot.duration_seconds,
            ),
        )
        manifest = compile_renderer_input(
            project=SimpleNamespace(
                project_id=project_id,
                visual_bible=visual_context,
                story_world=story_world or {},
            ),
            shot=shot,
            previous_shot=previous_shot,
            context=context,
            workflow_path=template_path,
            compiled_prompt=continuity_prompt,
            derived_seed=seed,
            submitted_workflow=workflow,
            workflow_identity=self.settings.comfy_workflow_template or "verified-comfyui-workflow",
            film_language=film_language,
        )
        shot.generation_input_hash = manifest.fingerprint()
        shot.qc_details["renderer_manifest"] = manifest.audit_dict()
        ensure_shot_metadata(
            shot,
            provider="comfyui",
            model=self.settings.comfy_workflow_template or "verified-comfyui-workflow",
            seed=seed,
        )
        try:
            prompt_id = self.client.submit(workflow)
            result = self.client.wait_for_completion(prompt_id)
            source = self._resolve_video(result)
            destination_dir = self.settings.outputs_dir / project_id / "shots" / "source"
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / f"shot-{shot.number:02d}.mp4"
            shutil.copy2(source, destination)
        except (ComfyUIError, OSError) as error:
            record_failure(shot, error, stage="generation")
            shot.status = "generation_failed"
            shot.qc_status = "FAILED"
            safe_message = error_info(error, stage="generation")["error_message"]
            raise ComfyUIError(f"Shot {shot.number} generation failed: {safe_message}") from error
        shot.output_placeholder = str(destination)
        # The model output is the immutable source.  It must not be labelled a
        # Final Master until normalization/edit approval has produced one.
        # A regenerated source invalidates any normalized per-shot master;
        # the previous record remains in ``asset_history`` for comparison.
        shot.media_assets.pop("final_master", None)
        shot.media_assets["source"] = asset_record(
            destination,
            tier="source",
            ffprobe_bin=self.settings.ffprobe_bin,
            target_resolution=target_resolution,
            source="comfyui_original",
            revision=shot.revision,
            prompt_hash=shot.prompt_hash or hash_shot_prompt(shot),
            generation_input_hash=shot.generation_input_hash,
            provider="comfyui",
            model=self.settings.comfy_workflow_template or "verified-comfyui-workflow",
            seed=shot.seed,
            workflow_template_digest=manifest.workflow_template_digest,
            submitted_workflow_digest=manifest.submitted_workflow_digest,
            compiled_prompt_digest=manifest.compiled_prompt_digest,
            derived_seed=manifest.derived_seed,
            source_duration_seconds=manifest.source_duration_seconds,
            renderer_manifest_version=manifest.to_dict()["renderer_manifest_version"],
            renderer_contract_status=manifest.contract_status,
            renderer_verification_status="VERIFIED",
            external_input_digests=manifest.external_input_digests,
            created_at=utc_now(),
            qc_status="PENDING",
        )
        source_record = shot.media_assets.get("source") or {}
        shot.source_resolution = source_record.get("source_resolution")
        shot.source_fps = source_record.get("source_fps")
        shot.source_duration = source_record.get("source_duration")
        shot.stale = False
        shot.status = "generated_comfyui"
        return f"Generation Agent: Shot {shot.number} completed (ComfyUI task {prompt_id})."

    def _resolve_video(self, result: dict[str, Any]) -> Path:
        outputs = result.get("outputs")
        if not isinstance(outputs, dict):
            raise ComfyUIError("ComfyUI task returned no output nodes.")
        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            for key in ("images", "videos"):
                files = node_output.get(key)
                if not isinstance(files, list):
                    continue
                for file_info in files:
                    if not isinstance(file_info, dict):
                        continue
                    filename = file_info.get("filename")
                    if not isinstance(filename, str) or not filename.lower().endswith(".mp4"):
                        continue
                    subfolder = file_info.get("subfolder", "")
                    if not isinstance(subfolder, str):
                        continue
                    candidate = self.settings.comfy_output_dir / subfolder / filename
                    if candidate.is_file():
                        return candidate
        raise ComfyUIError("ComfyUI completed, but no readable MP4 output file was found.")
