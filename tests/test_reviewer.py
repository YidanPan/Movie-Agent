from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from movie_agent.agents.reviewer import ReviewerAgent
from movie_agent.config import Settings
from movie_agent.models import Shot


def generated_shot() -> Shot:
    shot = Shot(1, 5, "中景", "原创基地", "角色转身", "低频环境音", "T2V", "original prompt", "shot.mp4")
    shot.status = "generated_comfyui"
    return shot


class StubVisionLLM:
    def complete_vision_json(self, system_prompt: str, user_prompt: str, image_paths: list[Path]) -> dict:
        return {
            "verdict": "pass",
            "character_consistency": 92,
            "scene_consistency": 88,
            "copyright_risk": "low",
            "review_note": "Character and scene are consistent with specifications.",
        }


class GeneratedShotReviewerTests(unittest.TestCase):
    def test_approves_video_duration_within_tolerance(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = Settings("http://127.0.0.1:8188", 900, Path("workflows"), 9071, Path(temporary_directory), True)
            reviewer = ReviewerAgent(settings)
            shot = generated_shot()
            with patch.object(reviewer, "_video_duration", return_value=5.17), patch.object(
                reviewer, "_extract_keyframes", return_value=[Path(temporary_directory) / "frame.jpg"]
            ):
                log = reviewer.review_generated(shot)

        self.assertEqual(shot.status, "approved_comfyui")
        self.assertIn("5.17s", log)

    def test_rejects_unexpected_duration(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = Settings("http://127.0.0.1:8188", 900, Path("workflows"), 9071, Path(temporary_directory), True)
            reviewer = ReviewerAgent(settings)
            shot = generated_shot()
            with patch.object(reviewer, "_video_duration", return_value=9.0):
                with self.assertRaisesRegex(RuntimeError, "duration anomaly"):
                    reviewer.review_generated(shot)

        self.assertEqual(shot.status, "generated_comfyui")

    def test_uses_evenly_spaced_interior_keyframes(self) -> None:
        self.assertEqual(ReviewerAgent._keyframe_timestamps(6.0, 3), [1.5, 3.0, 4.5])

    def test_records_visual_review_when_vision_model_is_available(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            settings = Settings("http://127.0.0.1:8188", 900, Path("workflows"), 9071, output_dir, True, outputs_dir=output_dir)
            reviewer = ReviewerAgent(settings, vision_llm=StubVisionLLM())
            shot = generated_shot()
            quality_dir = output_dir / "film-test" / "quality" / "shot-01"
            quality_dir.mkdir(parents=True)
            frame = quality_dir / "frame.jpg"
            frame.touch()
            with patch.object(reviewer, "_video_duration", return_value=5.0), patch.object(
                reviewer, "_extract_keyframes", return_value=[frame]
            ):
                log = reviewer.review_generated(
                    shot,
                    project_id="film-test",
                    visual_bible={"character_card": "原创角色", "scene_card": "原创场景", "style_card": "原创风格"},
                )

            self.assertEqual(shot.status, "approved_comfyui")
            self.assertIn("character 92/100", log)
            self.assertTrue((quality_dir / "review.json").is_file())
