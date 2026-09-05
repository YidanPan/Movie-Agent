import unittest

from movie_agent.services.media_pipeline import (
    combine_video_filters,
    delivery_video_args,
    mezzanine_video_args,
    preview_video_args,
)


class MediaPipelinePolicyTests(unittest.TestCase):
    def test_mezzanine_prefers_prores_422_lt_and_pcm(self) -> None:
        args = mezzanine_video_args()
        self.assertEqual(args[args.index("-c:v") + 1], "prores_ks")
        self.assertEqual(args[args.index("-profile:v") + 1], "1")
        self.assertEqual(args[args.index("-c:a") + 1], "pcm_s16le")
        self.assertNotIn("-crf", args)

    def test_mezzanine_fallback_is_high_quality_and_not_crf_18(self) -> None:
        args = mezzanine_video_args(fallback=True)
        self.assertEqual(args[args.index("-c:v") + 1], "libx264")
        self.assertEqual(args[args.index("-crf") + 1], "13")

    def test_preview_tiers_keep_their_explicit_quality_budget(self) -> None:
        self.assertEqual(preview_video_args("working_proxy")[5], "30")
        self.assertEqual(preview_video_args("screening_preview")[5], "22")

    def test_delivery_is_the_only_default_h264_delivery_encode(self) -> None:
        args = delivery_video_args("mp4")
        self.assertIn("libx264", args)
        self.assertIn("18", args)
        self.assertNotIn("prores_ks", args)

    def test_filter_graph_is_combined_once(self) -> None:
        self.assertEqual(combine_video_filters("scale=1920:1080", "setpts=2*PTS", "crop=1920:1080"), "scale=1920:1080,setpts=2*PTS,crop=1920:1080")
        self.assertIsNone(combine_video_filters(None, ""))


if __name__ == "__main__":
    unittest.main()
