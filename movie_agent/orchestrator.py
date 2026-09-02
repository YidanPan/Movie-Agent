"""Coordinates the MVP planning stages and stores their output."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
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
from movie_agent.storage.project_store import ProjectStore
from movie_agent.services.llm import build_creative_llm
from movie_agent.services.quality import PlanningQualityGate


class MovieOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = ProjectStore(settings.projects_dir)
        creative_llm = build_creative_llm(settings)
        self.using_creative_llm = creative_llm is not None
        self.director = DirectorAgent(creative_llm)
        self.writer = WriterAgent(creative_llm)
        self.storyboard_agent = StoryboardAgent(creative_llm)
        self.visual_bible_agent = VisualBibleAgent(creative_llm)
        self.generation_agent = GenerationAgent(settings)
        self.reviewer = ReviewerAgent(settings)
        self.editor = EditorAgent(settings)
        self.quality_gate = PlanningQualityGate()

    def create_project(
        self,
        idea: str,
        duration: int,
        visual_style: str,
        event_callback: Callable[[dict], None] | None = None,
    ) -> MovieProject:
        def emit(event: dict) -> None:
            if event_callback is not None:
                event_callback(event)

        cleaned_idea = idea.strip()
        if len(cleaned_idea) < 10:
            raise ValueError("请提供至少 10 个字的原创科幻创意。")
        if not 30 <= duration <= 80:
            raise ValueError("当前 MVP 支持 30–80 秒的目标时长。")

        project_id = f"film-{uuid4().hex[:8]}"
        emit(
            {
                "type": "project",
                "project_id": project_id,
                "text_mode": "modelscope" if self.using_creative_llm else "mock",
                "video_mode": self.settings.video_generation_mode,
            }
        )
        creative_source = "ModelScope 文本模型" if self.using_creative_llm else "mock 规则引擎"
        logs = [
            f"导演 Agent：已通过{creative_source}确定创作边界。",
            f"编剧 Agent：已通过{creative_source}生成短剧本、旁白与情绪节奏。",
            f"分镜 Agent：已通过{creative_source}拆分独立镜头并标记生成方式。",
            f"视觉设定 Agent：已通过{creative_source}锁定角色、场景和风格规范。",
            "生成调度 Agent：已准备好逐镜生成任务。",
            "项目归档：已保存项目 JSON，可继续渲染或导出。",
        ]
        emit({"type": "agent_start", "agent": "director"})
        brief = self.director.plan(cleaned_idea, duration, visual_style)
        emit({"type": "agent_done", "agent": "director", "brief": brief})
        emit({"type": "agent_start", "agent": "writer"})
        script = self.writer.write(cleaned_idea, brief)
        emit({"type": "agent_done", "agent": "writer", "script": script})
        emit({"type": "agent_start", "agent": "visual_bible"})
        visual_bible = self.visual_bible_agent.create(visual_style, brief, script)
        emit({"type": "agent_done", "agent": "visual_bible", "visual_bible": visual_bible})
        emit({"type": "agent_start", "agent": "storyboard"})
        storyboard = self.storyboard_agent.create(
            cleaned_idea, duration, visual_style, project_id, brief, script, visual_bible
        )
        emit(
            {
                "type": "agent_done",
                "agent": "storyboard",
                "storyboard": [shot.to_dict() for shot in storyboard],
            }
        )
        emit({"type": "agent_start", "agent": "quality"})
        quality_report = self.quality_gate.review(
            duration_seconds=duration,
            script=script,
            visual_bible=visual_bible,
            storyboard=storyboard,
        )
        emit({"type": "agent_done", "agent": "quality", "quality_report": quality_report})
        project = MovieProject(
            project_id=project_id,
            idea=cleaned_idea,
            duration_seconds=duration,
            visual_style=visual_style,
            status="planned_text_ai" if self.using_creative_llm else "planned_mock",
            brief=brief,
            script=script,
            visual_bible=visual_bible,
            storyboard=storyboard,
            quality_report=quality_report,
            logs=logs + quality_report,
        )
        self.store.save(project)
        emit({"type": "archived", "project_id": project_id})
        if self.settings.video_generation_mode == "comfyui":
            project.status = "ready_for_comfyui_render"
            project.logs.append("生成调度 Agent：项目已就绪，点击“Spark 真实生成并合成”后提交逐镜任务。")
            self.store.save(project)
            return project
        return self.run_mock_production(project_id, event_callback)

    def run_mock_production(
        self,
        project_id: str,
        event_callback: Callable[[dict], None] | None = None,
    ) -> MovieProject:
        """Simulate the state flow that will later call ComfyUI and FFmpeg."""

        def emit(event: dict) -> None:
            if event_callback is not None:
                event_callback(event)

        project = self.store.load(project_id)
        project.status = "generating_video_mock"
        project.logs.append("生成 Agent：开始模拟提交镜头任务队列。")
        emit({"type": "agent_start", "agent": "generation"})
        for shot in project.storyboard:
            project.logs.append(self.generation_agent.generate_mock(shot))
            emit({"type": "shot_update", "shot": shot.to_dict()})
            project.logs.append(self.reviewer.review_mock(shot))
            emit({"type": "shot_update", "shot": shot.to_dict()})
        emit({"type": "agent_done", "agent": "generation"})

        project.status = "completed_text_ai_video_mock" if self.using_creative_llm else "completed_mock"
        emit({"type": "agent_start", "agent": "editor"})
        project.logs.append(self.editor.assemble_mock(project))
        emit(
            {
                "type": "agent_done",
                "agent": "editor",
                "final_output": project.final_output_placeholder,
            }
        )
        project.logs.append(f"项目完成：最终成片预留路径为 {project.final_output_placeholder}。")
        self.store.save(project)
        return project

    def render_project(
        self,
        project_id: str,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> MovieProject:
        if self.settings.video_generation_mode != "comfyui":
            raise ValueError("当前为 mock 模式。请在 Spark 的 .env 设置 VIDEO_GENERATION_MODE=comfyui 后再渲染。")
        project = self.store.load(project_id)
        project.status = "rendering_comfyui"
        project.logs.append("生成调度 Agent：开始提交 Spark ComfyUI 逐镜任务。")
        self.store.save(project)
        total_shots = len(project.storyboard)
        for index, shot in enumerate(project.storyboard, start=1):
            if shot.status == "approved_comfyui" and Path(shot.output_placeholder).is_file():
                project.logs.append(f"生成调度 Agent：镜头 {shot.number} 已完成，断点续跑时跳过。")
                if progress_callback:
                    progress_callback(index, total_shots, f"镜头 {shot.number} 已完成，跳过")
                continue
            last_error: Exception | None = None
            for attempt in range(1, self.settings.comfy_max_retries + 1):
                try:
                    project.logs.append(self.generation_agent.generate(project.project_id, shot))
                    project.logs.append(self.reviewer.review_generated(shot))
                    self.store.save(project)
                    if progress_callback:
                        progress_callback(index, total_shots, f"镜头 {shot.number} 已生成并通过完整性质检")
                    last_error = None
                    break
                except Exception as error:
                    last_error = error
                    project.logs.append(
                        f"生成调度 Agent：镜头 {shot.number} 第 {attempt}/{self.settings.comfy_max_retries} 次失败：{error}"
                    )
                    self.store.save(project)
            if last_error is not None:
                project.status = "render_failed"
                project.logs.append("生成调度 Agent：可再次点击真实生成按钮，从未完成镜头继续。")
                self.store.save(project)
                raise RuntimeError(f"镜头 {shot.number} 多次生成失败：{last_error}") from last_error

        project.logs.append(self.editor.assemble(project))
        project.status = "completed_comfyui"
        project.logs.append(f"项目完成：真实成片已输出到 {project.final_output_placeholder}。")
        self.store.save(project)
        if progress_callback:
            progress_callback(total_shots, total_shots, "FFmpeg 合成完成")
        return project

    def regenerate_shot(self, project_id: str, shot_number: int) -> MovieProject:
        project = self.store.load(project_id)
        if not 1 <= shot_number <= len(project.storyboard):
            raise ValueError(f"镜头号必须在 1–{len(project.storyboard)} 之间。")
        index = shot_number - 1
        project.storyboard[index] = self.storyboard_agent.revise(project.storyboard[index], project.visual_bible)
        project.quality_report = self.quality_gate.review(
            duration_seconds=project.duration_seconds,
            script=project.script,
            visual_bible=project.visual_bible,
            storyboard=project.storyboard,
        )
        project.logs.append(f"分镜 Agent：已重新规划镜头 {shot_number}，保留其时长和叙事位置。")
        project.logs.extend(project.quality_report)
        self.store.save(project)
        return project
