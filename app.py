"""Gradio entry point for the Movie-Agent MVP."""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator


settings = Settings.from_env()
orchestrator = MovieOrchestrator(settings)


APP_CSS = """
:root {
  --ink: #2b3a53;
  --ocean: #4d81b0;
  --mist: #7a9ec1;
  --slate: #a4b1bc;
  --paper: #d7d6d2;
  --white: #f5f6f4;
}
body, .gradio-container {
  background:
    radial-gradient(circle at 82% -12%, rgba(122,158,193,.55), transparent 30rem),
    linear-gradient(135deg, #d7d6d2 0%, #e6e6e1 44%, #c9d6df 100%);
  color: var(--ink);
}
.gradio-container {
  max-width: 1440px !important;
  padding: 30px 28px 48px !important;
  font-family: "Noto Serif SC", "Songti SC", Georgia, serif;
}
.movie-hero {
  position: relative;
  overflow: hidden;
  margin-bottom: 22px;
  padding: 34px 40px 32px;
  border: 1px solid rgba(215,214,210,.22);
  border-radius: 18px;
  color: #f5f6f4;
  background: linear-gradient(120deg, #2b3a53 0%, #314d6c 50%, #4d81b0 150%);
  box-shadow: 0 16px 42px rgba(43,58,83,.22);
}
.movie-hero::after {
  content: "";
  position: absolute;
  inset: auto -40px -90px auto;
  width: 420px;
  height: 220px;
  border: 1px solid rgba(215,214,210,.24);
  border-radius: 50%;
  transform: rotate(-12deg);
}
.movie-hero__eyebrow {
  margin: 0 0 9px;
  color: #b9d4e8;
  font-family: Arial, sans-serif;
  font-size: .75rem;
  font-weight: 700;
  letter-spacing: .18em;
  text-transform: uppercase;
}
.movie-hero h1 { margin: 0; font-size: clamp(2rem, 4vw, 3.25rem); letter-spacing: .04em; }
.movie-hero p:last-child { max-width: 630px; margin: 12px 0 0; color: #dfeaf0; font-size: 1.02rem; line-height: 1.8; }
.panel {
  padding: 17px !important;
  border: 1px solid rgba(43,58,83,.13) !important;
  border-radius: 14px !important;
  background: rgba(245,246,244,.78) !important;
  box-shadow: 0 8px 22px rgba(43,58,83,.07) !important;
}
.panel-title { margin: 3px 0 12px; color: var(--ink); font-size: 1.02rem; font-weight: 700; letter-spacing: .08em; }
.stage-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin: 0 0 14px;
}
.stage-strip span {
  display: block;
  padding: 9px 7px;
  border-radius: 9px;
  color: #f5f6f4;
  background: var(--ocean);
  font-family: Arial, sans-serif;
  font-size: .74rem;
  letter-spacing: .04em;
  text-align: center;
}
.stage-strip span:nth-child(2) { background: #5f91bb; }
.stage-strip span:nth-child(3) { background: var(--mist); }
.stage-strip span:nth-child(4) { background: var(--slate); color: var(--ink); }
#create-button button, #render-button button {
  min-height: 46px;
  border: 0 !important;
  border-radius: 9px !important;
  color: #f5f6f4 !important;
  background: var(--ink) !important;
  box-shadow: 0 7px 16px rgba(43,58,83,.2) !important;
  font-weight: 700 !important;
  letter-spacing: .06em;
}
#render-button button { background: var(--ocean) !important; }
#create-button button:hover, #render-button button:hover { filter: brightness(1.12); transform: translateY(-1px); }
textarea, input, .wrap, .prose, .markdown { font-family: "Noto Serif SC", "Songti SC", Georgia, serif !important; }
.block, .form, .gr-box, .gr-panel { border-color: rgba(43,58,83,.14) !important; }
label span { color: var(--ink) !important; font-weight: 600; }
#status textarea, #final-output textarea { color: var(--ink) !important; background: rgba(215,214,210,.5) !important; }
#final-video { overflow: hidden; border: 1px solid rgba(43,58,83,.18); border-radius: 12px; }
@media (max-width: 760px) {
  .gradio-container { padding: 16px !important; }
  .movie-hero { padding: 26px 23px; }
  .stage-strip { grid-template-columns: repeat(2, 1fr); }
}
"""


def create_project(idea: str, duration: int, visual_style: str):
    try:
        project = orchestrator.create_project(idea, duration, visual_style)
    except Exception as error:
        return ("", "", "", "", "", f"## 任务日志\n- 失败：{error}", f"创作失败：{error}", "", None, gr.update())
    text_mode = "ModelScope AI 文案" if orchestrator.using_creative_llm else "mock 文案"
    video_mode = "Spark 真实视频待生成" if settings.video_generation_mode == "comfyui" else "mock 视频流程"
    return _project_outputs(
        project,
        f"已完成：{text_mode} + {video_mode}（{project.project_id}）",
        gr.update(choices=orchestrator.store.list_project_ids(), value=project.project_id),
    )


def load_project(project_id: str):
    if not project_id:
        return ("", "", "", "", "", "## 任务日志\n- 请先选择一个项目。", "尚未选择项目", "", None, gr.update())
    try:
        project = orchestrator.store.load(project_id)
    except Exception as error:
        return ("", "", "", "", "", f"## 任务日志\n- 失败：{error}", f"读取失败：{error}", "", None, gr.update())
    return _project_outputs(project, f"已恢复项目：{project.project_id}", gr.update(value=project.project_id))


