"""Generate individual shots using a pre-verified ComfyUI API workflow."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from movie_agent.config import Settings
from movie_agent.models import Shot
from movie_agent.services.comfyui import ComfyUIClient, ComfyUIError, WorkflowOverrides, load_verified_workflow
from movie_agent.services.media_quality import asset_record
from movie_agent.services.continuity import derive_shot_seed
from movie_agent.services.revisions import ensure_shot_metadata, hash_shot_prompt, utc_now


def _field(value: object, fallback: str = "Not specified") -> str:
    text = str(value or "").strip()
    return text or fallback


def build_continuity_prompt(
    shot: Shot,
    visual_bible: dict[str, Any],
    previous_shot: Shot | None = None,
    *,
    project_id: str = "ad-hoc-project",
    film_language: str = "en",
) -> str:
    """Compile the complete renderer prompt from global locks plus Shot Delta.

    ``Shot.prompt`` intentionally remains a concise editorial delta.  T2V
    cannot see a previous frame, so the generation layer must provide the
    previous ending state and all persistent locks explicitly.  Keeping this
    compilation here also makes the exact model input inspectable after a
    retry.
    """

    character = _field(visual_bible.get("character_lock") or visual_bible.get("character_card"))
    scene = _field(visual_bible.get("scene_lock") or visual_bible.get("scene_card"))
    cinema = _field(
        visual_bible.get("cinematography_lock") or visual_bible.get("style_card")
    )
    reference_seed = _field(visual_bible.get("reference_seed"), "42")
    previous_ending = "OPENING FRAME — no previous shot" if previous_shot is None else _field(
        previous_shot.ending_state or previous_shot.action
    )
    previous_hook = "Establish the world and the protagonist." if previous_shot is None else _field(
        previous_shot.transition_hook
    )
    sections = [
        f"FILM LANGUAGE\n{_field(film_language).lower()} only. All dialogue, narration, subtitles, title cards, credits, on-screen text, and monitor text must be in English.",
        f"GLOBAL CHARACTER LOCK\n{character}",
        f"GLOBAL SCENE LOCK\n{scene}",
        f"CINEMATOGRAPHY LOCK\n{cinema}",
        f"PROJECT REFERENCE SEED\n{reference_seed}",
        f"PREVIOUS SHOT ENDING STATE\n{previous_ending}",
        f"PREVIOUS SHOT TRANSITION HOOK\n{previous_hook}",
        f"CURRENT SHOT STARTING STATE\n{_field(shot.starting_state)}",
        f"CURRENT SHOT MAIN ACTION\n{_field(shot.main_action or shot.action)}",
        f"CHARACTER REACTION\n{_field(shot.character_reaction)}",
        f"CURRENT VISUAL EVENT\n{_field(shot.image_description)}",
        f"SHOT DELTA\n{_field(shot.prompt)}",
        f"TRANSITION HOOK\n{_field(shot.transition_hook)}",
        f"SOUND DESIGN\n{_field(shot.sound_design)}",
        "NEGATIVE CONSTRAINTS\nNo existing film or TV characters, titles, logos, brands, real-person likenesses, copyrighted designs, or language other than English in the generated film.",
    ]
    # Include the derived seed in the compiled prompt so a human can audit a
    # retry and verify that the model input and ComfyUI override agree.
    shot_seed = derive_shot_seed(project_id, reference_seed, shot.number)
    sections.insert(5, f"SHOT DERIVED SEED\n{shot_seed}")
    return "\n\n".join(sections)


class GenerationAgent:
    def __init__(self, settings: Settings, client: ComfyUIClient | None = None) -> None:
        self.settings = settings
        self.client = client or ComfyUIClient(settings.comfy_base_url, settings.comfy_timeout_seconds)

    def generate_mock(self, shot: Shot) -> str:
        ensure_shot_metadata(shot, provider="mock", model="mock-rule-engine")
        if shot.status == "approved_mock" and not shot.stale:
            return f"Generation Agent: Shot {shot.number} already has an approved mock result; reusing current revision {shot.revision}."
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
    ) -> str:
        """Submit one planned shot and copy its MP4 into the project output folder."""
        if shot.generation_mode != "T2V":
            raise ComfyUIError(
                f"Shot {shot.number} is marked as {shot.generation_mode}, but the current MiniMax-H3 workflow only supports T2V."
            )
        existing_output = Path(shot.output_placeholder)
        if shot.status == "approved_comfyui" and not shot.stale and existing_output.is_file():
            return f"Generation Agent: Shot {shot.number} already has an approved result; skipping duplicate generation."
        template_path = self.settings.workflows_dir / self.settings.comfy_workflow_template
        if not template_path.is_file():
            raise ComfyUIError(f"Verified workflow not found: {template_path}.")
        if not self.client.is_available():
            raise ComfyUIError("ComfyUI service is unavailable; please check the local Spark service.")

        shot.status = "generating_comfyui"
        shot.stale = False
        shot.qc_status = "PENDING"
        shot.attempts += 1
        visual_context = visual_bible or {}
        reference_seed = str(visual_context.get("reference_seed") or "42")
        seed = derive_shot_seed(project_id, reference_seed, shot.number)
        continuity_prompt = build_continuity_prompt(
            shot,
            visual_context,
            previous_shot,
            project_id=project_id,
            film_language=film_language,
        )
        shot.generation_seed = seed
        shot.seed = seed
        ensure_shot_metadata(
            shot,
            provider="comfyui",
            model=self.settings.comfy_workflow_template or "verified-comfyui-workflow",
            seed=seed,
        )
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
        try:
            prompt_id = self.client.submit(workflow)
            result = self.client.wait_for_completion(prompt_id)
            source = self._resolve_video(result)
            destination_dir = self.settings.outputs_dir / project_id / "shots" / "source"
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / f"shot-{shot.number:02d}.mp4"
            shutil.copy2(source, destination)
        except (ComfyUIError, OSError) as error:
            shot.status = "generation_failed"
            raise ComfyUIError(f"Shot {shot.number} generation failed: {error}") from error
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
            provider="comfyui",
            model=self.settings.comfy_workflow_template or "verified-comfyui-workflow",
            seed=shot.seed,
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
