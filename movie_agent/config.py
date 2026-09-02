"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        """Allow command-line deployments that export environment variables themselves."""
        return False


@dataclass(frozen=True)
class Settings:
    comfy_base_url: str
    comfy_timeout_seconds: int
    workflows_dir: Path
    port: int
    projects_dir: Path
    mock_mode: bool
    model_provider: str = "mock"
    modelscope_api_key: str | None = None
    modelscope_api_base: str = "https://api-inference.modelscope.cn/v1"
    modelscope_model: str = "Qwen/Qwen3-30B-A3B-Instruct-2507"
    video_generation_mode: str = "mock"
    comfy_workflow_template: str = "minimax_h3_t2v_api.json"
    comfy_output_dir: Path = Path("./comfy-output")
    outputs_dir: Path = Path("./outputs")
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    comfy_max_retries: int = 2
    modelscope_timeout_seconds: int = 90
    modelscope_max_retries: int = 2

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            comfy_base_url=os.getenv("COMFY_BASE_URL", "http://127.0.0.1:8188"),
            comfy_timeout_seconds=int(os.getenv("COMFY_TIMEOUT_SECONDS", "900")),
            workflows_dir=Path(os.getenv("WORKFLOWS_DIR", "./workflows")),
            port=int(os.getenv("PORT", "9071")),
            projects_dir=Path(os.getenv("PROJECTS_DIR", "./projects")),
            mock_mode=os.getenv("MOCK_MODE", "true").lower() == "true",
            model_provider=os.getenv("MODEL_PROVIDER", "mock").lower(),
            modelscope_api_key=os.getenv("MODELSCOPE_API_KEY") or None,
            modelscope_api_base=os.getenv("MODELSCOPE_API_BASE", "https://api-inference.modelscope.cn/v1"),
            modelscope_model=os.getenv("MODELSCOPE_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507"),
            video_generation_mode=os.getenv("VIDEO_GENERATION_MODE", "mock").lower(),
            comfy_workflow_template=os.getenv("COMFY_WORKFLOW_TEMPLATE", "minimax_h3_t2v_api.json"),
            comfy_output_dir=Path(os.getenv("COMFY_OUTPUT_DIR", "./comfy-output")),
            outputs_dir=Path(os.getenv("OUTPUTS_DIR", "./outputs")),
            ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
            ffprobe_bin=os.getenv("FFPROBE_BIN", "ffprobe"),
            comfy_max_retries=max(1, int(os.getenv("COMFY_MAX_RETRIES", "2"))),
            modelscope_timeout_seconds=max(10, int(os.getenv("MODELSCOPE_TIMEOUT_SECONDS", "90"))),
            modelscope_max_retries=max(1, int(os.getenv("MODELSCOPE_MAX_RETRIES", "2"))),
        )
