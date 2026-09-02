"""Gradio entry point for the Movie-Agent MVP."""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator


settings = Settings.from_env()
orchestrator = MovieOrchestrator(settings)


APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&family=Noto+Serif+SC:wght@500;600;700&display=swap');
:root {
  --ink: #161514;
  --ink-soft: #292725;
  --accent: #dd4e38;
  --accent-deep: #b63322;
  --paper: #f5f2ea;
  --surface: #fffdf8;
  --surface-muted: #ece7dd;
  --line: #d8d0c4;
  --muted: #756e64;
  --success: #366552;
}
body, .gradio-container {
  background: var(--paper);
  color: var(--ink);
}
.gradio-container {
  max-width: 1540px !important;
  padding: 22px clamp(16px, 3.4vw, 56px) 56px !important;
  font-family: "Manrope", "Noto Sans SC", "Microsoft YaHei UI", Arial, sans-serif;
}
.app-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  padding: 0 2px;
}
.brand-lockup { display: flex; align-items: center; gap: 10px; }
.brand-mark { display: grid; place-items: center; width: 28px; height: 28px; color: var(--surface); background: var(--ink); font-family: "DM Mono", monospace; font-size: .68rem; font-weight: 500; letter-spacing: -.08em; }
.brand-name { color: var(--ink); font-size: .83rem; font-weight: 800; letter-spacing: .15em; }
.topbar-meta { color: var(--muted); font-family: "DM Mono", monospace; font-size: .68rem; letter-spacing: .04em; }
.movie-hero {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 32px;
  align-items: end;
  margin-bottom: 18px;
  padding: clamp(30px, 5vw, 64px);
  border-radius: 3px;
  color: var(--surface);
  background: var(--ink);
  box-shadow: 0 18px 38px rgba(29,25,19,.12);
}
.movie-hero::after {
  content: "";
  position: absolute;
  inset: -24% -5% auto auto;
  width: min(42vw, 560px);
  aspect-ratio: 1;
  border: 1px solid rgba(255,253,248,.22);
  border-radius: 50%;
}
.movie-hero__eyebrow {
  margin: 0 0 13px;
  color: #d8d0c4;
  font-family: "DM Mono", monospace;
  font-size: .68rem;
  font-weight: 500;
  letter-spacing: .12em;
  text-transform: uppercase;
}
.movie-hero h1 { position: relative; z-index: 1; margin: 0; color: var(--surface) !important; font-family: "Noto Serif SC", "Songti SC", Georgia, serif !important; font-size: clamp(2.35rem, 4.5vw, 4.5rem); font-weight: 600; letter-spacing: .1em; line-height: 1.05; }
.movie-hero p:last-child { position: relative; z-index: 1; max-width: 600px; margin: 18px 0 0; color: #d8d0c4 !important; font-size: .98rem; line-height: 1.8; }
.hero-status { position: relative; z-index: 1; display: grid; gap: 9px; min-width: 205px; padding: 16px 17px; border: 1px solid rgba(255,253,248,.24); background: rgba(255,253,248,.06); font-size: .77rem; line-height: 1.45; }
.hero-status::before { content: "LIVE"; color: #ef725f; font-family: "DM Mono", monospace; font-size: .62rem; letter-spacing: .14em; }
.hero-status strong { color: var(--surface); font-size: .92rem; letter-spacing: .04em; }
.hero-status span { color: #d8d0c4; }
.panel {
  padding: 22px !important;
  border: 1px solid var(--line) !important;
  border-radius: 3px !important;
  background: var(--surface) !important;
  box-shadow: none !important;
}
.panel-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin: 0 0 18px; padding-bottom: 14px; border-bottom: 1px solid var(--line); }
.panel-title { margin: 0; color: var(--ink); font-family: "DM Mono", monospace; font-size: .69rem; font-weight: 500; letter-spacing: .1em; text-transform: uppercase; }
.panel-kicker { color: var(--muted); font-size: .76rem; }
.panel-note { margin: -5px 0 18px; color: var(--muted); font-size: .81rem; line-height: 1.65; }
.stage-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  margin: 0 0 18px;
  border: 1px solid var(--line);
  background: var(--line);
}
.stage-strip span {
  display: block;
  padding: 16px 14px;
  color: var(--ink);
  background: var(--surface);
  font-size: .78rem;
  font-weight: 700;
  letter-spacing: .03em;
}
.stage-strip b { display: block; margin-bottom: 5px; color: var(--muted); font-family: "DM Mono", monospace; font-size: .62rem; font-weight: 500; letter-spacing: .09em; }
.stage-strip span:nth-child(1), .stage-strip span:nth-child(2) { background: #f0ece3; }
.stage-strip span:nth-child(3) { color: var(--surface); background: var(--ink); }
.stage-strip span:nth-child(3) b { color: #ef725f; }
#create-button, #create-button button, #render-button, #render-button button {
  min-height: 48px;
  border: 1px solid var(--ink) !important;
  border-radius: 2px !important;
  color: var(--surface) !important;
  background: var(--ink) !important;
  box-shadow: none !important;
  font-weight: 700 !important;
  letter-spacing: .04em;
  transition: background .18s ease, color .18s ease, border-color .18s ease !important;
}
.render-note { margin: 10px 0 0; color: var(--muted); font-size: .72rem; line-height: 1.55; }
#render-button, #render-button button { border-color: var(--accent) !important; background: var(--accent) !important; }
#create-button:hover, #create-button button:hover { color: var(--ink) !important; background: var(--surface-muted) !important; }
#render-button:hover, #render-button button:hover { border-color: var(--accent-deep) !important; background: var(--accent-deep) !important; }
button.secondary, button:not(.primary) { border-radius: 2px !important; }
button, textarea, input, .wrap, .prose, .markdown { font-family: "Manrope", "Noto Sans SC", "Microsoft YaHei UI", Arial, sans-serif !important; }
.prose h1, .prose h2, .prose h3, .markdown h1, .markdown h2, .markdown h3 { font-family: "Noto Serif SC", "Songti SC", Georgia, serif !important; color: var(--ink); }
.prose h2, .markdown h2 { margin-top: 1.45rem !important; padding-top: 1.15rem !important; border-top: 1px solid var(--line); font-size: 1.2rem !important; }
.prose p, .markdown p, .prose li, .markdown li { color: #413d38 !important; line-height: 1.8 !important; }
.block, .form, .gr-box, .gr-panel { border-color: var(--line) !important; }
label span { color: var(--ink) !important; font-weight: 700; }
#create-button button:focus-visible, #render-button button:focus-visible, button:focus-visible, input:focus-visible, textarea:focus-visible { outline: 3px solid rgba(221,78,56,.35) !important; outline-offset: 2px !important; }
input[type="range"] { accent-color: var(--accent) !important; }
textarea, input, .wrap-inner { border-radius: 2px !important; }
#status textarea, #final-output textarea { color: var(--ink) !important; background: #f0ece3 !important; font-family: "DM Mono", monospace !important; font-size: .75rem !important; }
#final-video { overflow: hidden; border: 1px solid var(--line); border-radius: 3px; }
.workspace-status { display: grid; grid-template-columns: 1.6fr .9fr; gap: 18px; align-items: start; }
.status-meta { padding: 4px 0; }
.status-meta__label { margin-bottom: 5px; color: var(--muted); font-family: "DM Mono", monospace; font-size: .62rem; letter-spacing: .1em; text-transform: uppercase; }
.status-meta__copy { color: var(--ink); font-size: .8rem; font-weight: 700; line-height: 1.55; }
.status-meta__copy span { display: block; margin-top: 5px; color: var(--muted); font-size: .73rem; font-weight: 500; }
.tabs { margin-top: 18px !important; }
.tabs > .tab-nav { gap: 18px !important; border-bottom: 1px solid var(--line) !important; }
.tabs > .tab-nav button { padding: 11px 0 !important; color: var(--muted) !important; font-weight: 700 !important; }
.tabs > .tab-nav button.selected { color: var(--ink) !important; border-color: var(--accent) !important; }
.tabs > .tab-nav button:hover { color: var(--ink) !important; }
.asset-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 0 0 16px; }
.asset-card { min-height: 80px; padding: 14px; border: 1px solid var(--line); background: #faf7f0; }
.asset-card b { display: block; margin-bottom: 7px; color: var(--ink); font-size: .8rem; }
.asset-card span { color: var(--muted); font-size: .72rem; line-height: 1.45; }
.file-delivery { padding: 22px; border: 1px dashed #bdb2a3; background: #f7f3eb; }
.file-delivery h3 { margin: 0 0 8px; font-family: "Noto Serif SC", serif; font-size: 1.25rem; }
.file-delivery p { margin: 0; color: var(--muted); font-size: .82rem; line-height: 1.65; }
button { cursor: pointer !important; }
button[disabled] { opacity: .48 !important; cursor: not-allowed !important; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; } }
@media (max-width: 760px) {
  .gradio-container { padding: 16px !important; }
  .app-topbar { align-items: flex-start; }
  .topbar-meta { display: none; }
  .movie-hero { padding: 30px 24px; }
  .movie-hero { grid-template-columns: 1fr; }
  .movie-hero h1 { font-size: 2rem; letter-spacing: .055em; }
  .hero-status { min-width: 0; }
  .stage-strip { grid-template-columns: repeat(2, 1fr); }
  .workspace-status, .asset-grid { grid-template-columns: 1fr; }
  .panel { padding: 17px !important; }
}
"""


def create_project(idea: str, duration: int, visual_style: str):
    try:
        project = orchestrator.create_project(idea, duration, visual_style)
    except Exception as error:
        return ("", "", "", "", "", f"## 任务日志\n- 失败：{error}", f"创作失败：{error}", "", _hidden_video(), gr.update())
    text_mode = "ModelScope AI 文案" if orchestrator.using_creative_llm else "mock 文案"
    video_mode = "Spark 真实视频待生成" if settings.video_generation_mode == "comfyui" else "mock 视频流程"
    return _project_outputs(
        project,
        f"已完成：{text_mode} + {video_mode}（{project.project_id}）",
        gr.update(choices=orchestrator.store.list_project_ids(), value=project.project_id),
    )


def load_project(project_id: str):
    if not project_id:
        return ("", "", "", "", "", "## 任务日志\n- 请先选择一个项目。", "尚未选择项目", "", _hidden_video(), gr.update())
    try:
        project = orchestrator.store.load(project_id)
    except Exception as error:
        return ("", "", "", "", "", f"## 任务日志\n- 失败：{error}", f"读取失败：{error}", "", _hidden_video(), gr.update())
    return _project_outputs(project, f"已恢复项目：{project.project_id}", gr.update(value=project.project_id))


def refresh_history():
    project_ids = orchestrator.store.list_project_ids()
    return gr.update(choices=project_ids, value=project_ids[0] if project_ids else None)


def regenerate_shot(project_id: str, shot_number: int):
    try:
        project = orchestrator.regenerate_shot(project_id, int(shot_number))
    except Exception as error:
        return ("", "", "", "", "", f"## 任务日志\n- 失败：{error}", f"重新规划失败：{error}", "", _hidden_video(), gr.update())
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
        return ("", "", "", "", "", f"## 任务日志\n- 失败：{error}", f"渲染失败：{error}", "", _hidden_video(), gr.update())
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
        _video_update(project.final_output_placeholder),
        history_update,
    )


def _hidden_video():
    return gr.update(value=None, visible=False)


def _video_update(path: str | None):
    if path and Path(path).is_file():
        return gr.update(value=path, visible=True)
    return _hidden_video()


with gr.Blocks(title="Movie-Agent · 流影制片台", css=APP_CSS) as demo:
    gr.HTML(
        """
        <header class="app-topbar">
          <div class="brand-lockup"><span class="brand-mark">M/A</span><span class="brand-name">MOVIE AGENT</span></div>
          <div class="topbar-meta">ORIGINAL IDEAS / STRUCTURED PRODUCTION / V1.0</div>
        </header>
        <section class="movie-hero">
          <div><p class="movie-hero__eyebrow">A production desk for original sci-fi shorts</p><h1>流影制片台</h1><p>把一句原创科幻创意，组织成可审阅、可渲染、可交付的短片生产流程。</p></div>
          <aside class="hero-status"><strong>制作引擎就绪</strong><span>文案策划 · H3 生成 · FFmpeg 合片</span></aside>
        </section>
        """
    )
    with gr.Row(equal_height=False):
        with gr.Column(scale=1):
            with gr.Group(elem_classes="panel"):
                gr.HTML("<div class='panel-heading'><div class='panel-title'>01 / 新建项目</div><div class='panel-kicker'>从创意开始</div></div>")
                gr.HTML("<p class='panel-note'>先完成策划与分镜确认；视频生成会在你主动提交后才使用 Spark 资源。</p>")
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
                gr.HTML("<p class='render-note'>系统会保存项目方案、制作日志与每一个镜头状态。</p>")
            with gr.Group(elem_classes="panel"):
                gr.HTML("<div class='panel-heading'><div class='panel-title'>02 / 项目库</div><div class='panel-kicker'>可随时恢复</div></div>")
                gr.HTML("<p class='panel-note'>打开已有项目，或针对不满意的镜头重新生成其策划方案。</p>")
                history = gr.Dropdown(
                    choices=orchestrator.store.list_project_ids(), label="已保存项目", interactive=True
                )
                with gr.Row():
                    refresh = gr.Button("刷新历史")
                    load = gr.Button("打开项目")
                shot_number = gr.Slider(1, 10, value=1, step=1, label="要重新规划的镜头号")
                regenerate = gr.Button("重新规划单个镜头")
        with gr.Column(scale=2):
            gr.HTML("<div class='stage-strip'><span><b>01 / PLAN</b>设定与剧本</span><span><b>02 / PREVIS</b>分镜与视觉</span><span><b>03 / RENDER</b>H3 生成</span><span><b>04 / DELIVER</b>剪辑成片</span></div>")
            with gr.Group(elem_classes="panel"):
                gr.HTML("<div class='panel-heading'><div class='panel-title'>制作工作区</div><div class='panel-kicker'>状态与交付控制</div></div>")
                with gr.Row(elem_classes="workspace-status"):
                    status = gr.Textbox(label="当前制作状态", interactive=False, elem_id="status", placeholder="输入创意后，制作状态会显示在这里。")
                    gr.HTML("<div class='status-meta'><div class='status-meta__label'>Render policy</div><div class='status-meta__copy'>先策划，后渲染<span>仅在你点击“提交 Spark 生成”后，才会启动逐镜生成与合片。</span></div></div>")
                with gr.Row():
                    project_id = gr.Textbox(label="项目 ID", interactive=False, placeholder="尚未创建项目")
                    final_output = gr.Textbox(label="成片输出路径", interactive=False, elem_id="final-output", placeholder="成片完成后显示")
                render = gr.Button("提交 Spark 真实生成", variant="primary", elem_id="render-button")
                gr.HTML("<p class='render-note'>生成任务会逐镜执行质检；中断后可从已通过的镜头继续。</p>")
            with gr.Tabs():
                with gr.Tab("创作资产"):
                    with gr.Group(elem_classes="panel"):
                        gr.HTML("<div class='panel-heading'><div class='panel-title'>创作资产</div><div class='panel-kicker'>导演 · 编剧 · 视觉设定</div></div><div class='asset-grid'><div class='asset-card'><b>项目设定</b><span>主题、人物、世界观与影片规格</span></div><div class='asset-card'><b>剧本与旁白</b><span>可朗读的叙事与节奏骨架</span></div><div class='asset-card'><b>视觉规范</b><span>角色卡、场景卡与统一风格</span></div></div>")
                        brief = gr.Markdown("*创建项目后，这里会出现导演 Agent 的项目设定。*")
                        script = gr.Markdown("*剧本与旁白将在策划完成后显示。*")
                        visual_bible = gr.Markdown("*角色、场景和风格规范将在这里汇总。*")
                with gr.Tab("分镜制作"):
                    with gr.Group(elem_classes="panel"):
                        gr.HTML("<div class='panel-heading'><div class='panel-title'>镜头计划与日志</div><div class='panel-kicker'>6–10 个可渲染镜头</div></div>")
                        storyboard = gr.Markdown("*创建项目后，分镜 Agent 会在这里给出结构化镜头计划。*")
                        logs = gr.Markdown("*任务日志会记录每一步制作决策。*")
                with gr.Tab("交付文件"):
                    with gr.Group(elem_classes="panel"):
                        gr.HTML("<div class='file-delivery'><h3>交付中心</h3><p>生成完成后，在此预览最终 MP4，并导出可提交的项目 JSON 与 Markdown 制作档案。</p></div>")
                        final_video = gr.Video(label="最终成片", interactive=False, visible=False, elem_id="final-video")
                        export = gr.Button("导出项目档案（JSON + Markdown）")
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