def refresh_history():
    project_ids = orchestrator.store.list_project_ids()
    return gr.update(choices=project_ids, value=project_ids[0] if project_ids else None)


def regenerate_shot(project_id: str, shot_number: int):
    try:
        project = orchestrator.regenerate_shot(project_id, int(shot_number))
    except Exception as error:
        return ("", "", "", "", "", f"## 任务日志\n- 失败：{error}", f"重新规划失败：{error}", "", None, gr.update())
    return _project_outputs(project, f"已重新规划镜头 {int(shot_number)}", gr.update(value=project.project_id))


def render_project(project_id: str, progress=gr.Progress()):
    try:
        progress(0, desc="正在连接 Spark ComfyUI")
        project = orchestrator.render_project(
            project_id,
            progress_callback=lambda completed, total, description: progress(
                completed / total, desc=description
            ),
        )
    except Exception as error:
        return ("", "", "", "", "", f"## 任务日志\n- 失败：{error}", f"渲染失败：{error}", "", None, gr.update())
    return _project_outputs(
        project,
        f"真实成片已生成（{project.project_id}）",
        gr.update(value=project.project_id),
    )


def export_project(project_id: str):
    if not project_id:
        raise gr.Error("请先创建或打开一个项目。")
    return [str(path) for path in orchestrator.store.export(project_id)]


def _project_outputs(project, status_message: str, history_update):
    return (
        project.project_id,
        project.brief_as_markdown(),
        project.script_as_markdown(),
        project.visual_bible_as_markdown(),
        project.storyboard_as_markdown(),
        project.log_as_markdown(),
        status_message,
        project.final_output_placeholder or "",
        _video_value(project.final_output_placeholder),
        history_update,
    )


def _video_value(path: str | None) -> str | None:
    return path if path and Path(path).is_file() else None


with gr.Blocks(title="Movie-Agent · 流影制片台", css=APP_CSS) as demo:
    gr.HTML(
        """
        <section class="movie-hero">
          <p class="movie-hero__eyebrow">Movie-Agent / AI Film Studio</p>
          <h1>流影制片台</h1>
          <p>从一句原创科幻创意，走向剧本、分镜、视觉设定与 Spark 上的真实成片。</p>
        </section>
        """
    )
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group(elem_classes="panel"):
                gr.HTML("<div class='panel-title'>01 / 创意输入</div>")
                idea = gr.Textbox(
                    label="原创科幻创意",
                    lines=5,
                    placeholder="例如：最后一位城市值班员每天点亮空城，直到发现整座城市都在等待他下班。",
                )
                duration = gr.Slider(30, 80, value=48, step=1, label="目标时长（秒）")
                visual_style = gr.Dropdown(
                    ["写实近未来", "胶片科幻", "极简冷色", "梦境超现实"],
                    value="写实近未来",
                    label="视觉风格",
                )
                submit = gr.Button("开始创作", variant="primary", elem_id="create-button")
            with gr.Group(elem_classes="panel"):
                gr.HTML("<div class='panel-title'>02 / 项目控制</div>")
                history = gr.Dropdown(
                    choices=orchestrator.store.list_project_ids(), label="已保存项目", interactive=True
                )
                with gr.Row():
                    refresh = gr.Button("刷新历史")
                    load = gr.Button("打开项目")
                shot_number = gr.Slider(1, 10, value=1, step=1, label="要重新规划的镜头号")
                regenerate = gr.Button("重新规划单个镜头")
                render = gr.Button("Spark 真实生成并合成", variant="primary", elem_id="render-button")
                export = gr.Button("导出项目 JSON 与 Markdown")
        with gr.Column(scale=2):
            gr.HTML("<div class='stage-strip'><span>设定与剧本</span><span>分镜与视觉</span><span>H3 生成</span><span>剪辑成片</span></div>")
            with gr.Group(elem_classes="panel"):
                status = gr.Textbox(label="制作状态", interactive=False, elem_id="status")
                project_id = gr.Textbox(label="项目 ID", interactive=False)
                final_output = gr.Textbox(label="成片输出路径", interactive=False, elem_id="final-output")
                final_video = gr.Video(label="最终成片", interactive=False, elem_id="final-video")
            with gr.Group(elem_classes="panel"):
                brief = gr.Markdown(label="项目设定")
                script = gr.Markdown(label="剧本与旁白")
                visual_bible = gr.Markdown(label="视觉设定")
                storyboard = gr.Markdown(label="分镜")
                logs = gr.Markdown(label="任务日志")
                exports = gr.File(label="项目导出", file_count="multiple", interactive=False)

    # Keep creation and history recovery on the same display contract.
    submit.click(
        create_project,
        inputs=[idea, duration, visual_style],
        outputs=[project_id, brief, script, visual_bible, storyboard, logs, status, final_output, final_video, history],
    )
    refresh.click(refresh_history, outputs=history)
    load.click(
        load_project,
        inputs=history,
        outputs=[project_id, brief, script, visual_bible, storyboard, logs, status, final_output, final_video, history],
    )
    regenerate.click(
        regenerate_shot,
        inputs=[project_id, shot_number],
        outputs=[project_id, brief, script, visual_bible, storyboard, logs, status, final_output, final_video, history],
    )
    render.click(
        render_project,
        inputs=project_id,
        outputs=[project_id, brief, script, visual_bible, storyboard, logs, status, final_output, final_video, history],
    )
    export.click(export_project, inputs=project_id, outputs=exports)


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=1).launch(server_name="0.0.0.0", server_port=settings.port)
