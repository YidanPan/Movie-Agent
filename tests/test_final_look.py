from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.services.final_look import (
    final_look_filter,
    normalise_final_look,
    normalise_look_preset,
)


class FinalLookTests(unittest.TestCase):
    def _settings(self, root: Path) -> Settings:
        return Settings(
            "http://127.0.0.1:8188",
            900,
            Path("workflows"),
            9071,
            root,
            True,
            outputs_dir=root / "outputs",
        )

    def test_presets_and_effects_normalise_to_stable_contract(self) -> None:
        self.assertEqual(normalise_look_preset("胶片叙事"), "film_narrative")
        self.assertEqual(normalise_look_preset("cyber"), "cyber_night")
        look = normalise_final_look(
            {
                "preset": "film_narrative",
                "intensity": 2,
                "grain": 0.2,
                "vignette": 0.35,
                "highlight_soften": 0.4,
                "scope": "全片",
            }
        )
        self.assertEqual(look["scope"], "whole_film")
        self.assertEqual(look["intensity"], 1.0)
        self.assertEqual(look["grain"], 0.2)
        self.assertIn("eq=", final_look_filter(look))
        self.assertIn("noise=", final_look_filter(look))
        self.assertIn("vignette=", final_look_filter(look))
        self.assertIn("gblur=", final_look_filter(look))
        self.assertEqual(final_look_filter({"preset": "original"}), "null")

    def test_new_project_exposes_whole_film_final_look_defaults(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = MovieOrchestrator(self._settings(root)).create_project(
                "一名守夜人发现空城每天都在等他下班。", 48, "胶片科幻"
            )
            self.assertEqual(project.final_look["preset"], "original")
            self.assertEqual(project.final_look["scope"], "whole_film")
            self.assertFalse(project.final_look["applied"])
            saved = root / project.project_id / "project.json"
            self.assertIn('"final_look"', saved.read_text(encoding="utf-8"))
            markdown = MovieOrchestrator(self._settings(root)).store.export(project.project_id)[1]
            self.assertIn("最终润色 / Final Look", markdown.read_text(encoding="utf-8"))

    def test_apply_final_look_after_final_cut_saves_export_plan(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            orchestrator = MovieOrchestrator(self._settings(root))
            project = orchestrator.create_project(
                "一名守夜人发现空城每天都在等他下班。", 48, "胶片科幻"
            )
            orchestrator.lock_dialogue(project.project_id)
            orchestrator.create_rough_cut(project.project_id)
            completed = orchestrator.approve_edit(project.project_id)

            finished = orchestrator.set_final_look(
                completed.project_id,
                preset="film_narrative",
                intensity=0.8,
                grain=0.2,
                vignette=0.15,
                highlight_soften=0.1,
                apply=True,
            )
            self.assertEqual(finished.final_look["preset"], "film_narrative")
            self.assertEqual(finished.final_look["scope"], "whole_film")
            self.assertTrue(finished.final_look["applied"])
            self.assertIn("EXPORT FILTER READY", finished.final_look["status"])
            self.assertIsNone(finished.final_look["media_path"])
            self.assertTrue(any("最终润色" in entry for entry in finished.logs))

    def test_final_look_requires_a_completed_cut(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            orchestrator = MovieOrchestrator(self._settings(root))
            project = orchestrator.create_project(
                "一名守夜人发现空城每天都在等他下班。", 48, "胶片科幻"
            )
            with self.assertRaisesRegex(ValueError, "最终成片"):
                orchestrator.set_final_look(project.project_id, preset="cyber_night")


if __name__ == "__main__":
    unittest.main()
