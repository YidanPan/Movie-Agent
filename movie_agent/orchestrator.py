"""Coordinates the MVP planning stages and stores their output."""

from __future__ import annotations

from uuid import uuid4

from movie_agent.agents.director import DirectorAgent
from movie_agent.agents.editor import EditorAgent
from movie_agent.agents.generation import GenerationAgent
from movie_agent.agents.reviewer import ReviewerAgent
from movie_agent.agents.storyboard import StoryboardAgent
from movie_agent.agents.visual_bible import VisualBibleAgent
from movie_agent.agents.writer import WriterAgent
from movie_agent.config import Settings
from movie_agent.models import MovieProject
from movie_agent.services.mock_creator import build_storyboard
from movie_agent.storage.project_store import ProjectStore


class MovieOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = ProjectStore(settings.projects_dir)
        self.director = DirectorAgent()
        self.writer = WriterAgent()
        self.storyboard_agent = StoryboardAgent()
        self.visual_bible_agent = VisualBibleAgent()
        self.generation_agent = GenerationAgent()
        self.reviewer = ReviewerAgent()
        self.editor = EditorAgent()

    def create_project(self, idea: str, duration: int, visual_style: str) -> MovieProject:
        cleaned_idea = idea.strip()
        if len(cleaned_idea) < 10:
            raise ValueError("请提供至少 10 个字的原创科幻创意。")
        if not 30 <= duration <= 80:
            raise ValueError("当前 MVP 支持 30–80 秒的目标时长。")

        project_id = f"film-{uuid4().hex[:8]}"
        logs = [
            "导演 Agent：已理解创意并确定单人物、单空间、单事件的创作边界。",
            "编剧 Agent：已生成短剧本、旁白与情绪节奏。",
            "分镜 Agent：已拆分独立镜头，并为后续 ComfyUI 工作流标记生成方式。",
            "视觉设定 Agent：已锁定角色、场景和风格规范。",
            "生成调度 Agent：当前为 mock 模式，尚未提交真实 ComfyUI 任务。",
            "项目归档：已保存项目 JSON；后续将接入质检、重试与 FFmpeg 剪辑。",
        ]
        project = MovieProject(
            project_id=project_id,
            idea=cleaned_idea,
            duration_seconds=duration,
            visual_style=visual_style,
            status="planned_mock",
            brief=self.director.plan(cleaned_idea, duration, visual_style),
            script=self.writer.write(cleaned_idea),
            visual_bible=self.visual_bible_agent.create(visual_style),
            storyboard=self.storyboard_agent.create(cleaned_idea, duration, visual_style, project_id),
            logs=logs,
        )
        self.store.save(project)
        return self.run_mock_production(project_id)

    def run_mock_production(self, project_id: str) -> MovieProject:
        """Simulate the state flow that will later call ComfyUI and FFmpeg."""
        project = self.store.load(project_id)
        project.status = "generating_mock"
        project.logs.append("生成 Agent：开始模拟提交镜头任务队列。")
        for shot in project.storyboard:
            project.logs.append(self.generation_agent.generate_mock(shot))
            project.logs.append(self.reviewer.review_mock(shot))

        project.status = "completed_mock"
        project.logs.append(self.editor.assemble_mock(project))
        project.logs.append(f"项目完成：最终成片预留路径为 {project.final_output_placeholder}。")
        self.store.save(project)
        return project
