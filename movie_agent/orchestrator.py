"""Coordinates the MVP planning stages and stores their output."""

from __future__ import annotations

from uuid import uuid4

from movie_agent.config import Settings
from movie_agent.models import MovieProject
from movie_agent.services.mock_creator import build_storyboard
from movie_agent.storage.project_store import ProjectStore


class MovieOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = ProjectStore(settings.projects_dir)

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
            brief={
                "原始创意": cleaned_idea,
                "主题": "人在智能系统包围下重新确认自身选择的意义",
                "叙事尺度": "一个人 + 一个空间 + 一件小事",
                "视觉风格": visual_style,
                "目标时长": f"{duration} 秒",
                "合规约束": "仅使用原创或已授权素材；不复刻现有影视 IP、角色、台词或肖像。",
            },
            script={
                "story": (
                    f"主角置身于一个安静而高度自动化的空间。{cleaned_idea} "
                    "他先把异常当成系统噪声，随后发现那个细小变化正迫使自己作出选择。"
                    "结尾不解释所有答案，只留下一个与开场形成呼应的动作。"
                ),
                "narration": "未来最难被自动化的，也许不是工作，而是决定何时相信自己。",
            },
            visual_bible={
                "角色卡": "单一主角；中性、克制的服装；所有镜头保持同一发型、服饰轮廓和情绪状态。",
                "场景卡": "单一封闭近未来空间；少量可重复识别的控制台、窗面与冷色光源。",
                "风格卡": f"{visual_style}；低饱和、有限色板、慢镜头运动、以特写和空镜推进叙事。",
                "声音卡": "环境底噪、设备低鸣、克制配乐；避免模仿可识别人物音色。",
            },
            storyboard=build_storyboard(cleaned_idea, duration, visual_style, project_id),
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
            shot.status = "generating_mock"
            shot.attempts += 1
            project.logs.append(f"生成 Agent：镜头 {shot.number} 已进入 mock 生成队列。")
            shot.status = "approved_mock"
            project.logs.append(f"质检 Agent：镜头 {shot.number} 通过 mock 一致性与合规检查。")

        project.status = "completed_mock"
        project.final_output_placeholder = f"outputs/{project.project_id}/final-cut.mp4"
        project.logs.append("剪辑 Agent：已模拟合并镜头、字幕和音轨。")
        project.logs.append(f"项目完成：最终成片预留路径为 {project.final_output_placeholder}。")
        self.store.save(project)
        return project
