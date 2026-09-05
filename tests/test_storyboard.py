import unittest

from movie_agent.agents.storyboard import _fit_durations
from movie_agent.agents.writer import _as_text


class FitDurationsTests(unittest.TestCase):
    def test_keeps_exact_totals_untouched(self) -> None:
        durations = [6, 6, 6, 6, 6, 6, 6, 6]
        self.assertEqual(_fit_durations(durations, 48), durations)

    def test_redistributes_small_drift_within_bounds(self) -> None:
        # 8 镜原始 45 秒（含一个超界的 10 被夹到 8），需补 5 秒。
        fitted = _fit_durations([10, 5, 5, 5, 5, 5, 5, 5], 48)
        self.assertIsNotNone(fitted)
        self.assertEqual(sum(fitted), 48)
        self.assertTrue(all(4 <= duration <= 8 for duration in fitted))

    def test_pulls_back_overshoot(self) -> None:
        fitted = _fit_durations([8, 8, 8, 8, 8, 8, 8, 8], 48)  # 64 -> 48
        self.assertEqual(sum(fitted), 48)
        self.assertTrue(all(4 <= duration <= 8 for duration in fitted))

    def test_returns_none_when_shot_count_cannot_cover_target(self) -> None:
        self.assertIsNone(_fit_durations([8, 8, 8, 8, 8, 8], 80))


class WriterTextTests(unittest.TestCase):
    def test_flattens_structured_story_into_prose(self) -> None:
        structured = [
            {"duration": 6, "visual": "俯拍：探测舱缓缓停稳。"},
            {"duration": 6, "visual": "舱门开启，白光涌入。"},
        ]
        text = _as_text(structured)
        self.assertNotIn("{", text)
        self.assertIn("俯拍：探测舱缓缓停稳。", text)
        self.assertIn("舱门开启，白光涌入。", text)

    def test_plain_strings_pass_through(self) -> None:
        self.assertEqual(_as_text("一段安静的旁白。"), "一段安静的旁白。")


if __name__ == "__main__":
    unittest.main()
