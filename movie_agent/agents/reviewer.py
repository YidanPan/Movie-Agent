"""Output integrity checks for generated shots."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from movie_agent.config import Settings
from movie_agent.models import Shot


class ReviewerAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def review_mock(self, shot: Shot) -> str:
        shot.status = "approved_mock"
        return f"质检 Agent：镜头 {shot.number} 通过 mock 一致性与合规检查。"

    def review_generated(self, shot: Shot) -> str:
        if shot.status != "generated_comfyui":
            raise RuntimeError(f"镜头 {shot.number} 尚未生成完成，不能进入质检。")
        duration = self._video_duration(Path(shot.output_placeholder))
        tolerance = max(1.5, shot.duration_seconds * 0.25)
        if abs(duration - shot.duration_seconds) > tolerance:
            raise RuntimeError(
                f"镜头 {shot.number} 时长异常：目标 {shot.duration_seconds}s，实际 {duration:.2f}s。"
            )
        shot.status = "approved_comfyui"
        return f"质检 Agent：镜头 {shot.number} 完整性通过（{duration:.2f}s），待人工画面复核。"

    def _video_duration(self, path: Path) -> float:
        if not path.is_file():
            raise RuntimeError("质检找不到镜头 MP4 文件。")
        command = [
            self.settings.ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type",
            "-of",
            "json",
            str(path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"ffprobe 无法读取镜头文件：{completed.stderr[-300:]}")
        try:
            payload = json.loads(completed.stdout)
            duration = float(payload["format"]["duration"])
            streams = payload.get("streams", [])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("ffprobe 返回了无法解析的媒体信息。") from error
        if duration <= 0 or not any(stream.get("codec_type") == "video" for stream in streams):
            raise RuntimeError("镜头文件缺少有效视频流或时长。")
        return duration
