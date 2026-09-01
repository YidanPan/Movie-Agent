import unittest

from movie_agent.models import Shot
from movie_agent.services.quality import PlanningQualityGate


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
