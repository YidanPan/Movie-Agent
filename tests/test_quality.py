import unittest

from movie_agent.models import Shot
from movie_agent.services.quality import PlanningQualityGate, SemanticCopyrightReviewer


def shot(*, prompt: str = "original near-future astronaut checks a silent weather console") -> Shot:
    return Shot(1, 6, "中景", "原创未来基地", "抬头查看屏幕", "低频设备声", "T2V", prompt, "shot.mp4")


class PlanningQualityGateTests(unittest.TestCase):
    def test_rejects_copyrighted_reference(self) -> None:
        with self.assertRaisesRegex(ValueError, "影视 IP"):
            PlanningQualityGate().review(
                duration_seconds=36,
                script={"story": "模仿 Star Wars", "narration": "测试"},
                visual_bible={"角色卡": "角色", "场景卡": "场景", "风格卡": "风格"},
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

        with self.assertRaisesRegex(ValueError, "语义版权审核未通过"):
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

        self.assertIn("未发现", report[0])
