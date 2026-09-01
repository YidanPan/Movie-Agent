"""Reviewer agent: central place for later visual, audio, and compliance checks."""

from movie_agent.models import Shot


class ReviewerAgent:
    def review_mock(self, shot: Shot) -> str:
        shot.status = "approved_mock"
        return f"质检 Agent：镜头 {shot.number} 通过 mock 一致性与合规检查。"
