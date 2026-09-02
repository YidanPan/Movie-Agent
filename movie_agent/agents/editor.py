"""FFmpeg-backed final assembly with a mock fallback."""

from __future__ import annotations

import subprocess
from pathlib import Path

from movie_agent.config import Settings
from movie_agent.models import MovieProject


class EditorAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def assemble_mock(self, project: MovieProject) -> str:
        project.final_output_placeholder = f"outputs/{project.project_id}/final-cut.mp4"
        return "剪辑 Agent：已模拟合并镜头、字幕和音轨。"

    def assemble(self, project: MovieProject) -> str:
        output_dir = self.settings.outputs_dir / project.project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        final_cut = output_dir / "final-cut.mp4"
        shot_paths = [Path(shot.output_placeholder) for shot in project.storyboard]
        if not all(path.is_file() for path in shot_paths):
            raise RuntimeError("不能合成：存在未成功生成的镜头文件。")

        concat_file = output_dir / "concat.txt"
        concat_file.write_text(
            "".join(f"file '{path.resolve().as_posix()}'\\n" for path in shot_paths), encoding="utf-8"
        )
        command = [
            self.settings.ffmpeg_bin,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(final_cut),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            command = [
                self.settings.ffmpeg_bin,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(final_cut),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
        concat_file.unlink(missing_ok=True)
        if completed.returncode != 0:
            raise RuntimeError(f"FFmpeg 合成失败：{completed.stderr[-500:]}")
        project.final_output_placeholder = str(final_cut)
        return f"剪辑 Agent：已用 FFmpeg 合成 {len(shot_paths)} 个镜头。"
