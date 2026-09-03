from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.services.audio import normalise_music_mode


class AudioDesignTests(unittest.TestCase):
    def test_music_modes_normalise_to_stable_values(self) -> None:
        self.assertEqual(normalise_music_mode("AI 自动配乐"), "ai")
        self.assertEqual(normalise_music_mode("素材库音乐"), "library")
        self.assertEqual(normalise_music_mode("用户上传音乐"), "upload")
        self.assertEqual(normalise_music_mode("unknown"), "ai")

    def test_ducking_cues_follow_locked_subtitles(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(
                "http://127.0.0.1:8188", 900, Path("workflows"), 9071, root, True,
                outputs_dir=root / "outputs",
            )
            orchestrator = MovieOrchestrator(settings)
            project = orchestrator.create_project(
                "一名守夜人发现空城每天都在等他下班。", 48, "胶片科幻"
            )
            self.assertEqual(project.smart_ducking["status"], "LOCK REQUIRED")
            project = orchestrator.lock_dialogue(project.project_id)
            self.assertEqual(len(project.smart_ducking["voice_cues"]), len(project.storyboard))
            self.assertEqual(project.smart_ducking["status"], "ACTIVE")
            self.assertEqual(project.audio_tracks["voice"]["status"], "READY")
            self.assertLess(project.smart_ducking["amount_db"], 0)

    def test_switching_music_mode_does_not_reuse_uploaded_preview(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(
                "http://127.0.0.1:8188", 900, Path("workflows"), 9071, root, True,
                outputs_dir=root / "outputs",
            )
            orchestrator = MovieOrchestrator(settings)
            project = orchestrator.create_project(
                "一名守夜人发现空城每天都在等他下班。", 48, "胶片科幻"
            )
            project.audio_tracks["music"]["preview_url"] = "/audio/uploaded.wav"
            project.audio_tracks["music"]["media_path"] = str(root / "uploaded.wav")
            project.music_mode = "upload"
            project.music_asset_name = "uploaded.wav"
            orchestrator.store.save(project)
            switched = orchestrator.set_audio_design(project.project_id, music_mode="ai")
            self.assertEqual(switched.music_mode, "ai")
            self.assertEqual(switched.music_asset_name, "")
            self.assertIsNone(switched.audio_tracks["music"].get("preview_url"))
            self.assertNotIn("media_path", switched.audio_tracks["music"])

    def test_audio_changes_invalidate_stale_cut(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(
                "http://127.0.0.1:8188", 900, Path("workflows"), 9071, root, True,
                outputs_dir=root / "outputs",
            )
            orchestrator = MovieOrchestrator(settings)
            project = orchestrator.create_project(
                "一名守夜人发现空城每天都在等他下班。", 48, "胶片科幻"
            )
            orchestrator.lock_dialogue(project.project_id)
            rough = orchestrator.create_rough_cut(project.project_id)
            self.assertEqual(rough.status, "rough_cut_ready")
            changed = orchestrator.set_audio_design(project.project_id, smart_ducking=False)
            self.assertEqual(changed.status, "ready_for_ai_edit")
            self.assertIsNone(changed.rough_cut_placeholder)
            self.assertIsNone(changed.final_output_placeholder)
            self.assertEqual(changed.mix_state["status"], "DESIGN UPDATED · RE-CUT REQUIRED")

    def test_music_intensity_persists_and_updates_score_level(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(
                "http://127.0.0.1:8188", 900, Path("workflows"), 9071, root, True,
                outputs_dir=root / "outputs",
            )
            orchestrator = MovieOrchestrator(settings)
            project = orchestrator.create_project(
                "一名守夜人发现空城每天都在等他下班。", 48, "胶片科幻"
            )
            changed = orchestrator.set_audio_design(project.project_id, music_intensity=0.25)
            self.assertEqual(changed.music_intensity, 0.25)
            self.assertEqual(changed.music_brief["intensity_percent"], 25)
            self.assertEqual(changed.audio_tracks["music"]["volume_db"], -17.5)


if __name__ == "__main__":
    unittest.main()
