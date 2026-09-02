"""Generate individual shots using a pre-verified ComfyUI API workflow."""

from __future__ import annotations

import secrets
import shutil
from pathlib import Path
from typing import Any

from movie_agent.config import Settings
from movie_agent.models import Shot
from movie_agent.services.comfyui import ComfyUIClient, ComfyUIError, WorkflowOverrides, load_verified_workflow


class GenerationAgent:
    def __init__(self, settings: Settings, client: ComfyUIClient | None = None) -> None:
        self.settings = settings
        self.client = client or ComfyUIClient(settings.comfy_base_url, settings.comfy_timeout_seconds)

    def generate_mock(self, shot: Shot) -> str:
        shot.status = "generating_mock"
        shot.attempts += 1
        return f"生成 Agent：镜头 {shot.number} 已进入 mock 生成队列。"

    def generate(self, project_id: str, shot: Shot) -> str:
        """Submit one planned shot and copy its MP4 into the project output folder."""
        if shot.generation_mode != "T2V":
            raise ComfyUIError(
                f"镜头 {shot.number} 标记为 {shot.generation_mode}，但当前 MiniMax-H3 工作流仅支持 T2V。"
            )
        existing_output = Path(shot.output_placeholder)
        if shot.status == "approved_comfyui" and existing_output.is_file():
            return f"生成 Agent：镜头 {shot.number} 已有通过质检的结果，跳过重复生成。"
        template_path = self.settings.workflows_dir / self.settings.comfy_workflow_template
        if not template_path.is_file():
            raise ComfyUIError(f"未找到已验证工作流：{template_path}。")
        if not self.client.is_available():
            raise ComfyUIError("ComfyUI 服务不可用，请检查 Spark 本机服务。")

        shot.status = "generating_comfyui"
        shot.attempts += 1
        seed = secrets.randbelow(2**63 - 1)
        workflow = load_verified_workflow(
            template_path,
            WorkflowOverrides(prompt=shot.prompt, seed=seed, duration_seconds=shot.duration_seconds),
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
            raise ComfyUIError(f"镜头 {shot.number} 生成失败：{error}") from error
        shot.output_placeholder = str(destination)
        shot.status = "generated_comfyui"
        return f"生成 Agent：镜头 {shot.number} 已完成（ComfyUI 任务 {prompt_id}）。"

    def _resolve_video(self, result: dict[str, Any]) -> Path:
        outputs = result.get("outputs")
        if not isinstance(outputs, dict):
            raise ComfyUIError("ComfyUI 任务未返回输出节点。")
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
        raise ComfyUIError("ComfyUI 已完成，但未找到可读取的 MP4 输出文件。")
