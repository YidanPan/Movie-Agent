"""Generate individual shots using a pre-verified ComfyUI API workflow."""

from __future__ import annotations

import secrets
import shutil
from pathlib import Path
from typing import Any

from movie_agent.config import Settings
from movie_agent.models import Shot
from movie_agent.services.comfyui import ComfyUIClient, ComfyUIError, WorkflowOverrides, load_verified_workflow


def build_continuity_prompt(shot: Shot, visual_bible: dict[str, str], previous_shot: Shot | None = None) -> str:
    """Build a layered prompt with visual bible prefix + delta-only shot description.

    The visual bible lock cards (character_lock, scene_lock, cinematography_lock)
    provide persistent context for visual continuity. The shot's prompt field
    should contain only the delta: what changes from the previous shot.
    """
    character = visual_bible.get("character_lock", "")
    scene = visual_bible.get("scene_lock", "")
    cinema = visual_bible.get("cinematography_lock", "")
    delta = shot.prompt

    language = "English only: dialogue, narration, subtitles, title cards, credits, on-screen text, and monitor text."
    parts = [language, character, scene, cinema, delta]
    return ". ".join(parts) if parts else delta


class GenerationAgent:
    def __init__(self, settings: Settings, client: ComfyUIClient | None = None) -> None:
        self.settings = settings
        self.client = client or ComfyUIClient(settings.comfy_base_url, settings.comfy_timeout_seconds)

    def generate_mock(self, shot: Shot) -> str:
        shot.status = "generating_mock"
        shot.attempts += 1
        return f"Generation Agent: Shot {shot.number} entered the mock generation queue."

    def generate(self, project_id: str, shot: Shot, *, visual_bible: dict[str, str] | None = None, previous_shot: Shot | None = None) -> str:
        """Submit one planned shot and copy its MP4 into the project output folder."""
        if shot.generation_mode != "T2V":
            raise ComfyUIError(
                f"Shot {shot.number} is marked as {shot.generation_mode}, but the current MiniMax-H3 workflow only supports T2V."
            )
        existing_output = Path(shot.output_placeholder)
        if shot.status == "approved_comfyui" and existing_output.is_file():
            return f"Generation Agent: Shot {shot.number} already has an approved result; skipping duplicate generation."
        template_path = self.settings.workflows_dir / self.settings.comfy_workflow_template
        if not template_path.is_file():
            raise ComfyUIError(f"Verified workflow not found: {template_path}.")
        if not self.client.is_available():
            raise ComfyUIError("ComfyUI service is unavailable; please check the local Spark service.")

        shot.status = "generating_comfyui"
        shot.attempts += 1
        seed = secrets.randbelow(2**63 - 1)
        continuity_prompt = build_continuity_prompt(shot, visual_bible or {}, previous_shot)
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
            destination_dir = self.settings.outputs_dir / project_id / "shots"
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / f"shot-{shot.number:02d}.mp4"
            shutil.copy2(source, destination)
        except (ComfyUIError, OSError) as error:
            shot.status = "generation_failed"
            raise ComfyUIError(f"Shot {shot.number} generation failed: {error}") from error
        shot.output_placeholder = str(destination)
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
