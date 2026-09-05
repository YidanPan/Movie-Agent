from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator


class MovieOrchestratorTests(unittest.TestCase):
    def test_creates_a_structured_project(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings("http://127.0.0.1:8188", 9071, root, True)
            project = MovieOrchestrator(settings).create_project(
                "一名守夜人发现空城每天都在等他下班。", 48, "写实近未来"
            )

            self.assertEqual(project.status, "planned_mock")
            self.assertGreaterEqual(len(project.storyboard), 6)
            self.assertLessEqual(len(project.storyboard), 10)
            self.assertEqual(sum(shot.duration_seconds for shot in project.storyboard), 48)
            self.assertTrue((root / project.project_id / "project.json").exists())

    def test_rejects_short_ideas(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = Settings("http://127.0.0.1:8188", 9071, Path(temporary_directory), True)
            with self.assertRaisesRegex(ValueError, "至少 10"):
                MovieOrchestrator(settings).create_project("太短", 48, "写实近未来")
