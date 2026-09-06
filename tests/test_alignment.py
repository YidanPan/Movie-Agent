import unittest

from movie_agent.services.alignment import WordBoundary, word_level_cues


class WordBoundaryAlignmentTests(unittest.TestCase):
    def test_word_cues_split_at_shot_boundary_between_words(self) -> None:
        cues = word_level_cues(
            {"subtitle_track": [{"shot": 1, "text": "The signal arrives now"}]},
            [
                WordBoundary("The", 0.0, 0.3),
                WordBoundary("signal", 0.4, 0.8),
                WordBoundary("arrives", 1.1, 1.5),
                WordBoundary("now", 1.6, 1.9),
            ],
            shot_transitions=[1.0],
        )
        self.assertEqual([cue["text"] for cue in cues], ["The signal", "arrives now"])
        self.assertEqual(cues[0]["end_seconds"], 0.8)
        self.assertEqual(cues[1]["start_seconds"], 1.1)


if __name__ == "__main__":
    unittest.main()
