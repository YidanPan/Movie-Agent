from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from movie_agent.models import MovieProject
from movie_agent.agents.editor import EditorAgent
from movie_agent.config import Settings
from movie_agent.services.media_quality import (
    asset_record,
    best_master_path,
    export_dimensions,
    quality_label,
    quality_snapshot,
)


class MediaQualityTests(unittest.TestCase):
    def test_quality_labels_never_call_low_resolution_a_master(self) -> None:
        self.assertEqual(quality_label({"width": 608, "height": 352}), "LOW RES SOURCE")
        self.assertEqual(quality_label({"width": 1280, "height": 720}), "720P")
        self.assertEqual(quality_label({"width": 1920, "height": 1080}), "1080P")
        self.assertEqual(quality_label({"width": 1080, "height": 1920}), "1080P")

    def test_asset_record_is_explicit_about_tier_and_missing_media(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "missing.mp4"
            record = asset_record(path, tier="working_proxy")
            self.assertEqual(record["tier"], "working_proxy")
            self.assertFalse(record["exists"])
            self.assertEqual(record["quality"], "QUALITY UNKNOWN")

    def test_master_resolution_is_preferred_over_preview(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            master = root / "master.mp4"
            preview = root / "preview.mp4"
            master.touch()
            preview.touch()
            project = MovieProject(
                "film-quality", "原创科幻创意", 48, "胶片科幻", "completed_mock", {}, {}, {}, [],
                video_assets={
                    "screening_preview": {"path": str(preview), "tier": "screening_preview"},
                    "final_master": {"path": str(master), "tier": "final_master"},
                },
            )
            self.assertEqual(best_master_path(project), master)
            snapshot = quality_snapshot(project)
            self.assertEqual(snapshot["final_master"]["tier"], "final_master")
            self.assertFalse(snapshot["source_low_res"])

    def test_export_dimensions_keep_portrait_and_square_native(self) -> None:
        self.assertEqual(export_dimensions("1080p", "16:9"), (1920, 1080))
        self.assertEqual(export_dimensions("1080p", "9:16"), (1080, 1920))
        self.assertEqual(export_dimensions("1080p", "1:1"), (1080, 1080))
        self.assertEqual(export_dimensions("720p", "9:16"), (720, 1280))

    def test_editor_cut_contract_does_not_claim_unrendered_crossfade(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            project = MovieProject(
                "film-cut", "原创科幻创意", 8, "胶片科幻", "ready_for_ai_edit", {}, {}, {}, [],
            )
            # A project with no media still gets the honest planning contract.
            editor = EditorAgent(Settings("http://127.0.0.1:8188", 900, root / "workflows", 9071, root / "projects", True, outputs_dir=root / "outputs"))
            plan = editor._rough_cut_plan(project)
            self.assertEqual(plan["transition_semantics"]["type"], "cut")
            self.assertEqual(plan["media_encoding"]["edit_master"], "prores_422_lt")
            self.assertEqual(plan["media_encoding"]["final_delivery"], "one_final_encode_crf18")


if __name__ == "__main__":
    unittest.main()
