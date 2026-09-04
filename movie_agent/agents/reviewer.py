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
        return f"Quality Agent: Shot {shot.number} passed mock consistency and compliance checks."

    def review_generated(
        self,
        shot: Shot,
        *,
        project_id: str | None = None,
        visual_bible: dict[str, str] | None = None,
    ) -> str:
        if shot.status != "generated_comfyui":
            raise RuntimeError(f"Shot {shot.number} has not been generated yet; cannot enter quality review.")
        video_path = Path(shot.output_placeholder)
        duration = self._video_duration(video_path)
        # Review the native media against the length requested from the video
        # model.  Editorial timing may intentionally trim, extend, hold, or
        # slow the shot later, so ``duration_seconds`` is not the right QC
        # expectation once a timeline edit has been made.
        expected_duration = float(shot.source_duration_seconds or shot.duration_seconds)
        tolerance = max(1.5, expected_duration * 0.25)
        if abs(duration - expected_duration) > tolerance:
            raise RuntimeError(
                f"Shot {shot.number} duration anomaly: native target {expected_duration:g}s, actual {duration:.2f}s."
            )
        if project_id is None:
            project_id = "ad-hoc-review"
        frames = self._extract_keyframes(project_id, shot, video_path, duration)
        if self.vision_llm is None:
            shot.qc_flags = []
            shot.status = "approved_comfyui"
            return (
                f"Quality Agent: Shot {shot.number} integrity passed ({duration:.2f}s), "
                f"{len(frames)} keyframes archived; no vision model configured; manual character/scene consistency review pending."
            )

        review = self._review_visual_consistency(project_id, shot, visual_bible or {}, frames)
        self._write_visual_review(project_id, shot.number, review)
        verdict = str(review.get("verdict", "")).strip().lower()
        character_score = self._score(review.get("character_consistency"))
        scene_score = self._score(review.get("scene_consistency"))
        drift_flags = [
            str(flag).strip().upper()
            for flag in (review.get("drift_flags") or [])
            if str(flag).strip().upper() in {"STYLE_DRIFT", "CHARACTER_DRIFT", "SCENE_DRIFT"}
        ]
        shot.qc_flags = drift_flags
        copyright_risk = str(review.get("copyright_risk", "")).strip().lower()
        if (
            verdict == "fail"
            or verdict == "review"
            or character_score < 70
            or scene_score < 70
            or copyright_risk == "high"
            or len(drift_flags) >= 2
        ):
            shot.status = "qc_failed_continuity"
            flag_text = ", ".join(drift_flags) if drift_flags else "none"
            raise RuntimeError(
                f"Shot {shot.number} visual quality check failed: character consistency {character_score}/100, "
                f"scene consistency {scene_score}/100, copyright risk {copyright_risk or 'unknown'}, flags {flag_text}."
            )
        self._reference_frames.setdefault(project_id, frames[len(frames) // 2])
        shot.status = "approved_comfyui"
        review_note = str(review.get("review_note", "Visual review completed.")).strip()
        return (
            f"Quality Agent: Shot {shot.number} integrity and visual review passed ({duration:.2f}s, "
            f"character {character_score}/100, scene {scene_score}/100). {review_note}"
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
                raise RuntimeError(f"Shot {shot.number} keyframe extraction failed: {completed.stderr[-300:]}")
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
        reference_note = "The first image is a previously approved character/scene reference frame; subsequent images are keyframes from the current shot." if reference else "All images are keyframes from the current shot."
        cinematography_lock = visual_bible.get("cinematography_lock", "")
        character_lock = visual_bible.get("character_lock", "")
        scene_lock = visual_bible.get("scene_lock", "")
        return self.vision_llm.complete_vision_json(
            "You are a film post-production visual quality inspector. Review character appearance, costume, environment, colour, lighting, camera style, and originality risk based only on the provided frames and visual specifications. "
            "Do not speculate about information not visible in the images; choose 'review' when uncertain. "
            "Check for STYLE_DRIFT (color/lighting/camera deviates from spec), CHARACTER_DRIFT (appearance changed), SCENE_DRIFT (environment inconsistent).",
            "Review this shot and return only JSON: "
            '{"verdict":"pass|review|fail","character_consistency":0,"scene_consistency":0,'
            '"camera_style_consistency":0,"color_consistency":0,"lighting_consistency":0,'
            '"copyright_risk":"low|medium|high","review_note":"Brief English conclusion",'
            '"drift_flags":["STYLE_DRIFT","CHARACTER_DRIFT","SCENE_DRIFT"] or []}.\n'
            f"Shot {shot.number}: {shot.image_description}; action: {shot.action}.\n"
            f"Character spec: {visual_bible.get('character_card', 'not provided')}\n"
            f"Character lock: {character_lock or 'not provided'}\n"
            f"Scene spec: {visual_bible.get('scene_card', 'not provided')}\n"
            f"Scene lock: {scene_lock or 'not provided'}\n"
            f"Style spec: {visual_bible.get('style_card', 'not provided')}\n"
            f"Cinematography lock: {cinematography_lock or 'not provided'}\n"
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
            raise RuntimeError("Quality review cannot find shot MP4 file.")
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
            raise RuntimeError(f"ffprobe cannot read shot file: {completed.stderr[-300:]}")
        try:
            payload = json.loads(completed.stdout)
            duration = float(payload["format"]["duration"])
            streams = payload.get("streams", [])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("ffprobe returned unparseable media info.") from error
        if duration <= 0 or not any(stream.get("codec_type") == "video" for stream in streams):
            raise RuntimeError("Shot file missing valid video stream or duration.")
        return duration
