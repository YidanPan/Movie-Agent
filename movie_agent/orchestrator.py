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
from movie_agent.services.quality import PlanningQualityGate, SemanticCopyrightReviewer
from movie_agent.services.subtitles import (
    align_script_to_shots,
    ensure_dialogue_assets,
    normalise_subtitle_mode,
    shot_count_for_duration,
)


class MovieOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = ProjectStore(settings.projects_dir)
        creative_llm = build_creative_llm(settings)
        self.using_creative_llm = creative_llm is not None
        self.director = DirectorAgent(creative_llm)
        self.writer = WriterAgent(creative_llm)
        supported_modes = {"T2V"} if settings.video_generation_mode == "comfyui" else None
        self.storyboard_agent = StoryboardAgent(creative_llm, supported_modes)
        self.visual_bible_agent = VisualBibleAgent(creative_llm)
        self.generation_agent = GenerationAgent(settings)
        self.reviewer = ReviewerAgent(settings)
        self.editor = EditorAgent(settings)
        self.quality_gate = PlanningQualityGate()
        self.semantic_copyright_reviewer = SemanticCopyrightReviewer(creative_llm)

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
            f"编剧 Agent：已通过{creative_source}生成短剧本、旁白、台词本与字幕轨。",
            f"分镜 Agent：已通过{creative_source}拆分独立镜头并标记生成方式。",
            f"视觉设定 Agent：已通过{creative_source}锁定角色、场景和风格规范。",
            "生成调度 Agent：已准备好逐镜生成任务。",
            "台词本：Dialogue Book 与 Subtitle Track 已生成，等待用户锁定。",
            "项目归档：已保存项目 JSON，可继续审阅、AI 剪辑或导出。",
        ]
        emit({"type": "agent_start", "agent": "director"})
        emit(
            {
                "type": "artifact",
                "agent": "director",
                "title": "创意拆解",
                "content": "正在提取核心意象、冲突对象和观众最后一秒应获得的情绪。",
            }
        )
        emit(
            {
                "type": "chat",
                "from": "director",
                "to": "writer",
                "message": "我先锁定一个可被动作表达的冲突，编剧收到设定后再补足人物选择。",
            }
        )
        brief = self.director.plan(cleaned_idea, duration, visual_style)
        emit({"type": "agent_done", "agent": "director", "brief": brief})
        emit(
            {
                "type": "artifact",
                "agent": "director",
                "title": "导演手记",
                "content": (
                    f"核心意象：{brief.get('主题', '孤独与自动化')}。"
                    "观众应在最后一秒才意识到主角的选择意味着什么。"
                ),
            }
        )
        emit(
            {
                "type": "chat",
                "from": "director",
                "to": "writer",
                "message": (
                    "这个创意的核心冲突很清晰，建议聚焦主角的内心转折，"
                    "不要过度解释世界观，让观众从动作里自己感受。"
                ),
            }
        )
        emit({"type": "agent_start", "agent": "writer"})
        emit(
            {
                "type": "artifact",
                "agent": "writer",
                "title": "冲突草稿",
                "content": "正在把世界观压缩成一个人物、一个异常和一次不可逆的选择。",
            }
        )
        planned_shot_count = shot_count_for_duration(duration)
        script = self.writer.write(
            cleaned_idea,
            brief,
            duration_seconds=duration,
            shot_count=planned_shot_count,
        )
        emit({"type": "agent_done", "agent": "writer", "script": script})
        emit(
            {
                "type": "artifact",
                "agent": "writer",
                "title": "台词本 / 字幕稿",
                "content": (
                    f"已按 {planned_shot_count} 个镜头生成 Dialogue Book 与 Subtitle Track，"
                    "请在制作手册中审阅、编辑并锁定。"
                ),
            }
        )
        if script.get("outline"):
            emit(
                {
                    "type": "artifact",
                    "agent": "writer",
                    "title": "故事大纲",
                    "content": script["outline"],
                }
            )
        emit(
            {
                "type": "chat",
                "from": "writer",
                "to": "visual_bible",
                "message": (
                    "故事需要一个压抑但温暖的视觉基调，"
                    "主角所处的空间应该有旧金属和暖黄色灯光的对比。"
                ),
            }
        )
        emit({"type": "agent_start", "agent": "visual_bible"})
        emit(
            {
                "type": "artifact",
                "agent": "visual_bible",
                "title": "材质样本",
                "content": "旧金属、玻璃反光与唯一暖色光源进入视觉候选，等待剧本确认情绪方向。",
            }
        )
        visual_bible = self.visual_bible_agent.create(visual_style, brief, script)
        emit({"type": "agent_done", "agent": "visual_bible", "visual_bible": visual_bible})
        emit(
            {
                "type": "artifact",
                "agent": "visual_bible",
                "title": "情绪板",
                "content": (
                    f"{visual_style}主导。旧金属、钨丝灯、冷灰墙面，"
                    "唯一暖源来自主角手中的设备。"
                ),
            }
        )
        emit(
            {
                "type": "chat",
                "from": "visual_bible",
                "to": "storyboard",
                "message": (
                    "前三个镜头建议固定机位，只在结尾用一次缓慢推轨，"
                    "这样运动才有意义。"
                ),
            }
        )
        emit({"type": "agent_start", "agent": "storyboard"})
        emit(
            {
                "type": "artifact",
                "agent": "storyboard",
                "title": "机位草图",
                "content": "先以固定机位建立秩序，再把镜头运动留给关键转折，避免每一镜都在炫技。",
            }
        )
        storyboard = self.storyboard_agent.create(
            cleaned_idea, duration, visual_style, project_id, brief, script, visual_bible
        )
        script = align_script_to_shots(script, storyboard)
        emit(
            {
                "type": "agent_done",
                "agent": "storyboard",
                "storyboard": [shot.to_dict() for shot in storyboard],
            }
        )
        emit(
            {
                "type": "artifact",
                "agent": "storyboard",
                "title": "镜头节奏",
                "content": (
                    f"{len(storyboard)} 镜构成：静-静-静-动-静，"
                    f"结尾 {storyboard[-1].duration_seconds if storyboard else 4} 秒留白。"
                ),
            }
        )
        emit(
            {
                "type": "chat",
                "from": "storyboard",
                "to": "director",
                "message": (
                    f"{len(storyboard)} 个镜头可以覆盖完整叙事弧线，"
                    "是否需要预留一个备用镜头以防节奏过快？"
                ),
            }
        )
        emit({"type": "agent_start", "agent": "quality"})
        emit(
            {
                "type": "artifact",
                "agent": "quality",
                "title": "质检预扫描",
                "content": "正在并行检查时长、镜头数量、提示词完整性和潜在版权近似。",
            }
        )
        quality_report = self.quality_gate.review(
            duration_seconds=duration,
            script=script,
            visual_bible=visual_bible,
            storyboard=storyboard,
        )
        quality_report.extend(
            self.semantic_copyright_reviewer.review(
                idea=cleaned_idea,
                script=script,
                visual_bible=visual_bible,
                storyboard=storyboard,
            )
        )
        emit({"type": "agent_done", "agent": "quality", "quality_report": quality_report})
        emit(
            {
                "type": "chat",
                "from": "quality",
                "to": "all",
                "message": (
                    "剧本与视觉描述已通过版权检查，所有元素均为原创，"
                    f"共发现 {len(quality_report)} 项需要关注的点。"
                ),
            }
        )
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
            project.logs.append("生成调度 Agent：项目已就绪，点击“Spark 真实生成”后提交逐镜任务。")
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
            # Keep the mock path resumable too: a refresh during the staged
            # reveal should not discard completed shot states.
            self.store.save(project)
        emit({"type": "agent_done", "agent": "generation"})

        project.status = "ready_for_ai_edit"
        project.logs.append(f"生成 Agent：{len(project.storyboard)}/{len(project.storyboard)} SHOTS READY，当前阶段已推进到 DELIVER。")
        project.logs.append("剪辑 Agent：等待用户锁定台词本后启动 AI Edit Rough Cut。")
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
        self._require_dialogue_locked(project)
        unsupported_modes = sorted(
            {shot.generation_mode for shot in project.storyboard if shot.generation_mode != "T2V"}
        )
        if unsupported_modes:
            modes = "、".join(unsupported_modes)
            raise ValueError(
                f"当前 Spark 已验证工作流仅支持 T2V，项目中仍有 {modes} 镜头。"
                "请重新规划这些镜头后再提交真实生成。"
            )
        project.status = "rendering_comfyui"
        project.final_output_placeholder = None
        project.rough_cut_placeholder = None
        project.edit_plan = {}
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
                    project.logs.append(
                        self.reviewer.review_generated(
                            shot,
                            project_id=project.project_id,
                            visual_bible=project.visual_bible,
                        )
                    )
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

        project.status = "ready_for_ai_edit"
        project.logs.append(f"生成 Agent：{len(project.storyboard)}/{len(project.storyboard)} SHOTS READY，当前阶段已推进到 DELIVER。")
        project.logs.append("剪辑 Agent：等待用户启动 AI Edit，先生成 Rough Cut 再批准最终成片。")
        self.store.save(project)
        if progress_callback:
            progress_callback(
                total_shots,
                total_shots,
                f"{total_shots}/{total_shots} SHOTS READY · 等待 AI Edit",
            )
        return project

    def render_shot(self, project_id: str, shot_number: int) -> MovieProject:
        """Regenerate one shot from the Inspector without assembling the full film."""
        if self.settings.video_generation_mode != "comfyui":
            raise ValueError("当前为 mock 模式。请在 Spark 的 .env 设置 VIDEO_GENERATION_MODE=comfyui 后再生成镜头。")
        project = self.store.load(project_id)
        if not 1 <= shot_number <= len(project.storyboard):
            raise ValueError(f"镜头号必须在 1–{len(project.storyboard)} 之间。")
        shot = project.storyboard[shot_number - 1]
        if shot.generation_mode != "T2V":
            raise ValueError(
                f"镜头 {shot.number} 标记为 {shot.generation_mode}，但当前 MiniMax-H3 工作流仅支持 T2V。"
            )

        shot.status = "replanned"
        project.status = "rendering_comfyui"
        project.final_output_placeholder = None
        project.rough_cut_placeholder = None
        project.edit_plan = {}
        project.logs.append(f"生成调度 Agent：Inspector 已提交镜头 {shot_number} 的单镜重生成。")
        self.store.save(project)
        try:
            project.logs.append(self.generation_agent.generate(project.project_id, shot))
            project.logs.append(
                self.reviewer.review_generated(
                    shot,
                    project_id=project.project_id,
                    visual_bible=project.visual_bible,
                )
            )
        except Exception as error:
            project.status = "render_failed"
            project.logs.append(f"生成调度 Agent：镜头 {shot_number} 单镜生成失败：{error}")
            self.store.save(project)
            raise

        project.status = (
            "ready_for_ai_edit"
            if all(str(item.status).startswith("approved") for item in project.storyboard)
            else "ready_for_comfyui_render"
        )
        project.logs.append(f"质检 Agent：镜头 {shot_number} 已通过单镜检查，可继续合成完整成片。")
        self.store.save(project)
        return project

    @staticmethod
    def _require_dialogue_locked(project: MovieProject) -> None:
        if not bool((project.script or {}).get("dialogue_locked")):
            raise ValueError("请先在编剧阶段审阅并锁定台词本 / 字幕稿。")

    @staticmethod
    def _invalidate_edit_outputs(project: MovieProject) -> None:
        """Drop stale rough/final media whenever an upstream asset changes."""

        project.final_output_placeholder = None
        project.rough_cut_placeholder = None
        project.edit_plan = {}
        shots_ready = bool(project.storyboard) and all(
            str(shot.status).startswith("approved") for shot in project.storyboard
        )
        if shots_ready:
            project.status = "ready_for_ai_edit"
        elif str(project.status).startswith("completed"):
            project.status = "ready_for_comfyui_render"

    def update_dialogue(
        self,
        project_id: str,
        *,
        dialogue_book: list[dict],
        subtitle_track: list[dict] | None = None,
    ) -> MovieProject:
        project = self.store.load(project_id)
        if bool((project.script or {}).get("dialogue_locked")):
            raise ValueError("台词本已锁定。如需修改，请先解锁当前版本并重新审核。")
        script = ensure_dialogue_assets(
            {
                **project.script,
                "dialogue_book": dialogue_book,
                "subtitle_track": subtitle_track if subtitle_track else dialogue_book,
            },
            duration_seconds=project.duration_seconds,
            shot_count=len(project.storyboard) or None,
        )
        script["dialogue_revision"] = int(script.get("dialogue_revision", 1)) + 1
        project.script = align_script_to_shots(script, project.storyboard)
        self._invalidate_edit_outputs(project)
        project.logs.append("场记：已保存台词本与字幕轨草稿，尚未锁定。")
        self.store.save(project)
        return project

    def lock_dialogue(self, project_id: str) -> MovieProject:
        project = self.store.load(project_id)
        # Do not silently lock a brand-new empty payload that the normaliser
        # would otherwise turn into placeholder lines.
        if not (project.script or {}).get("dialogue_book") or not (project.script or {}).get("subtitle_track"):
            raise ValueError("台词本或字幕轨为空，无法锁定。")
        project.script = ensure_dialogue_assets(
            project.script,
            duration_seconds=project.duration_seconds,
            shot_count=len(project.storyboard) or None,
        )
        if not project.script.get("dialogue_book") or not project.script.get("subtitle_track"):
            raise ValueError("台词本或字幕轨为空，无法锁定。")
        project.script["dialogue_locked"] = True
        project.logs.append(
            f"场记：已锁定台词本 / 字幕稿第 {project.script.get('dialogue_revision', 1)} 版，后续配音、字幕与剪辑均以此为准。"
        )
        self.store.save(project)
        return project

    def unlock_dialogue(self, project_id: str) -> MovieProject:
        """Allow an explicit revision pass and invalidate downstream edits."""

        project = self.store.load(project_id)
        if not bool((project.script or {}).get("dialogue_locked")):
            return project
        project.script["dialogue_locked"] = False
        self._invalidate_edit_outputs(project)
        project.logs.append("场记：已解锁台词本，允许修改后重新审核并锁定。")
        self.store.save(project)
        return project

    def set_subtitle_mode(self, project_id: str, mode: str) -> MovieProject:
        project = self.store.load(project_id)
        project.subtitle_mode = normalise_subtitle_mode(mode)
        project.script["subtitle_mode"] = project.subtitle_mode
        self.store.save(project)
        return project

    def create_rough_cut(
        self,
        project_id: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> MovieProject:
        project = self.store.load(project_id)
        self._require_dialogue_locked(project)
        if not project.storyboard or not all(str(shot.status).startswith("approved") for shot in project.storyboard):
            raise ValueError("全部镜头通过质检后才能启动 AI Edit。")
        project.status = "editing_rough_cut"
        project.logs.append("剪辑 Agent：启动 AI Edit，读取已锁定台词本与字幕轨。")
        self.store.save(project)
        if progress_callback:
            progress_callback("AI Edit：正在排序镜头并计算 Trim / 转场。")
        project.logs.append("剪辑 Agent：镜头排序、Trim 与转场已完成。")
        if progress_callback:
            progress_callback("AI Edit：正在编排旁白、BGM、SFX 与字幕轨。")
        project.logs.append("剪辑 Agent：旁白、BGM、SFX 与字幕轨已挂接。")
        project.logs.append(self.editor.create_rough_cut(project))
        project.status = "rough_cut_ready"
        project.logs.append("剪辑 Agent：Rough Cut 已完成，可预览、重新剪辑或批准最终成片。")
        self.store.save(project)
        return project

    def approve_edit(self, project_id: str, subtitle_mode: str | None = None) -> MovieProject:
        project = self.store.load(project_id)
        self._require_dialogue_locked(project)
        if project.status not in {"rough_cut_ready", "editing_rough_cut"}:
            raise ValueError("请先完成 Rough Cut，再批准最终成片。")
        if subtitle_mode:
            project.subtitle_mode = normalise_subtitle_mode(subtitle_mode)
        project.status = "editing_final"
        project.logs.append(f"剪辑 Agent：收到最终批准，按 {project.subtitle_mode} 字幕模式导出。")
        self.store.save(project)
        if self.settings.video_generation_mode == "comfyui":
            project.logs.append(self.editor.assemble(project, project.subtitle_mode))
            project.status = "completed_comfyui"
        else:
            project.logs.append(self.editor.assemble_mock(project))
            project.status = "completed_text_ai_video_mock" if self.using_creative_llm else "completed_mock"
        project.logs.append(f"项目完成：最终成片已批准，交付模式为 {project.subtitle_mode}。")
        self.store.save(project)
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
        project.quality_report.extend(
            self.semantic_copyright_reviewer.review(
                idea=project.idea,
                script=project.script,
                visual_bible=project.visual_bible,
                storyboard=project.storyboard,
            )
        )
        project.final_output_placeholder = None
        project.rough_cut_placeholder = None
        project.edit_plan = {}
        project.status = "ready_for_ai_edit" if all(
            str(shot.status).startswith("approved") for shot in project.storyboard
        ) else "ready_for_comfyui_render"
        project.logs.append(f"分镜 Agent：已重新规划镜头 {shot_number}，保留其时长和叙事位置。")
        project.logs.extend(project.quality_report)
        self.store.save(project)
        return project
