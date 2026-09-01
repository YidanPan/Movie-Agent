"""Storyboard agent: creates renderable, independently generated shots."""

from movie_agent.models import Shot
from movie_agent.services.mock_creator import build_storyboard


class StoryboardAgent:
    def create(self, idea: str, duration_seconds: int, visual_style: str, project_id: str) -> list[Shot]:
        return build_storyboard(idea, duration_seconds, visual_style, project_id)
