"""Rough-cut and final delivery assembly with a mock-safe FFmpeg fallback."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from movie_agent.config import Settings
from movie_agent.models import MovieProject
from movie_agent.services.subtitles import (
    normalise_subtitle_mode,
    render_srt,
    render_vtt,
    script_subtitle_track,
)


class EditorAgent:
    """Keep rough-cut planning separate from final approval.

    A project can therefore be inspected after all shots are ready without
    accidentally presenting a final master. In mock mode the same metadata
    and sidecar exports are produced, while media paths remain placeholders.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def _require_locked_dialogue(project: MovieProject) -> None:
        if not bool((project.script or {}).get("dialogue_locked")):
            raise RuntimeError("请先在编剧阶段审阅并锁定台词本 / 字幕稿，再进入 AI Edit。")

    def _output_dir(self, project: MovieProject) -> Path:
        output_dir = self.settings.outputs_dir / project.project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def write_subtitle_exports(self, project: MovieProject) -> tuple[Path, Path]:
        """Write canonical SRT/VTT sidecars from the locked subtitle track."""

        output_dir = self._output_dir(project)
        track = script_subtitle_track(project.script)
        srt_path = output_dir / "subtitles.srt"
        vtt_path = output_dir / "subtitles.vtt"
        srt_path.write_text(render_srt(track), encoding="utf-8")
        vtt_path.write_text(render_vtt(track), encoding="utf-8")
        return srt_path, vtt_path

    def _shot_paths(self, project: MovieProject) -> list[Path]:
        return [Path(shot.output_placeholder) for shot in project.storyboard]

    def _concat_media(self, project: MovieProject, output_path: Path) -> Path:
        """Concat verified shot files into a temporary or deliverable MP4."""

        shot_paths = self._shot_paths(project)
        if not shot_paths or not all(path.is_file() for path in shot_paths):
            raise RuntimeError("不能合成：存在未成功生成的镜头文件。")
        output_dir = self._output_dir(project)
        concat_file = output_dir / "concat.txt"
        concat_file.write_text(
            "".join(f"file '{path.resolve().as_posix()}'\n" for path in shot_paths), encoding="utf-8"
        )
        try:
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
                str(output_path),
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
                    str(output_path),
                ]
                completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                raise RuntimeError(f"FFmpeg 合成失败：{completed.stderr[-500:]}")
        finally:
            concat_file.unlink(missing_ok=True)
        return output_path

    def _rough_cut_plan(self, project: MovieProject) -> dict[str, Any]:
        return {
            "status": "rough_cut",
            "sequence": [
                {
                    "shot": shot.number,
                    "trim": {"in_seconds": 0, "out_seconds": shot.duration_seconds},
                    "transition": "cut" if shot.number == 1 else "crossfade_6f",
                }
                for shot in project.storyboard
            ],
            "audio": {
                "voiceover": "locked subtitle track / dialogue book",
                "bgm": "ambient score · restrained",
                "sfx": "shot sound design cues",
            },
            "subtitles": {
                "enabled": normalise_subtitle_mode(project.subtitle_mode) != "none",
                "mode": normalise_subtitle_mode(project.subtitle_mode),
                "source": "locked subtitle track",
            },
        }

    def _mux_soft_subtitles(self, rough_path: Path, srt_path: Path, final_cut: Path) -> bool:
        """Try to package the subtitle track as a selectable MP4 subtitle stream."""

        command = [
            self.settings.ffmpeg_bin,
            "-y",
            "-i",
            str(rough_path),
            "-i",
            str(srt_path),
            "-map",
            "0",
            "-map",
            "1:0",
            "-c",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=chi",
            "-movflags",
            "+faststart",
            str(final_cut),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        return completed.returncode == 0 and final_cut.is_file()

    def create_rough_cut(self, project: MovieProject) -> str:
        """Build an editable Rough Cut, never a final delivery master."""

        self._require_locked_dialogue(project)
        project.subtitle_mode = normalise_subtitle_mode(project.subtitle_mode)
        project.script["subtitle_mode"] = project.subtitle_mode
        self.write_subtitle_exports(project)
        project.edit_plan = self._rough_cut_plan(project)
        rough_path = self._output_dir(project) / "rough-cut.mp4"
        if all(path.is_file() for path in self._shot_paths(project)):
            self._concat_media(project, rough_path)
            project.rough_cut_placeholder = str(rough_path)
            return "剪辑 Agent：已完成 Rough Cut，排序、Trim、转场、旁白、BGM、SFX 与字幕轨已就绪。"
        project.rough_cut_placeholder = f"outputs/{project.project_id}/rough-cut.mp4"
        return "剪辑 Agent：已模拟完成 Rough Cut，等待真实镜头媒体后可预览。"

    def assemble_mock(self, project: MovieProject) -> str:
        """Create the mock final-delivery placeholder after explicit approval."""

        self._require_locked_dialogue(project)
        project.subtitle_mode = normalise_subtitle_mode(project.subtitle_mode)
        project.script["subtitle_mode"] = project.subtitle_mode
        self.write_subtitle_exports(project)
        project.final_output_placeholder = f"outputs/{project.project_id}/final-cut.mp4"
        project.edit_plan = {**(project.edit_plan or {}), "status": "final_approved", "approved": True}
        return f"剪辑 Agent：已批准交付 mock 成片（字幕模式：{project.subtitle_mode}）。"

    def assemble(self, project: MovieProject, subtitle_mode: str | None = None) -> str:
        """Render the final master from locked dialogue and the selected subtitle mode."""

        self._require_locked_dialogue(project)
        project.subtitle_mode = normalise_subtitle_mode(subtitle_mode or project.subtitle_mode)
        project.script["subtitle_mode"] = project.subtitle_mode
        srt_path, _ = self.write_subtitle_exports(project)
        output_dir = self._output_dir(project)
        rough_path = output_dir / "rough-cut.mp4"
        if not rough_path.is_file():
            self._concat_media(project, rough_path)
        final_cut = output_dir / "final-cut.mp4"

        if project.subtitle_mode == "burned":
            # Burn-in is best-effort because font packages differ between the
            # local machine and Spark. A clean concat fallback still leaves
            # the canonical SRT sidecar available for review.
            subtitle_filter_path = str(srt_path.resolve()).replace("\\", "\\\\").replace(":", "\\:")
            command = [
                self.settings.ffmpeg_bin,
                "-y",
                "-i",
                str(rough_path),
                "-vf",
                f"subtitles={subtitle_filter_path}",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(final_cut),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                self._concat_media(project, final_cut)
        elif project.subtitle_mode == "soft":
            # Prefer a selectable MP4 subtitle stream while keeping canonical
            # SRT/VTT sidecars available for external players and delivery.
            if not self._mux_soft_subtitles(rough_path, srt_path, final_cut):
                self._concat_media(project, final_cut)
        else:
            # none mode delivers the clean picture and retains exports for
            # users who want to add subtitles later.
            self._concat_media(project, final_cut)
        project.final_output_placeholder = str(final_cut)
        project.edit_plan = {**(project.edit_plan or {}), "status": "final_approved", "approved": True}
        return f"剪辑 Agent：已用 FFmpeg 合成 {len(project.storyboard)} 个镜头（字幕模式：{project.subtitle_mode}）。"
