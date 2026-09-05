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
            self.assertTrue(any("Copyright review" in note for note in project.quality_report))
            self.assertEqual(len(project.script["dialogue_book"]), len(project.storyboard))
            self.assertEqual(len(project.script["subtitle_track"]), len(project.storyboard))
            self.assertFalse(project.script["dialogue_locked"])
            self.assertEqual(project.music_mode, "ai")
            self.assertIn("emotional_arc", project.music_brief)
            self.assertEqual(len(project.music_brief["emotional_arc"]), len(project.storyboard))
            self.assertEqual(set(project.audio_tracks), {"voice", "music", "sfx", "ambience"})
            self.assertTrue(project.smart_ducking["enabled"])
            self.assertEqual(project.mix_state["pipeline"], ["picture_cut", "voice", "music", "sfx", "subtitles", "mix", "final_encode"])
            self.assertEqual(project.film_language, "en")
            self.assertEqual(project.continuity_lock["status"], "LOCKED")
            self.assertTrue(all(shot.source_duration_seconds == shot.duration_seconds for shot in project.storyboard))
            self.assertTrue(all(shot.desired_duration == shot.duration_seconds for shot in project.storyboard))
            self.assertTrue(any("Continuity QC" in note for note in project.quality_report))
            exported = MovieOrchestrator(settings).store.export(project.project_id)
            self.assertEqual(len(exported), 2)
            self.assertIn("Final Video Prompts", exported[1].read_text(encoding="utf-8"))
            self.assertIn("Sound Department", exported[1].read_text(encoding="utf-8"))

            locked = MovieOrchestrator(settings).lock_dialogue(project.project_id)
            self.assertTrue(locked.script["dialogue_locked"])
            configured = MovieOrchestrator(settings).set_audio_design(
                project.project_id,
                music_mode="library",
                smart_ducking=False,
            )
            self.assertEqual(configured.music_mode, "library")
            self.assertFalse(configured.smart_ducking["enabled"])
            self.assertEqual(configured.audio_tracks["music"]["source"], "STUDIO LIBRARY / CURATED SCORE")
            refreshed = MovieOrchestrator(settings).regenerate_audio_track(project.project_id, "music")
            self.assertGreaterEqual(refreshed.audio_tracks["music"].get("revision", 1), 2)
            rough = MovieOrchestrator(settings).create_rough_cut(project.project_id)
            self.assertEqual(rough.status, "rough_cut_ready")
            self.assertIsNotNone(rough.rough_cut_placeholder)
            self.assertIsNone(rough.final_output_placeholder)
            self.assertTrue(all(value == "done" for value in rough.mix_state["stage_status"].values()))
            approved = MovieOrchestrator(settings).approve_edit(project.project_id, "soft")
            self.assertEqual(approved.status, "completed_mock")
            self.assertEqual(approved.subtitle_mode, "soft")
            self.assertEqual(approved.final_output_placeholder, f"outputs/{project.project_id}/final-cut.mp4")
            self.assertTrue((root / "outputs" / project.project_id / "subtitles.srt").exists())

            re_cut = MovieOrchestrator(settings).create_rough_cut(project.project_id)
            self.assertEqual(re_cut.status, "rough_cut_ready")
            self.assertIsNone(re_cut.final_output_placeholder)

            unlocked = MovieOrchestrator(settings).unlock_dialogue(project.project_id)
            self.assertFalse(unlocked.script["dialogue_locked"])
            self.assertEqual(unlocked.status, "ready_for_ai_edit")
            self.assertIsNone(unlocked.final_output_placeholder)

            revised = MovieOrchestrator(settings).regenerate_shot(project.project_id, 1)
            self.assertEqual(revised.storyboard[0].status, "replanned")
            self.assertEqual(revised.storyboard[0].attempts, 2)

    def test_editorial_timing_is_separate_from_native_generation_length(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(
                "http://127.0.0.1:8188", 900, Path("workflows"), 9071, root, True,
                outputs_dir=root / "outputs",
            )
            orchestrator = MovieOrchestrator(settings)
            project = orchestrator.create_project("一名守夜人发现空城每天都在等他下班。", 48, "胶片科幻")
            source = project.storyboard[0].source_duration_seconds
            updated = orchestrator.update_shot_timing(
                project.project_id, 1, desired_duration=9, timing_mode="hold_last_frame"
            )
            shot = updated.storyboard[0]
            self.assertEqual(shot.duration_seconds, 9)
            self.assertEqual(shot.desired_duration, 9)
            self.assertEqual(shot.source_duration_seconds, source)
            self.assertEqual(shot.timing_mode, "hold_last_frame")
            self.assertEqual(updated.duration_seconds, sum(item.duration_seconds for item in updated.storyboard))
            self.assertEqual(len(updated.script["subtitle_track"]), len(updated.storyboard))
            self.assertEqual(updated.status, "ready_for_ai_edit")

    def test_rejects_short_ideas(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = Settings(
                "http://127.0.0.1:8188", 900, Path("workflows"), 9071, Path(temporary_directory), True
            )
            with self.assertRaisesRegex(ValueError, "at least 10"):
                MovieOrchestrator(settings).create_project("太短", 48, "写实近未来")

    def test_real_render_requires_comfyui_mode(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            settings = Settings(
                "http://127.0.0.1:8188", 900, Path("workflows"), 9071, Path(temporary_directory), True
            )
            project = MovieOrchestrator(settings).create_project(
                "一名守夜人发现空城每天都在等他下班。", 48, "写实近未来"
            )
            with self.assertRaisesRegex(ValueError, "Current mode is mock"):
                MovieOrchestrator(settings).render_project(project.project_id)
            with self.assertRaisesRegex(ValueError, "Current mode is mock"):
                MovieOrchestrator(settings).render_shot(project.project_id, 1)
