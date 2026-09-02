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


class GeneratedShotReviewerTests(unittest.TestCase):
    def test_approves_video_duration_within_tolerance(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = Settings("http://127.0.0.1:8188", 900, Path("workflows"), 9071, Path(temporary_directory), True)
            reviewer = ReviewerAgent(settings)
            shot = generated_shot()
            with patch.object(reviewer, "_video_duration", return_value=5.17):
                log = reviewer.review_generated(shot)

        self.assertEqual(shot.status, "approved_comfyui")
        self.assertIn("5.17s", log)

    def test_rejects_unexpected_duration(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = Settings("http://127.0.0.1:8188", 900, Path("workflows"), 9071, Path(temporary_directory), True)
            reviewer = ReviewerAgent(settings)
            shot = generated_shot()
            with patch.object(reviewer, "_video_duration", return_value=9.0):
                with self.assertRaisesRegex(RuntimeError, "时长异常"):
                    reviewer.review_generated(shot)

        self.assertEqual(shot.status, "generated_comfyui")
