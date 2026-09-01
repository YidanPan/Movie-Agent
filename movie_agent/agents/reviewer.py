"""Reviewer agent: central place for later visual, audio, and compliance checks."""

from movie_agent.models import Shot


class ReviewerAgent:
    def review_mock(self, shot: Shot) -> str:
        shot.status = "approved_mock"
        return f"质检 Agent：镜头 {shot.number} 通过 mock 一致性与合规检查。"

    def review_generated(self, shot: Shot) -> str:
        if shot.status != "generated_comfyui":
            raise RuntimeError(f"镜头 {shot.number} 尚未生成完成，不能进入质检。")
        shot.status = "approved_comfyui"
        return f"质检 Agent：镜头 {shot.number} 已通过生成完整性检查，待人工画面复核。"
