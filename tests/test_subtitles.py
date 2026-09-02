from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from movie_agent.agents.editor import EditorAgent
from movie_agent.config import Settings
from movie_agent.models import MovieProject, Shot
from movie_agent.services.subtitles import ensure_dialogue_assets, render_srt, render_vtt


class SubtitleAssetTests(unittest.TestCase):
    def test_writer_assets_are_timed_and_exportable(self) -> None:
        script = ensure_dialogue_assets(
            {"story": "一个原创故事。", "narration": "灯亮了。门开了。"},
            duration_seconds=48,
            shot_count=6,
        )
        self.assertEqual(len(script["dialogue_book"]), 6)
        self.assertEqual(script["dialogue_book"][0]["start_seconds"], 0.0)
        self.assertEqual(script["dialogue_book"][-1]["end_seconds"], 48.0)
        self.assertIn("00:00:00,000 --> 00:00:08,000", render_srt(script["subtitle_track"]))
        self.assertTrue(render_vtt(script["subtitle_track"]).startswith("WEBVTT"))

    def test_old_project_is_migrated_without_losing_script(self) -> None:
        data = {
            "project_id": "film-1234abcd",
            "idea": "一名守夜人发现空城每天都在等他下班。",
            "duration_seconds": 48,
            "visual_style": "写实近未来",
            "status": "planned_mock",
            "brief": {},
            "script": {"story": "故事", "narration": "旁白"},
            "visual_bible": {},
            "storyboard": [
                {
                    "number": index,
                    "duration_seconds": 8,
                    "framing": "中景",
                    "image_description": "原创画面",
                    "action": "动作",
                    "sound_design": "声音",
                    "generation_mode": "T2V",
                    "prompt": "an original cinematic prompt",
                    "output_placeholder": "shot.mp4",
                }
                for index in range(1, 7)
            ],
        }
        project = MovieProject.from_dict(data)
        self.assertEqual(len(project.script["subtitle_track"]), 6)
        self.assertFalse(project.script["dialogue_locked"])
        self.assertIsNone(project.rough_cut_placeholder)

    def test_mock_editor_requires_lock_and_writes_sidecars(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(
                "http://127.0.0.1:8188",
                900,
                Path("workflows"),
                9071,
                root / "projects",
                True,
                outputs_dir=root / "outputs",
            )
            shots = [
                Shot(index, 8, "中景", "原创画面", "动作", "声音", "T2V", "original cinematic prompt", "shot.mp4", "approved_mock")
                for index in range(1, 7)
            ]
            project = MovieProject(
                "film-1234abcd",
                "一名守夜人发现空城每天都在等他下班。",
                48,
                "写实近未来",
                "ready_for_ai_edit",
                {},
                ensure_dialogue_assets({"story": "故事", "narration": "旁白"}, duration_seconds=48, shot_count=6),
                {},
                shots,
            )
            editor = EditorAgent(settings)
            with self.assertRaisesRegex(RuntimeError, "锁定台词本"):
                editor.create_rough_cut(project)
            project.script["dialogue_locked"] = True
            editor.create_rough_cut(project)
            self.assertEqual(project.edit_plan["status"], "rough_cut")
            self.assertTrue((root / "outputs" / project.project_id / "subtitles.srt").is_file())


if __name__ == "__main__":
    unittest.main()
