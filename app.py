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
  --ink: #21324a;
  --ocean: #3f769f;
  --mist: #7a9ec1;
  --slate: #a4b1bc;
  --paper: #eef0ed;
  --line: #c7d0d5;
  --surface: #fbfcfa;
  --muted: #526274;
}
body, .gradio-container {
  background:
    radial-gradient(circle at 92% -10%, rgba(122,158,193,.35), transparent 29rem),
    linear-gradient(135deg, #eef0ed 0%, #e2e7e7 46%, #d5e0e6 100%);
  color: var(--ink);
}
.gradio-container {
  max-width: 1480px !important;
  padding: 28px clamp(16px, 3vw, 42px) 52px !important;
  font-family: "Noto Sans SC", "Microsoft YaHei UI", Arial, sans-serif;
}
.movie-hero {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: end;
  margin-bottom: 20px;
  padding: 34px clamp(24px, 4vw, 52px);
  border: 1px solid rgba(215,214,210,.22);
  border-radius: 16px;
  color: #f5f6f4;
  background: linear-gradient(112deg, #21324a 0%, #2b4664 54%, #3f769f 145%);
  box-shadow: 0 18px 44px rgba(33,50,74,.19);
}
.movie-hero::after {
  content: "";
  position: absolute;
  inset: auto -40px -90px auto;
  width: 440px;
  height: 245px;
  border: 1px solid rgba(215,214,210,.24);
  border-radius: 50%;
  transform: rotate(-12deg);
}
.movie-hero__eyebrow {
  margin: 0 0 9px;
  color: #b9d4e8;
  font-family: "Noto Sans SC", Arial, sans-serif;
  font-size: .75rem;
  font-weight: 700;
  letter-spacing: .18em;
  text-transform: uppercase;
}
.movie-hero h1 { margin: 0; font-family: "Noto Serif SC", "Songti SC", Georgia, serif; font-size: clamp(2.2rem, 4vw, 3.55rem); font-weight: 600; letter-spacing: .08em; }
.movie-hero p:last-child { max-width: 630px; margin: 12px 0 0; color: #dfeaf0; font-size: 1rem; line-height: 1.85; }
.hero-status { position: relative; z-index: 1; display: grid; gap: 6px; min-width: 178px; padding: 13px 15px; border: 1px solid rgba(215,214,210,.3); border-radius: 10px; background: rgba(15,29,45,.16); backdrop-filter: blur(6px); font-size: .78rem; line-height: 1.45; }
.hero-status strong { font-size: .9rem; letter-spacing: .05em; }
.hero-status span { color: #c6ddeb; }
.panel {
  padding: 19px !important;
  border: 1px solid var(--line) !important;
  border-radius: 12px !important;
  background: rgba(251,252,250,.9) !important;
  box-shadow: 0 8px 24px rgba(33,50,74,.06) !important;
}
.panel-title { margin: 2px 0 14px; color: var(--ink); font-size: .82rem; font-weight: 800; letter-spacing: .12em; }
.panel-note { margin: -7px 0 15px; color: var(--muted); font-size: .82rem; line-height: 1.6; }
.stage-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin: 0 0 12px;
}
.stage-strip span {
  display: block;
  padding: 12px 11px;
  border: 1px solid var(--line);
  border-radius: 10px;
  color: var(--ink);
  background: rgba(251,252,250,.72);
  font-size: .76rem;
  font-weight: 700;
  letter-spacing: .03em;
}
.stage-strip b { display: block; margin-bottom: 3px; color: var(--ocean); font-size: .7rem; letter-spacing: .09em; }
.stage-strip span:nth-child(3) { border-color: rgba(63,118,159,.5); background: #e0edf3; }
#create-button button, #render-button button {
  min-height: 46px;
  border: 1px solid transparent !important;
  border-radius: 8px !important;
  color: #f5f6f4 !important;
  background: var(--ink) !important;
  box-shadow: 0 6px 14px rgba(33,50,74,.16) !important;
  font-weight: 700 !important;
  letter-spacing: .06em;
}
#render-button button { background: var(--ocean) !important; }
#create-button button:hover, #render-button button:hover { filter: brightness(1.08); box-shadow: 0 8px 18px rgba(33,50,74,.21) !important; }
button, textarea, input, .wrap, .prose, .markdown { font-family: "Noto Sans SC", "Microsoft YaHei UI", Arial, sans-serif !important; }
.prose h1, .prose h2, .prose h3, .markdown h1, .markdown h2, .markdown h3 { font-family: "Noto Serif SC", "Songti SC", Georgia, serif !important; color: var(--ink); }
.block, .form, .gr-box, .gr-panel { border-color: var(--line) !important; }
label span { color: var(--ink) !important; font-weight: 700; }
#create-button button:focus-visible, #render-button button:focus-visible, button:focus-visible, input:focus-visible, textarea:focus-visible { outline: 3px solid rgba(63,118,159,.4) !important; outline-offset: 2px !important; }
#status textarea, #final-output textarea { color: var(--ink) !important; background: rgba(215,214,210,.5) !important; }
#final-video { overflow: hidden; border: 1px solid rgba(43,58,83,.18); border-radius: 12px; }
.tabs > .tab-nav button { color: var(--muted) !important; font-weight: 700 !important; }
.tabs > .tab-nav button.selected { color: var(--ink) !important; border-color: var(--ocean) !important; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; } }
@media (max-width: 760px) {
  .gradio-container { padding: 16px !important; }
  .movie-hero { padding: 26px 23px; }
  .movie-hero { grid-template-columns: 1fr; }
  .hero-status { min-width: 0; }
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
          <div><p class="movie-hero__eyebrow">Movie-Agent / AI Film Studio</p><h1>流影制片台</h1><p>从一句原创科幻创意，走向剧本、分镜、视觉设定与 Spark 上的真实成片。</p></div>
          <aside class="hero-status"><strong>制作引擎就绪</strong><span>文本策划 · H3 生成 · FFmpeg 合片</span></aside>
        </section>
        """
    )
    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group(elem_classes="panel"):
                gr.HTML("<div class='panel-title'>01 / 创意输入</div>")
                gr.HTML("<p class='panel-note'>先完成文字策划；确认分镜后，再单独提交 Spark 渲染任务。</p>")
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
                gr.HTML("<p class='panel-note'>项目会持续保存。渲染中断后，重新点击即可从已完成镜头继续。</p>")
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
            gr.HTML("<div class='stage-strip'><span><b>01</b>设定与剧本</span><span><b>02</b>分镜与视觉</span><span><b>03</b>H3 生成</span><span><b>04</b>剪辑成片</span></div>")
            with gr.Group(elem_classes="panel"):
                status = gr.Textbox(label="制作状态", interactive=False, elem_id="status")
                project_id = gr.Textbox(label="项目 ID", interactive=False)
                final_output = gr.Textbox(label="成片输出路径", interactive=False, elem_id="final-output")
                final_video = gr.Video(label="最终成片", interactive=False, elem_id="final-video")
            with gr.Tabs():
                with gr.Tab("创作蓝图"):
                    with gr.Group(elem_classes="panel"):
                        brief = gr.Markdown(label="项目设定")
                        script = gr.Markdown(label="剧本与旁白")
                        visual_bible = gr.Markdown(label="视觉设定")
                with gr.Tab("分镜与生产"):
                    with gr.Group(elem_classes="panel"):
                        storyboard = gr.Markdown(label="分镜")
                        logs = gr.Markdown(label="任务日志")
                with gr.Tab("交付文件"):
                    with gr.Group(elem_classes="panel"):
                        gr.Markdown("### 导出\n将项目方案导出为 JSON 与 Markdown，便于提交比赛材料或继续制作。")
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
