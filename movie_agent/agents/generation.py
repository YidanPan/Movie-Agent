"""Generation agent. The current implementation is a ComfyUI-ready mock."""

from movie_agent.models import Shot


class GenerationAgent:
    def generate_mock(self, shot: Shot) -> str:
        shot.status = "generating_mock"
        shot.attempts += 1
        return f"生成 Agent：镜头 {shot.number} 已进入 mock 生成队列。"
