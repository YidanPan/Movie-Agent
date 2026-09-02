"""Output integrity checks for generated shots."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from movie_agent.config import Settings
from movie_agent.models import Shot
from movie_agent.services.llm import ModelScopeLLM, build_vision_llm


class ReviewerAgent:
    def __init__(self, settings: Settings, vision_llm: ModelScopeLLM | None = None) -> None:
        self.settings = settings
        self.vision_llm = vision_llm or build_vision_llm(settings)
        self._reference_frames: dict[str, Path] = {}

    def review_mock(self, shot: Shot) -> str:
        shot.status = "approved_mock"
        return f"质检 Agent：镜头 {shot.number} 通过 mock 一致性与合规检查。"

    def review_generated(
        self,
        shot: Shot,
        *,
        project_id: str | None = None,
        visual_bible: dict[str, str] | None = None,
    ) -> str:
        if shot.status != "generated_comfyui":
            raise RuntimeError(f"镜头 {shot.number} 尚未生成完成，不能进入质检。")
        video_path = Path(shot.output_placeholder)
        duration = self._video_duration(video_path)
        tolerance = max(1.5, shot.duration_seconds * 0.25)
        if abs(duration - shot.duration_seconds) > tolerance:
            raise RuntimeError(
                f"镜头 {shot.number} 时长异常：目标 {shot.duration_seconds}s，实际 {duration:.2f}s。"
            )
        if project_id is None:
            # Backwards-compatible fallback for integrations that only inspect a single shot.
            project_id = "ad-hoc-review"
        frames = self._extract_keyframes(project_id, shot, video_path, duration)
        if self.vision_llm is None:
            shot.status = "approved_comfyui"
            return (
                f"质检 Agent：镜头 {shot.number} 完整性通过（{duration:.2f}s），"
                f"{len(frames)} 张关键帧已归档；未配置视觉模型，待人工复核角色与场景一致性。"
            )

        review = self._review_visual_consistency(project_id, shot, visual_bible or {}, frames)
        self._write_visual_review(project_id, shot.number, review)
        verdict = str(review.get("verdict", "")).strip().lower()
        character_score = self._score(review.get("character_consistency"))
        scene_score = self._score(review.get("scene_consistency"))
        copyright_risk = str(review.get("copyright_risk", "")).strip().lower()
        if verdict == "fail" or character_score < 70 or scene_score < 70 or copyright_risk == "high":
            raise RuntimeError(
                f"镜头 {shot.number} 视觉质检未通过：角色一致性 {character_score}/100，"
                f"场景一致性 {scene_score}/100，版权风险 {copyright_risk or '未知'}。"
            )
        self._reference_frames.setdefault(project_id, frames[len(frames) // 2])
        shot.status = "approved_comfyui"
        review_note = str(review.get("review_note", "已完成视觉审核。")).strip()
        return (
            f"质检 Agent：镜头 {shot.number} 完整性与视觉审核通过（{duration:.2f}s，"
            f"角色 {character_score}/100，场景 {scene_score}/100）。{review_note}"
        )

    def _extract_keyframes(self, project_id: str, shot: Shot, video_path: Path, duration: float) -> list[Path]:
        output_dir = self.settings.outputs_dir / project_id / "quality" / f"shot-{shot.number:02d}"
        output_dir.mkdir(parents=True, exist_ok=True)
        frames: list[Path] = []
        for index, timestamp in enumerate(
            self._keyframe_timestamps(duration, self.settings.vision_keyframes_per_shot), start=1
        ):
            frame_path = output_dir / f"frame-{index:02d}-{timestamp:.2f}s.jpg"
            command = [
                self.settings.ffmpeg_bin,
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(frame_path),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode != 0 or not frame_path.is_file():
                raise RuntimeError(f"镜头 {shot.number} 关键帧提取失败：{completed.stderr[-300:]}")
            frames.append(frame_path)
        return frames

    @staticmethod
    def _keyframe_timestamps(duration: float, count: int) -> list[float]:
        """Choose interior samples so fades on the first/last frame do not dominate review."""
        return [max(0.01, duration * index / (count + 1)) for index in range(1, count + 1)]

    def _review_visual_consistency(
        self,
        project_id: str,
        shot: Shot,
        visual_bible: dict[str, str],
        frames: list[Path],
    ) -> dict[str, Any]:
        reference = self._reference_frames.get(project_id)
        images = ([reference] if reference else []) + frames
        reference_note = "第一张图片是此前通过的角色/场景参考帧；后续图片是当前镜头的关键帧。" if reference else "所有图片均为当前镜头的关键帧。"
        return self.vision_llm.complete_vision_json(
            "你是电影后期视觉质检员。只依据提供的帧和视觉规范审核角色外貌、服装、环境、色彩与原创性风险。"
            "不要臆测图片中没有的信息；不能确认时选择 review。",
            "请审核这支镜头，并只返回 JSON："
            '{"verdict":"pass|review|fail","character_consistency":0,"scene_consistency":0,'
            '"copyright_risk":"low|medium|high","review_note":"简短中文结论"}。\n'
            f"镜头 {shot.number}：{shot.image_description}；动作：{shot.action}。\n"
            f"角色规范：{visual_bible.get('角色卡', '未提供')}\n"
            f"场景规范：{visual_bible.get('场景卡', '未提供')}\n"
            f"风格规范：{visual_bible.get('风格卡', '未提供')}\n"
            f"{reference_note}",
            images,
        )

    def _write_visual_review(self, project_id: str, shot_number: int, review: dict[str, Any]) -> None:
        review_path = self.settings.outputs_dir / project_id / "quality" / f"shot-{shot_number:02d}" / "review.json"
        review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _score(value: Any) -> int:
        try:
            return max(0, min(100, int(float(value))))
        except (TypeError, ValueError):
            return 0

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
