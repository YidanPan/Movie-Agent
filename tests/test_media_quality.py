from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from movie_agent.models import MovieProject
from movie_agent.services.media_quality import asset_record, best_master_path, quality_label, quality_snapshot


class MediaQualityTests(unittest.TestCase):
    def test_quality_labels_never_call_low_resolution_a_master(self) -> None:
        self.assertEqual(quality_label({"width": 608, "height": 352}), "LOW RES SOURCE")
        self.assertEqual(quality_label({"width": 1280, "height": 720}), "720P")
        self.assertEqual(quality_label({"width": 1920, "height": 1080}), "1080P")

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


if __name__ == "__main__":
    unittest.main()
