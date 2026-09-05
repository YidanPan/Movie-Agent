import unittest

from movie_agent.models import Shot
from movie_agent.services.quality import ContinuityQualityGate, PlanningQualityGate, SemanticCopyrightReviewer


def shot(*, prompt: str = "original near-future astronaut checks a silent weather console") -> Shot:
    return Shot(1, 6, "中景", "原创未来基地", "抬头查看屏幕", "低频设备声", "T2V", prompt, "shot.mp4")


class PlanningQualityGateTests(unittest.TestCase):
    def test_rejects_copyrighted_reference(self) -> None:
        with self.assertRaisesRegex(ValueError, "existing film/TV IP"):
            PlanningQualityGate().review(
                duration_seconds=36,
                script={"story": "模仿 Star Wars", "narration": "测试"},
                visual_bible={"character_card": "角色", "scene_card": "场景", "style_card": "风格"},
                storyboard=[shot() for _ in range(6)],
            )


class StubLLM:
    def __init__(self, result: dict) -> None:
        self.result = result

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        return self.result


class SemanticCopyrightReviewerTests(unittest.TestCase):
    def test_blocks_high_semantic_copyright_risk(self) -> None:
        reviewer = SemanticCopyrightReviewer(
            StubLLM(
                {
                    "risk_level": "high",
                    "reasons": ["角色与某现有系列核心设定近似"],
                    "rewrite_guidance": "替换角色设定",
                }
            )
        )

        with self.assertRaisesRegex(ValueError, "Copyright review failed"):
            reviewer.review(
                idea="一座漂浮城市等待风暴",
                script={"story": "原创故事", "narration": "原创旁白"},
                visual_bible={"角色卡": "原创角色", "场景卡": "海上城市", "风格卡": "低饱和"},
                storyboard=[shot()],
            )

    def test_marks_low_semantic_copyright_risk_as_passed(self) -> None:
        reviewer = SemanticCopyrightReviewer(
            StubLLM({"risk_level": "low", "reasons": [], "rewrite_guidance": ""})
        )

        report = reviewer.review(
            idea="一座漂浮城市等待风暴",
            script={"story": "原创故事", "narration": "原创旁白"},
            visual_bible={"角色卡": "原创角色", "场景卡": "海上城市", "风格卡": "低饱和"},
            storyboard=[shot()],
        )

        self.assertIn("No substantial similarity", report[0])


class ContinuityQualityGateTests(unittest.TestCase):
    def test_accepts_locked_story_beats_and_delta_shots(self) -> None:
        shots = []
        for index in range(6):
            item = shot()
            item.number = index + 1
            item.narrative_purpose = "establish" if index == 0 else "escalate"
            item.starting_state = "space is still"
            item.main_action = "protagonist investigates"
            item.ending_state = "anomaly grows"
            item.transition_hook = "carry the gaze forward"
            shots.append(item)
        report = ContinuityQualityGate().review(
            visual_bible={
                "character_lock": "same protagonist",
                "scene_lock": "same room",
                "cinematography_lock": "35mm",
            },
            storyboard=shots,
            continuity_lock={"status": "LOCKED"},
        )
        self.assertTrue(any("delta strategy" in note for note in report))

    def test_blocks_a_shot_without_transition_hook(self) -> None:
        item = shot()
        item.narrative_purpose = "establish"
        item.starting_state = "still"
        item.main_action = "look"
        item.ending_state = "unease"
        with self.assertRaisesRegex(ValueError, "Continuity QC failed"):
            ContinuityQualityGate().review(
                visual_bible={"character_lock": "x", "scene_lock": "y", "cinematography_lock": "z"},
                storyboard=[item],
                continuity_lock={"status": "LOCKED"},
            )
