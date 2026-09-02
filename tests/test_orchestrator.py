from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator


class MovieOrchestratorTests(unittest.TestCase):
    def test_creates_a_structured_project(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(
                "http://127.0.0.1:8188", 900, Path("workflows"), 9071, root, True,
                outputs_dir=root / "outputs",
            )
            project = MovieOrchestrator(settings).create_project(
                "一名守夜人发现空城每天都在等他下班。", 48, "写实近未来"
            )

            self.assertEqual(project.status, "ready_for_ai_edit")
            self.assertGreaterEqual(len(project.storyboard), 6)
            self.assertLessEqual(len(project.storyboard), 10)
            self.assertEqual(sum(shot.duration_seconds for shot in project.storyboard), 48)
            self.assertTrue((root / project.project_id / "project.json").exists())
            self.assertEqual(MovieOrchestrator(settings).store.list_project_ids(), [project.project_id])
            self.assertIsNone(project.final_output_placeholder)
            self.assertIsNone(project.rough_cut_placeholder)
            self.assertTrue(all(shot.status == "approved_mock" for shot in project.storyboard))
            self.assertGreaterEqual(len(project.quality_report), 4)
            self.assertTrue(any("版权审核" in note for note in project.quality_report))
            self.assertEqual(len(project.script["dialogue_book"]), len(project.storyboard))
            self.assertEqual(len(project.script["subtitle_track"]), len(project.storyboard))
            self.assertFalse(project.script["dialogue_locked"])
            exported = MovieOrchestrator(settings).store.export(project.project_id)
            self.assertEqual(len(exported), 2)
            self.assertIn("最终视频提示词", exported[1].read_text(encoding="utf-8"))

            locked = MovieOrchestrator(settings).lock_dialogue(project.project_id)
            self.assertTrue(locked.script["dialogue_locked"])
            rough = MovieOrchestrator(settings).create_rough_cut(project.project_id)
            self.assertEqual(rough.status, "rough_cut_ready")
            self.assertIsNotNone(rough.rough_cut_placeholder)
            self.assertIsNone(rough.final_output_placeholder)
            approved = MovieOrchestrator(settings).approve_edit(project.project_id, "soft")
            self.assertEqual(approved.status, "completed_mock")
            self.assertEqual(approved.subtitle_mode, "soft")
            self.assertEqual(approved.final_output_placeholder, f"outputs/{project.project_id}/final-cut.mp4")
            self.assertTrue((root / "outputs" / project.project_id / "subtitles.srt").exists())

            unlocked = MovieOrchestrator(settings).unlock_dialogue(project.project_id)
            self.assertFalse(unlocked.script["dialogue_locked"])
            self.assertEqual(unlocked.status, "ready_for_ai_edit")
            self.assertIsNone(unlocked.final_output_placeholder)

            revised = MovieOrchestrator(settings).regenerate_shot(project.project_id, 1)
            self.assertEqual(revised.storyboard[0].status, "replanned")
            self.assertEqual(revised.storyboard[0].attempts, 2)

    def test_rejects_short_ideas(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = Settings(
                "http://127.0.0.1:8188", 900, Path("workflows"), 9071, Path(temporary_directory), True
            )
            with self.assertRaisesRegex(ValueError, "至少 10"):
                MovieOrchestrator(settings).create_project("太短", 48, "写实近未来")

    def test_real_render_requires_comfyui_mode(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = Settings(
                "http://127.0.0.1:8188", 900, Path("workflows"), 9071, Path(temporary_directory), True
            )
            project = MovieOrchestrator(settings).create_project(
                "一名守夜人发现空城每天都在等他下班。", 48, "写实近未来"
            )
            with self.assertRaisesRegex(ValueError, "mock 模式"):
                MovieOrchestrator(settings).render_project(project.project_id)
            with self.assertRaisesRegex(ValueError, "mock 模式"):
                MovieOrchestrator(settings).render_shot(project.project_id, 1)
