import unittest

from movie_agent.models import Shot
from movie_agent.services.storyboard_quality import (
    StoryboardRelevanceGate,
    previous_ending_connects_to_next_starting_state,
)


def shot(number: int, **changes: object) -> Shot:
    value = Shot(
        number,
        6,
        "medium shot",
        "The protagonist watches the amber console.",
        "The protagonist reaches toward the console.",
        "Room tone",
        "T2V",
        "Shot delta",
        f"shot-{number}.mp4",
        story_function="REVELATION",
        information_gain=0.8,
        emotional_shift="curiosity",
        visual_motif="amber console",
        ending_state="the console opens",
        starting_state="the console is closed",
    )
    for key, value_override in changes.items():
        setattr(value, key, value_override)
    return value


class StoryboardQualityTests(unittest.TestCase):
    def test_relevance_detects_filler_shot(self) -> None:
        result = StoryboardRelevanceGate().evaluate(
            shot(1, story_function="", main_action="", image_description="", visual_motif="", information_gain=0)
        )
        self.assertIn("LOW_RELEVANCE_SHOT", result["flags"])

    def test_relevance_allows_necessary_atmosphere(self) -> None:
        result = StoryboardRelevanceGate().evaluate(
            shot(1, story_function="ATMOSPHERE", main_action="", image_description="", visual_motif="", information_gain=0)
        )
        self.assertNotIn("LOW_RELEVANCE_SHOT", result["flags"])
        self.assertTrue(result["atmosphere_exception"])

    def test_redundant_information_is_explainable(self) -> None:
        previous = shot(1)
        result = StoryboardRelevanceGate().evaluate(shot(2), previous_shot=previous)
        self.assertIn("REDUNDANT_SHOT", result["flags"])
        self.assertIn("REPEATED_INFORMATION", result["flags"])

    def test_overloaded_action_is_flagged(self) -> None:
        result = StoryboardRelevanceGate().evaluate(
            shot(1, shot_complexity="HIGH", action="opens, turns, runs, speaks and falls, then looks back")
        )
        self.assertIn("SHOT_TOO_COMPLEX", result["flags"])

    def test_previous_ending_connects_to_next_starting_state(self) -> None:
        self.assertTrue(previous_ending_connects_to_next_starting_state(shot(1), shot(2)))
        self.assertFalse(
            previous_ending_connects_to_next_starting_state(
                shot(1, ending_state="the door is sealed"),
                shot(2, starting_state="the river is empty"),
            )
        )


if __name__ == "__main__":
    unittest.main()
